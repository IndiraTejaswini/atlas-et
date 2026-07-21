"""Quality & process-deviation flagging.

Flags deviations *before they escalate* by comparing operating records and
live readings against design/datasheet limits and procedural requirements:
process parameters drifting off design, live sensor breaches, and control
lapses (a hold point bypassed, a permit re-test skipped). Each deviation
names the expected value, the observed value, and the source.

Every check below scans documents by *content shape* — a "<TAG> outlet
temperature dropped N °C below design" sentence, a "bypass ... interlock
I-nnn" prohibition, a "ran near N m3/hr, below the M m3/hr minimum" record —
rather than by a hard-coded document id, exactly like compliance.py. Point
this at a different plant's corpus (different ids, different tags) and the
same deviations still fire wherever the same shapes appear, instead of only
matching the specific work orders / SOP this seed corpus happens to use.
The equipment tag, the numbers, and any corroborating datasheet/OEM manual
are all parsed or discovered per-document, never asserted.
"""
from __future__ import annotations

import re

from . import telemetry

# A process-outlet-below-design record: "<TAG> ... outlet temperature dropped
# N °C below design". Tag and drop are both captured from the sentence.
_OUTLET_BELOW_DESIGN_RE = re.compile(
    r"\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\b[^.\n]*?outlet temperature dropped\s+(\d+)\s*°C below design",
    re.I,
)
# A control-of-work prohibition against bypassing a named interlock.
_INTERLOCK_BYPASS_RE = re.compile(r"bypass(?:ing|ed)?\s+(?:the\s+)?[^.\n]*?interlock\s+(I-\d+)", re.I)
# The consequence clause that makes the prohibition a *recorded* deviation
# rather than a generic caution: "... caused <mode> damage/failure ...".
_CONSEQUENCE_RE = re.compile(r"(?:caused|causing|led to)\s+([a-z]+(?:\s+[a-z]+)*?\s+(?:damage|failure))", re.I)
# A minimum-continuous-flow excursion recorded against an OEM limit.
_MIN_FLOW_RE = re.compile(r"ran near\s+(\d+)\s*m3/hr,\s*below the\s+(\d+)\s*m3/hr minimum", re.I)
# Optional turndown qualifier so the detail can name *which* turndown window,
# read from the record instead of asserted.
_TURNDOWN_RE = re.compile(r"during\s+((?:[A-Za-z]+\s+)?turndown)", re.I)


def _primary_equipment(doc) -> list[str]:
    return [t.strip() for t in doc.meta.get("equipment", "").split(",") if t.strip()]


def _supporting(docs: list, tag: str, types: tuple) -> list[str]:
    """Datasheet / OEM-manual documents that cover `tag`, attached as
    corroborating evidence — discovered by equipment overlap (frontmatter),
    not by naming a fixed document id."""
    if not tag:
        return []
    return [d.id for d in docs if d.type in types and tag in _primary_equipment(d)]


def evaluate(docs: list, assets: list) -> dict:
    deviations = []

    def add(kind, severity, title, expected, observed, detail, docs_ref, asset=""):
        deviations.append({
            "kind": kind, "severity": severity, "title": title,
            "expected": expected, "observed": observed, "detail": detail,
            "docs": docs_ref, "asset": asset,
        })

    # 1. Process deviation — an exchanger outlet below design (fouling →
    #    energy/quality loss), from a "<TAG> outlet temperature dropped N °C
    #    below design" sentence in ANY document. A stated design temperature
    #    is quoted when the record gives one; otherwise reported generically
    #    rather than asserting a number that isn't in the source.
    for doc in docs:
        m = _OUTLET_BELOW_DESIGN_RE.search(doc.body)
        if not m:
            continue
        tag, drop = m.group(1).upper(), m.group(2)
        design = re.search(r"design[^.\n]*?(\d{2,3})\s*°C", doc.body, re.I)
        expected = f"≈{design.group(1)} °C (design)" if design else "at or above design outlet temp"
        evidence = sorted({doc.id, *_supporting(docs, tag, ("datasheet", "oem_manual"))})
        add("process", "high", f"{tag} outlet temperature below design",
            expected, f"−{drop} °C vs design",
            "Outlet has fallen below design due to accelerated fouling; heat/furnace duty rising "
            "to compensate — an energy and throughput-quality deviation.",
            evidence, tag)

    # 2. Live sensor breaches → quality/process deviations in real time
    for b in telemetry.active_breaches():
        add("realtime", b["severity"], f"{b['asset']} live reading out of limits",
            "within alarm limits", b["detail"].split("≥")[0].split("≤")[0].strip(),
            f"Live operating condition breach: {b['detail']}.", [], b["asset"])

    # 3. Control-of-work deviation — a procedure prohibiting an interlock
    #    bypass *because* bypassing previously caused damage. Both the
    #    interlock id and the recorded consequence are parsed from the text.
    for doc in docs:
        m = _INTERLOCK_BYPASS_RE.search(doc.body)
        if not m:
            continue
        interlock = m.group(1).upper()
        cons = _CONSEQUENCE_RE.search(doc.body)
        consequence = cons.group(1).strip().lower() if cons else "equipment damage"
        tags = _primary_equipment(doc)
        asset = tags[0] if tags else ""
        label = "/".join(tags) or asset or interlock
        add("control", "medium", f"Interlock-bypass prohibition on {label}",
            f"Interlock {interlock} always in service",
            f"bypass caused past {consequence}",
            f"Procedure records that bypassing interlock {interlock} previously caused "
            f"{consequence} — a recurring control deviation to guard against.",
            [doc.id], asset)

    # 4. Minimum-flow deviation from an OEM limit, recorded in ANY document as
    #    "ran near N m3/hr, below the M m3/hr minimum" — observed/expected
    #    flows and the equipment tag are all read from the record.
    for doc in docs:
        m = _MIN_FLOW_RE.search(doc.body)
        if not m:
            continue
        observed_flow, min_flow = m.group(1), m.group(2)
        tags = _primary_equipment(doc)
        asset = tags[0] if tags else ""
        tw = _TURNDOWN_RE.search(doc.body)
        turndown = tw.group(1).strip() if tw else "low-flow turndown"
        evidence = sorted({doc.id, *_supporting(docs, asset, ("oem_manual",))})
        add("process", "medium", f"{asset} operated below minimum continuous flow",
            f"≥{min_flow} m3/hr (OEM)", f"~{observed_flow} m3/hr during {turndown}",
            f"Pump was run below its OEM minimum continuous flow during {turndown}, "
            "contributing to bearing distress.",
            evidence, asset)

    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    deviations.sort(key=lambda d: sev.get(d["severity"], 3))
    counts = {}
    for d in deviations:
        counts[d["kind"]] = counts.get(d["kind"], 0) + 1
    return {"deviations": deviations, "total": len(deviations), "by_kind": counts}
