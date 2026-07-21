"""Optimised preventive-maintenance schedule.

Turns failure history, OEM intervals and compliance due-dates into a single
prioritised maintenance calendar. Task intervals are pulled from the failure
record (an asset that failed every ~150 days gets a tighter cycle), from OEM
manual text (oil-change hours, strainer cleaning), and from statutory due
dates — then sorted so the plant works the highest-risk, soonest-due task
first instead of a flat time-based PM list.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger("atlas.schedule")

OEM_TASKS = [
    (re.compile(r"strainer.*(monthly|every 3 months)", re.I), "Clean Plan 32 flush strainer", 30),
    (re.compile(r"oil.*change every (\d+) hours", re.I), "Change bearing oil (ISO VG 68)", 180),
]


def _d(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def build(assets: list, docs: list, compliance: dict, today: date | None = None) -> dict:
    today = today or date.today()
    tasks = []

    def add(asset, task, due, source_kind, priority, docs_ref, reason):
        days = (due - today).days if due else None
        tasks.append({
            "asset": asset, "task": task,
            "due": due.isoformat() if due else None,
            "days_until": days, "source": source_kind, "priority": priority,
            "docs": docs_ref, "reason": reason,
        })

    for a in assets:
        tag = a["tag"]
        # 1. Condition-based interval from failure history (predictive)
        if a.get("mtbf_days"):
            last_ev = max((e["date"] for e in a["events"] if e["date"]), default=None)
            last = _d(last_ev) if last_ev else None
            if last:
                # schedule an inspection at 60% of MTBF since the last event
                interval = max(int(a["mtbf_days"] * 0.6), 30)
                due = last + timedelta(days=interval)
                add(tag, f"Condition inspection (predictive, {interval}d cycle)", due,
                    "predictive", "high" if a["health"] < 60 else "medium",
                    a["events"] and [a["events"][-1]["doc_id"]] or [],
                    f"MTBF {a['mtbf_days']}d from {a['corrective_count']} failures; act before next expected failure.")

        # 2. OEM-driven recurring tasks (from manual/handover text)
        knowledge = [d for d in docs if d.type in ("oem_manual", "memo") and tag in d.entities.get("equipment", {})]
        for kd in knowledge:
            for rx, task, interval in OEM_TASKS:
                if rx.search(kd.body):
                    due = today + timedelta(days=interval // 2)  # next occurrence
                    add(tag, task, due, "oem", "medium", [kd.id],
                        f"OEM/handover interval ({interval}d) for {tag}.")
                    break

    # 3. Statutory / compliance-driven tasks (hard due dates win priority)
    for f in compliance["findings"]:
        if f["status"] in ("gap", "due_soon") and f["equipment"]:
            due = None
            m = re.search(r"(\d{4}-\d{2}-\d{2})", f["detail"])
            if m:
                due = _d(m.group(1))
            for tag in f["equipment"]:
                add(tag, f["title"], due, "statutory",
                    "critical" if f["status"] == "gap" else "high",
                    f["evidence"], f"{f['standard']}: {f['detail']}")

    # De-duplicate identical (asset, task) keeping the earliest due
    seen = {}
    for t in tasks:
        key = (t["asset"], t["task"])
        if key not in seen or (t["days_until"] is not None and
                               (seen[key]["days_until"] is None or t["days_until"] < seen[key]["days_until"])):
            seen[key] = t
    tasks = list(seen.values())

    prio = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    # Optimisation objective: overdue/critical first, then soonest due
    tasks.sort(key=lambda t: (prio.get(t["priority"], 3),
                              t["days_until"] if t["days_until"] is not None else 9999))
    overdue = [t for t in tasks if t["days_until"] is not None and t["days_until"] < 0]
    next_30 = [t for t in tasks if t["days_until"] is not None and 0 <= t["days_until"] <= 30]
    logger.info("PM schedule built: %d tasks, %d overdue, %d due within 30 days", len(tasks), len(overdue), len(next_30))
    return {
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "overdue": len(overdue),
            "next_30_days": len(next_30),
            "by_source": {s: len([t for t in tasks if t["source"] == s])
                          for s in ("statutory", "predictive", "oem")},
        },
    }
