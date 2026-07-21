"""Maintenance intelligence: fuses work order history, inspections, incidents
and OEM/handover knowledge per asset — failure timelines, MTBF, health scores
and generated recommendations with document citations.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime

TRACKED_TYPES = ("work_order", "inspection", "incident")

# Pulls the actual root-cause clause out of the cited work order / incident
# text, rather than asserting a fixed conclusion in code. Matches "Root cause
# suspected to be X." / "Root cause: X." / "Root cause was X." and stops at
# the first sentence boundary.
ROOT_CAUSE_RE = re.compile(r"root cause(?:\s+(?:is|was|suspected to be))?\s*:?\s*([^.\n]+)", re.I)


def _d(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _primary_equipment(doc) -> list[str]:
    raw = doc.meta.get("equipment", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _find_root_cause(by_id: dict, doc_ids: list[str]) -> tuple[str, str] | None:
    """Search the cited records for an explicit root-cause statement and
    return (clause, source_doc_id) — quoting evidence instead of authoring a
    conclusion. Returns None when no record states one, which the caller
    treats as an honest "not yet determined" rather than guessing."""
    for doc_id in doc_ids:
        doc = by_id.get(doc_id)
        if not doc:
            continue
        m = ROOT_CAUSE_RE.search(doc.body)
        if m:
            clause = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;")
            if clause:
                return clause, doc_id
    return None


def build_assets(docs: list, compliance: dict, today: date | None = None) -> list[dict]:
    today = today or date.today()
    by_id = {d.id: d for d in docs}
    events = defaultdict(list)          # tag -> event dicts
    related = defaultdict(set)          # tag -> all doc ids that mention it

    for doc in docs:
        tags = _primary_equipment(doc)
        for tag in doc.entities.get("equipment", {}):
            related[tag].add(doc.id)
        if doc.type in TRACKED_TYPES and tags:
            for tag in tags[:1] if doc.type == "work_order" else tags:
                events[tag].append({
                    "doc_id": doc.id,
                    "date": doc.date,
                    "type": doc.type,
                    "title": doc.title,
                    "failure_mode": doc.meta.get("failure_mode", ""),
                    "downtime_hours": float(doc.meta.get("downtime_hours", 0) or 0),
                    "cost_inr": float(doc.meta.get("cost_inr", 0) or 0),
                    "status": doc.meta.get("status", ""),
                })

    gap_equipment = defaultdict(list)
    for finding in compliance["findings"]:
        if finding["status"] in ("gap", "due_soon"):
            for tag in finding["equipment"]:
                gap_equipment[tag].append(finding)

    memo_docs = [d for d in docs if d.type in ("memo", "oem_manual")]
    assets = []
    tags = sorted(set(events) | set(gap_equipment), key=lambda t: -len(events.get(t, [])))
    for tag in tags:
        evs = sorted(events.get(tag, []), key=lambda e: e["date"])
        corrective = [e for e in evs if e["type"] == "work_order"
                      and e["failure_mode"] not in ("", "preventive")]
        downtime = sum(e["downtime_hours"] for e in evs)
        cost = sum(e["cost_inr"] for e in evs)
        modes = Counter(e["failure_mode"] for e in corrective if e["failure_mode"])

        mtbf_days = None
        dates = [d for d in (_d(e["date"]) for e in corrective) if d]
        if len(dates) >= 2:
            gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
            mtbf_days = round(sum(gaps) / len(gaps))

        health = 100
        recent = [e for e in corrective if _d(e["date"]) and (today - _d(e["date"])).days < 900]
        health -= 14 * len(recent)
        health -= 18 * len([f for f in gap_equipment.get(tag, []) if f["status"] == "gap"])
        health -= 8 * len([f for f in gap_equipment.get(tag, []) if f["status"] == "due_soon"])
        if any(e["type"] == "incident" for e in evs):
            health -= 10
        if any(e["type"] == "inspection" and e["status"] == "open" for e in evs):
            health -= 12
        health = max(health, 5)

        recommendations = []
        for mode, n in modes.items():
            if n >= 2:
                cites = [e["doc_id"] for e in corrective if e["failure_mode"] == mode]
                knowledge = [d.id for d in memo_docs if tag in d.entities.get("equipment", {})]
                # Quote the root cause from the cited records rather than
                # asserting one — this generalises to any corpus instead of a
                # single fixed narrative, and is honest when no record states
                # a cause yet.
                found = _find_root_cause(by_id, cites)
                if found:
                    clause, source = found
                    text = (f'Recurring failure pattern: {n}× "{mode}" ({", ".join(cites)}). '
                            f'Root cause per {source}: {clause}. Review whether the corrective '
                            f'action from that record has actually closed the gap.')
                else:
                    text = (f'Recurring failure pattern: {n}× "{mode}" ({", ".join(cites)}). '
                            f'No explicit root cause is recorded in the cited documents — review '
                            f'against OEM limits and recent operating conditions.')
                recommendations.append({
                    "kind": "recurring_failure",
                    "priority": "high",
                    "text": text,
                    "docs": cites + knowledge,
                })
        for finding in gap_equipment.get(tag, []):
            recommendations.append({
                "kind": "compliance",
                "priority": "high" if finding["status"] == "gap" else "medium",
                "text": f"{finding['title']}: {finding['detail']}",
                "docs": finding["evidence"],
            })
        knowledge = [d.id for d in memo_docs if tag in d.entities.get("equipment", {})]
        if knowledge and not any(r["kind"] == "recurring_failure" for r in recommendations):
            recommendations.append({
                "kind": "knowledge",
                "priority": "info",
                "text": "Expert knowledge available for this asset (OEM manual / retirement handover notes).",
                "docs": knowledge,
            })

        assets.append({
            "tag": tag,
            "events": evs,
            "related_docs": sorted(related.get(tag, set())),
            "corrective_count": len(corrective),
            "downtime_hours": downtime,
            "cost_inr": cost,
            "failure_modes": dict(modes),
            "mtbf_days": mtbf_days,
            "health": health,
            "recommendations": recommendations,
        })

    assets.sort(key=lambda a: a["health"])
    return assets


def plant_summary(assets: list) -> dict:
    monthly = defaultdict(float)
    for asset in assets:
        for e in asset["events"]:
            if e["downtime_hours"] and e["date"]:
                monthly[e["date"][:7]] += e["downtime_hours"]
    return {
        "total_downtime_hours": sum(a["downtime_hours"] for a in assets),
        "total_cost_inr": sum(a["cost_inr"] for a in assets),
        "assets_at_risk": len([a for a in assets if a["health"] < 60]),
        "downtime_by_month": [
            {"month": m, "hours": h} for m, h in sorted(monthly.items())
        ],
    }
