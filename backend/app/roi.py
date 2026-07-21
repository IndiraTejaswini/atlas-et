"""Business-impact / avoidable-cost engine.

Computes the concrete downtime and cost that connecting the dots earlier would
have avoided. Method: for each asset, order its corrective failures by failure
mode; the *first* occurrence is unavoidable detection, but every *repeat* of a
mode already seen was preventable — the pattern (and its fix) was already in
the record. Sum the downtime, cost and linked incidents of those repeats.
Nothing is assumed: every rupee traces to a work order in the corpus.
"""
from __future__ import annotations

from datetime import datetime


def _d(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def compute(docs: list) -> dict:
    # collect corrective work-order events
    events = []
    for d in docs:
        if d.type == "work_order":
            fm = d.meta.get("failure_mode", "")
            if fm and fm != "preventive":
                events.append({
                    "id": d.id, "asset": d.meta.get("equipment", "").split(",")[0].strip(),
                    "mode": fm, "date": d.date,
                    "downtime": float(d.meta.get("downtime_hours", 0) or 0),
                    "cost": float(d.meta.get("cost_inr", 0) or 0),
                })

    # group by (asset, mode), order by date; repeats are avoidable
    from collections import defaultdict
    groups = defaultdict(list)
    for e in events:
        groups[(e["asset"], e["mode"])].append(e)

    avoidable = []
    for key, evs in groups.items():
        evs.sort(key=lambda e: e["date"] or "")
        for e in evs[1:]:  # every repeat after the first
            avoidable.append(e)

    # incidents/near-misses tied to an avoidable recurrence (same asset + mode)
    avoidable_keys = {(e["asset"], e["mode"]) for e in avoidable}
    avoided_incidents = []
    for d in docs:
        if d.type == "incident":
            asset = d.meta.get("equipment", "").split(",")[0].strip()
            mode = d.meta.get("failure_mode", "")
            if (asset, mode) in avoidable_keys:
                avoided_incidents.append(d.id)

    downtime = sum(e["downtime"] for e in avoidable)
    cost = sum(e["cost"] for e in avoidable)
    cite = sorted({e["id"] for e in avoidable} | set(avoided_incidents)
                  | {evs[0]["id"] for key, evs in groups.items() if len(evs) > 1})

    headline = None
    if avoidable:
        top = max(avoidable, key=lambda e: e["cost"])
        first = groups[(top["asset"], top["mode"])][0]
        headline = (
            f"The repeat {top['mode']} on {top['asset']} ({top['id']}, {top['date']}) "
            f"replayed a root cause already recorded in {first['id']} months earlier. "
            f"Surfacing that pattern after the first event would have avoided it.")

    return {
        "avoidable_downtime_hours": round(downtime, 1),
        "avoidable_cost_inr": round(cost),
        "avoided_incidents": len(avoided_incidents),
        "recurrence_count": len(avoidable),
        "headline": headline,
        "docs": cite,
        "detail": [
            {"id": e["id"], "asset": e["asset"], "mode": e["mode"], "date": e["date"],
             "downtime": e["downtime"], "cost": e["cost"]}
            for e in sorted(avoidable, key=lambda e: -e["cost"])
        ],
    }
