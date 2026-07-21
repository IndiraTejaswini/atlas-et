"""Lessons Learned & Failure Intelligence Engine.

Analyses incidents, near-misses and failure records across the *whole* corpus —
not one asset at a time — to surface systemic patterns that no single review
would see, matches them against a reference library of known industry failure
signatures, and pushes forward-looking warnings before conditions recur.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("atlas.lessons")
from collections import defaultdict

# Reference library of known industry failure signatures (stand-in for an
# external industry failure database; each entry is a recognised cause→effect
# pattern from OISD / API / OEM practice). ATLAS matches internal patterns
# against these to say "this is a known industry failure mode, not a one-off".
INDUSTRY_SIGNATURES = [
    {
        "id": "SIG-SEAL-FLUSH",
        "name": "API Plan 32 flush loss → seal failure",
        "signature": r"flush|plan 32|seal",
        "modes": {"Mechanical seal failure", "Wax blockage"},
        "note": "Loss/degradation of external seal flush causes seal-face overheating and failure within 200–400 operating hours (API 682 / OEM guidance).",
    },
    {
        "id": "SIG-CUI",
        "name": "Corrosion under insulation at cold-trap points",
        "signature": r"insulation|cui|saddle",
        "modes": {"Corrosion under insulation"},
        "note": "Water ingress under insulation at saddles/supports in the 60–175 °C band drives localised CUI (OISD-STD-128).",
    },
    {
        "id": "SIG-WAX-FEED",
        "name": "Waxy-feed changeover accelerates fouling",
        "signature": r"wax|asphaltene|pour point|mangala",
        "modes": {"Wax blockage", "Fouling"},
        "note": "High-wax/asphaltene feedstock roughly doubles preheat fouling and blocks small-bore support lines, especially in winter.",
    },
    {
        "id": "SIG-MOC",
        "name": "Change bypassing Management of Change",
        "signature": r"management of change|\bmoc\b|slate change|without review",
        "modes": set(),
        "note": "Feedstock or process changes implemented without an MOC review repeatedly precede equipment-support failures.",
    },
]


def _incidents(docs):
    return [d for d in docs if d.type in ("incident",)]


def analyze(docs, graph, compliance, assets) -> dict:
    incidents = _incidents(docs)

    # ---- 1. Fleet-wide recurring failure patterns -------------------------
    # doc_count reflects how widely a mode is discussed across the corpus;
    # asset attribution is restricted to the primary equipment of *event*
    # documents (work orders / inspections / incidents) so a mode is only
    # tied to assets that actually exhibited it — not every tag co-mentioned.
    EVENT_TYPES = ("work_order", "inspection", "incident")
    mode_docs = defaultdict(set)
    mode_assets = defaultdict(set)
    mode_years = defaultdict(set)
    # (mode, asset) -> (earliest date, doc_id) — lets warnings name *which*
    # asset was first affected and which followed, computed from the actual
    # record dates instead of a fixed narrative naming specific tags.
    mode_asset_first: dict[tuple[str, str], tuple[str, str]] = {}
    for d in docs:
        primary = {t.strip() for t in d.meta.get("equipment", "").split(",") if t.strip()}
        year = d.date[:4] if d.date else ""
        for mode in d.entities.get("failure_mode", {}):
            mode_docs[mode].add(d.id)
            if d.type in EVENT_TYPES:
                mode_assets[mode] |= primary
                if d.date:
                    for tag in primary:
                        key = (mode, tag)
                        if key not in mode_asset_first or d.date < mode_asset_first[key][0]:
                            mode_asset_first[key] = (d.date, d.id)
            if year:
                mode_years[mode].add(year)

    patterns = []
    for mode, dset in mode_docs.items():
        if len(dset) < 2:
            continue
        assets_hit = sorted(a for a in mode_assets[mode] if re.match(r"[A-Z]+-\d", a))
        sigs = [s["name"] for s in INDUSTRY_SIGNATURES if mode in s["modes"]]
        strength = "high" if len(dset) >= 3 else "medium"
        # Timeline of which asset was affected first, computed from dates —
        # ordered oldest-to-newest so the most recently affected asset (the
        # "leading indicator" case) is last.
        timeline = sorted(
            ({"asset": a, "date": mode_asset_first[(mode, a)][0], "doc": mode_asset_first[(mode, a)][1]}
             for a in assets_hit if (mode, a) in mode_asset_first),
            key=lambda t: t["date"],
        )
        patterns.append({
            "mode": mode,
            "doc_count": len(dset),
            "asset_count": len(assets_hit),
            "assets": assets_hit[:8],
            "docs": sorted(dset),
            "years": sorted(mode_years[mode]),
            "industry_match": sigs,
            "strength": strength,
            "asset_timeline": timeline,
        })
    patterns.sort(key=lambda p: (-p["doc_count"], -p["asset_count"]))

    # ---- 2. Systemic organisational themes --------------------------------
    themes = []
    theme_defs = [
        # Bounded `.{0,N}` rather than unbounded `.*` — semantically tighter
        # (catches "without ... review" as a local phrase, not two words that
        # happen to both appear anywhere in a multi-page document) and avoids
        # relying on the regex engine to behave well on attacker-supplied
        # document text of arbitrary length.
        ("Change management (MOC) bypass",
         r"management of change|\bmoc\b|without.{0,80}review|no moc",
         "Changes implemented without formal Management of Change review."),
        ("Stale controlled documents",
         r"out-of-date procedure|past.{0,80}review|stale (permit|procedure)|review was due",
         "Procedures/permits past their review date driving field-practice gaps."),
        ("Undocumented tribal knowledge",
         r"never (wrote|written) into|not in any manual|in my head|lost in a revision",
         "Critical operating knowledge existing only in individuals' heads."),
    ]
    for name, pattern, desc in theme_defs:
        rx = re.compile(pattern, re.I)
        hits = sorted(d.id for d in docs if rx.search(d.body))
        if len(hits) >= 1:
            themes.append({"name": name, "description": desc, "docs": hits, "count": len(hits)})
    themes.sort(key=lambda t: -t["count"])

    # ---- 3. Extracted learnings from incident/near-miss reports -----------
    learnings = []
    for inc in incidents:
        m = re.search(r"\*\*Learning:\*\*\s*(.+?)(?:\n\n|\Z)", inc.body, re.S)
        if m:
            learnings.append({"doc": inc.id, "title": inc.title, "text": re.sub(r"\s+", " ", m.group(1)).strip()})

    # ---- 4. Proactive, forward-looking warnings ---------------------------
    warnings = []

    # (a) Recurring failure mode spreading to additional assets over time —
    # "who was affected first, who followed" is read from asset_timeline
    # (computed above from record dates), not asserted as a fixed narrative.
    wax = next((p for p in patterns if p["mode"] == "Wax blockage"), None)
    if wax and wax["asset_count"] >= 2 and wax["asset_timeline"]:
        timeline = wax["asset_timeline"]
        earliest, latest = timeline[0], timeline[-1]
        sig_note = next((s["note"] for s in INDUSTRY_SIGNATURES if s["id"] == "SIG-WAX-FEED"), "")
        spread = (
            f' {earliest["asset"]} was affected first ({earliest["date"]}, per {earliest["doc"]}); '
            f'{latest["asset"]} shows the pattern most recently ({latest["date"]}, per {latest["doc"]}) — '
            f'treat newly-affected assets as a leading indicator and inspect before the next failure window.'
            if latest["asset"] != earliest["asset"] else
            f' First recorded on {earliest["asset"]} ({earliest["date"]}, per {earliest["doc"]}).'
        )
        warnings.append({
            "severity": "high",
            "title": f'"{wax["mode"]}" is spreading across the fleet',
            "text": (f'"{wax["mode"]}" now appears on {wax["asset_count"]} assets '
                     f'({", ".join(wax["assets"])}) across {len(wax["years"])} year(s).{spread}'
                     + (f' {sig_note}' if sig_note else '')),
            "docs": wax["docs"],
            "matches_signature": "SIG-WAX-FEED",
        })

    # (b) MOC bypass with still-open corrective actions — the affected
    # documents, co-occurring failure modes and any open action text are all
    # read from the records rather than naming a fixed incident.
    moc_docs = sorted({d.id for d in docs if re.search(r"management of change|\bmoc\b", d.body, re.I)})
    if moc_docs:
        open_actions = []
        linked_modes = set()
        for d in docs:
            if d.id in moc_docs:
                open_actions += re.findall(r"\d\.\s+([^\n]+?)\s+—\s+OPEN", d.body)
                linked_modes |= set(d.entities.get("failure_mode", {}))
        consequence = f' Documents referencing it also record: {", ".join(sorted(linked_modes))}.' if linked_modes else ''
        action_note = f' Open corrective action(s) from that review: {"; ".join(a.strip() for a in open_actions)}.' if open_actions else ''
        warnings.append({
            "severity": "high",
            "title": "A change bypassed Management of Change",
            "text": (f'{len(moc_docs)} document(s) reference a change made without a formal MOC review '
                     f'({", ".join(moc_docs)}).{consequence} This is a repeatable organisational failure — '
                     f'any future process or feedstock change should trigger an MOC review before '
                     f'implementation.{action_note}'),
            "docs": moc_docs,
            "matches_signature": "SIG-MOC",
        })

    # (c) Stale procedure that already caused an incident and is still overdue
    stale_gaps = [f for f in compliance["findings"]
                  if f["status"] == "gap" and "review" in f["id"] and "NM-517" in f.get("evidence", [])]
    for f in stale_gaps:
        warnings.append({
            "severity": "medium",
            "title": "A stale procedure already implicated in a near-miss is still overdue",
            "text": (f"{f['title']} — {f['detail']} The same pattern (out-of-date controlled document → field "
                     f"practice gap) is a recognised recurring theme; close the review before the next permit cycle."),
            "docs": f["evidence"],
            "matches_signature": None,
        })

    # (d) An open inspection with a finite remaining life
    for d in docs:
        if d.type == "inspection" and d.meta.get("status") == "open" and re.search(r"remaining life", d.body, re.I):
            rl = re.search(r"[Rr]emaining life[^.]*?(\d+)\s*year", d.body)
            warnings.append({
                "severity": "medium",
                "title": f"{d.meta.get('equipment', d.id)} is on a finite remaining-life clock",
                "text": (f"{d.title} records active degradation"
                         + (f" with ~{rl.group(1)} years remaining life" if rl else "")
                         + ". Ensure the re-inspection interval is not deferred — deferral is how slow degradation becomes a failure."),
                "docs": [d.id],
                "matches_signature": "SIG-CUI" if "CUI" in d.body or "insulation" in d.body.lower() else None,
            })
            break

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    warnings.sort(key=lambda w: severity_rank.get(w["severity"], 3))

    logger.info("lessons analysis: %d incidents, %d fleet-wide patterns, %d themes, %d active warnings",
               len(incidents), len(patterns), len(themes), len(warnings))
    return {
        "patterns": patterns,
        "themes": themes,
        "learnings": learnings,
        "warnings": warnings,
        "industry_signatures": INDUSTRY_SIGNATURES_public(),
        "stats": {
            "incidents_analysed": len(incidents),
            "patterns_found": len(patterns),
            "warnings_active": len(warnings),
            "signatures_matched": len({w["matches_signature"] for w in warnings if w["matches_signature"]}),
        },
    }


def INDUSTRY_SIGNATURES_public():
    return [{"id": s["id"], "name": s["name"], "note": s["note"]} for s in INDUSTRY_SIGNATURES]
