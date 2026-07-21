"""Proactive alert routing — the "push to teams" mechanism.

Aggregates every forward-looking signal in the platform — Lessons-Learned
warnings, real-time telemetry breaches, quality deviations and compliance
gaps — into a single alert stream, routes each to the responsible team by
content, and tracks acknowledgement. This is what turns intelligence into
action: the right team is notified before a condition escalates.

Delivery beyond the app itself (`dispatch_new`, below) was previously just
the routing metadata on each alert ("team": "Rotating Equipment") with no
actual outbound send — the in-app queue *was* the whole delivery mechanism.
`dispatch_new` closes that gap with a real, generic webhook POST (Slack's
incoming-webhook JSON shape, which Teams/Discord/most alerting stacks also
accept or can be adapted to trivially) — same optional-capability pattern as
OCR/vision/Claude elsewhere in this codebase: no `ATLAS_ALERT_WEBHOOK_URL`
configured, and it's a documented no-op rather than a silent lie.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("atlas.alerts")

# Acknowledgement store, persisted to disk — alert ids are stable hashes of
# their source + title (see _mk), so an ack survives both polling and a
# process restart; previously this was in-memory only and every restart
# silently un-acknowledged every alert.
_ACK_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts_ack.json"


def _load_acks() -> dict[str, dict]:
    try:
        if _ACK_STORE_PATH.exists():
            return json.loads(_ACK_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("could not read alert-ack store at %s — starting empty", _ACK_STORE_PATH, exc_info=True)
    return {}


def _save_acks() -> None:
    try:
        _ACK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ACK_STORE_PATH.write_text(json.dumps(_ACK, indent=2), encoding="utf-8")
    except OSError:
        logger.warning("could not write alert-ack store (non-fatal — ack still applied in memory)", exc_info=True)


_ACK: dict[str, dict] = _load_acks()

# Dispatch-history store, persisted to disk exactly like the ack store above
# (same reasoning: without persistence, a restart would forget which alerts
# were already sent and re-spam every active alert to the webhook). Alert
# ids are already stable hashes of source+title (see _mk), so they double
# as idempotency keys here for free.
_DISPATCH_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts_dispatched.json"

WEBHOOK_URL = os.environ.get("ATLAS_ALERT_WEBHOOK_URL", "").strip()
_WEBHOOK_TIMEOUT_S = 4


def _load_dispatched() -> set[str]:
    try:
        if _DISPATCH_STORE_PATH.exists():
            return set(json.loads(_DISPATCH_STORE_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        logger.warning("could not read dispatch store at %s — starting empty", _DISPATCH_STORE_PATH, exc_info=True)
    return set()


def _save_dispatched() -> None:
    try:
        _DISPATCH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DISPATCH_STORE_PATH.write_text(json.dumps(sorted(_DISPATCHED)), encoding="utf-8")
    except OSError:
        logger.warning("could not write dispatch store (non-fatal)", exc_info=True)


_DISPATCHED: set[str] = _load_dispatched()

TEAMS = {
    "rotating": "Rotating Equipment",
    "integrity": "Inspection & Integrity",
    "safety": "Process Safety",
    "compliance": "Compliance & Regulatory",
    "operations": "Operations",
}


def _route(text: str, equipment: list[str]) -> str:
    t = text.lower()
    eq = " ".join(equipment).upper()
    if re.search(r"seal|bearing|vibration|flush|pump|p-101|rotating|cavitation", t) or eq.startswith("P-101"):
        return "rotating"
    if re.search(r"corrosion|cui|insulation|inspection|exchanger|e-104|vessel|v-302|relief|psv|thickness", t) or "E-104" in eq or "V-302" in eq:
        return "integrity"
    if re.search(r"permit|confined space|hot work|incident|near-miss|management of change|\bmoc\b|safety|fire", t):
        return "safety"
    if re.search(r"oisd|factories act|peso|statutory|waste|license|audit|compliance", t):
        return "compliance"
    return "operations"


def _mk(source, severity, title, detail, docs, equipment, kind_hint=""):
    routing_text = f"{title} {detail} {kind_hint}"
    team = _route(routing_text, equipment or [])
    aid = "alert-" + hashlib.sha1(f"{source}|{title}".encode()).hexdigest()[:10]
    return {
        "id": aid, "source": source, "severity": severity, "title": title,
        "detail": detail, "docs": sorted(set(docs or [])), "equipment": equipment or [],
        "team": TEAMS[team], "team_key": team,
        "acknowledged": _ACK.get(aid),
    }


def build(lessons: dict, quality: dict, compliance: dict, telemetry_mod) -> dict:
    alerts = []

    # 1. Lessons-Learned proactive warnings
    for w in lessons["warnings"]:
        alerts.append(_mk("Failure Intelligence", w["severity"], w["title"], w["text"],
                          w["docs"], _eq_from_docs(w["docs"], compliance)))

    # 2. Real-time telemetry breaches
    for b in telemetry_mod.active_breaches():
        alerts.append(_mk("Live Conditions", b["severity"],
                          f"{b['asset']}: {b['channel']} out of limits", b["detail"],
                          [], [b["asset"]], kind_hint="realtime sensor"))

    # 3. Quality / process deviations
    for d in quality["deviations"]:
        if d["kind"] == "realtime":
            continue  # already covered by telemetry breach above
        alerts.append(_mk("Quality Deviation", d["severity"], d["title"],
                          f"Expected {d['expected']}; observed {d['observed']}. {d['detail']}",
                          d["docs"], [d["asset"]] if d["asset"] else []))

    # 4. Critical / high compliance gaps
    for f in compliance["findings"]:
        if f["status"] == "gap" and f["severity"] in ("critical", "high"):
            alerts.append(_mk("Compliance", f["severity"], f["title"], f["detail"],
                              f["evidence"], f.get("equipment", []),
                              kind_hint=f["standard"]))

    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: (a["acknowledged"] is not None, sev.get(a["severity"], 3)))

    by_team, active = {}, 0
    for a in alerts:
        if not a["acknowledged"]:
            active += 1
            by_team[a["team"]] = by_team.get(a["team"], 0) + 1
    # DEBUG, not INFO: build() runs on every /api/alerts poll and every ~3s
    # SSE tick (see main.py stream_alerts) — an INFO line here would flood
    # the log by design, not by mistake. Available on demand by lowering the
    # log level, silent by default.
    logger.debug("alerts built: %d active, %d acknowledged, by_team=%s", active, len(alerts) - active, by_team)
    return {
        "alerts": alerts,
        "active": active,
        "acknowledged": len(alerts) - active,
        "by_team": by_team,
        "teams": list(TEAMS.values()),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def acknowledge(alert_id: str, by: str = "Operator") -> bool:
    _ACK[alert_id] = {"by": by, "at": time.strftime("%H:%M:%S")}
    _save_acks()
    return True


def unacknowledge(alert_id: str) -> bool:
    _ACK.pop(alert_id, None)
    _save_acks()
    return True


def webhook_configured() -> bool:
    return bool(WEBHOOK_URL)


def _slack_payload(alert: dict) -> dict:
    lines = [f"*[{alert['severity'].upper()}] {alert['title']}*", alert["detail"],
             f"→ routed to *{alert['team']}* · source: {alert['source']}"]
    if alert["docs"]:
        lines.append("Documents: " + ", ".join(alert["docs"]))
    return {"text": "\n".join(lines)}


def _post_webhook(url: str, payload: dict) -> bool:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        logger.warning("alert webhook delivery failed", exc_info=True)
        return False


def dispatch_new(alerts_result: dict, url: str | None = None, poster=_post_webhook) -> dict:
    """Send every active (unacknowledged), not-yet-sent alert to the
    configured webhook. Idempotent — an alert is sent at most once, tracked
    by its stable id in the disk-persisted dispatch store, so re-running
    this against an unchanged alert set sends nothing.

    `url`/`poster` are injectable so this is testable without a real
    endpoint and without monkeypatching module internals. Returns
    {"configured": bool, "sent": int, "failed": int} — never raises; a
    delivery failure is logged and counted, not propagated, because a
    webhook outage must not break the alert queue itself.
    """
    target = WEBHOOK_URL if url is None else url
    if not target:
        return {"configured": False, "sent": 0, "failed": 0}
    sent = failed = 0
    for a in alerts_result["alerts"]:
        if a["acknowledged"] or a["id"] in _DISPATCHED:
            continue
        if poster(target, _slack_payload(a)):
            sent += 1
            _DISPATCHED.add(a["id"])
        else:
            failed += 1
    if sent:
        _save_dispatched()
    return {"configured": True, "sent": sent, "failed": failed}


def send_test_webhook(url: str | None = None, poster=_post_webhook) -> dict:
    """Manual connectivity check — sends one synthetic payload immediately,
    independent of the real alert queue and its dispatch-history dedup, so a
    user can confirm the configured target actually works without waiting
    for a genuine alert to fire."""
    target = WEBHOOK_URL if url is None else url
    if not target:
        return {"configured": False, "sent": False}
    ok = poster(target, {"text": "✅ ATLAS test alert — webhook delivery is configured correctly."})
    return {"configured": True, "sent": ok}


def _eq_from_docs(doc_ids, compliance):
    """Best-effort equipment inference for routing lessons warnings."""
    eq = set()
    for f in compliance["findings"]:
        if set(f["evidence"]) & set(doc_ids):
            eq |= set(f.get("equipment", []))
    joined = " ".join(doc_ids)
    for tag in re.findall(r"P-101[AB]|E-104|V-302|C-201|PSV-\d+", joined):
        eq.add(tag)
    return sorted(eq)
