"""Industrial ontology layer — ISO 14224 taxonomy + ISA-95 hierarchy.

Turns ATLAS's pragmatic entity/relation schema into a formal industrial
ontology so the knowledge graph speaks the language maintenance and reliability
engineers already use:

- **ISO 14224** (Petroleum & gas — collection of reliability/maintenance data)
  supplies the equipment taxonomy (class → type → subunit) and the standard
  failure-mode codes, so failures are comparable across sites and vendors.
- **ISA-95 / IEC 62264** supplies the physical location hierarchy
  (Enterprise → Site → Area → Process Cell/Unit → Equipment).

Every equipment tag in the corpus is classified into both, which is what makes
cross-plant benchmarking and standards-based reporting possible.
"""
from __future__ import annotations

import re

# --- ISO 14224 equipment taxonomy -------------------------------------------
# tag prefix → (equipment class, ISO 14224 class code, equipment type, typical subunits)
ISO14224_CLASSES = {
    "P": ("Pumps", "PU", "Centrifugal pump",
          ["Power transmission", "Pump unit", "Control and monitoring", "Lubrication system", "Seal system"]),
    "E": ("Heat exchangers", "HE", "Shell-and-tube exchanger",
          ["Tube bundle", "Shell", "Channel/head", "Internals"]),
    "V": ("Vessels", "VE", "Pressure vessel",
          ["Shell", "Internals", "Nozzles", "Support"]),
    "C": ("Columns", "CO", "Distillation column",
          ["Shell", "Trays/packing", "Internals", "Nozzles"]),
    "TK": ("Tanks", "TA", "Atmospheric storage tank",
           ["Shell", "Roof", "Bottom", "Appurtenances"]),
    "PSV": ("Safety valves", "SV", "Pressure relief valve",
            ["Valve body", "Spring/bellows", "Trim", "Pilot"]),
    "MOV": ("Valves", "VA", "Motor-operated valve",
            ["Valve body", "Actuator", "Trim", "Control"]),
}

# --- ISO 14224 failure-mode codes (Table B.6 style) --------------------------
ISO14224_FAILURE_MODES = {
    "Mechanical seal failure": ("ELP", "External leakage – process medium"),
    "Bearing failure":         ("VIB", "Vibration"),
    "High vibration":          ("VIB", "Vibration"),
    "Cavitation":              ("INL", "Internal leakage"),
    "Fouling":                 ("PDE", "Performance degradation"),
    "Wax blockage":            ("PLU", "Plugged / choked"),
    "Corrosion under insulation": ("ELU", "External leakage – utility medium"),
    "Overheating":             ("OHE", "Overheating"),
    "Erosion":                 ("PDE", "Performance degradation"),
}

# --- ISA-95 physical hierarchy ----------------------------------------------
ISA95 = {
    "enterprise": "Refinery Operations",
    "site": "Refinery — Western Region",
    "area": "Crude & Vacuum",
    "unit": "Unit 300 — Crude Distillation",
}

_PREFIX_RE = re.compile(r"^(PSV|MOV|TK|CML|HX|[PEVCKI])-")


def classify_tag(tag: str) -> dict | None:
    m = _PREFIX_RE.match(tag)
    if not m:
        return None
    prefix = m.group(1)
    entry = ISO14224_CLASSES.get(prefix)
    if not entry:
        return None
    cls, code, etype, subunits = entry
    return {
        "tag": tag,
        "iso14224": {"class": cls, "class_code": code, "type": etype, "subunits": subunits},
        "isa95": {**ISA95, "equipment": tag,
                  "path": f"{ISA95['enterprise']} / {ISA95['site']} / {ISA95['area']} / {ISA95['unit']} / {tag}"},
    }


def classify_failure_mode(mode: str) -> dict | None:
    entry = ISO14224_FAILURE_MODES.get(mode)
    if not entry:
        return None
    code, label = entry
    return {"mode": mode, "iso14224_code": code, "iso14224_label": label}


def build(docs: list, graph) -> dict:
    """Classify every equipment tag and failure mode found in the corpus."""
    tags, modes = set(), set()
    for d in docs:
        tags |= set(d.entities.get("equipment", {}))
        modes |= set(d.entities.get("failure_mode", {}))

    equipment = [c for c in (classify_tag(t) for t in sorted(tags)) if c]
    failure_modes = [c for c in (classify_failure_mode(m) for m in sorted(modes)) if c]

    by_class: dict[str, list[str]] = {}
    for e in equipment:
        by_class.setdefault(e["iso14224"]["class"], []).append(e["tag"])

    unclassified = sorted(t for t in tags if not classify_tag(t))
    return {
        "standards": [
            {"id": "ISO 14224", "role": "Equipment taxonomy & failure-mode coding",
             "note": "Petroleum, petrochemical and natural gas industries — collection and exchange of reliability and maintenance data."},
            {"id": "ISA-95 / IEC 62264", "role": "Physical equipment hierarchy",
             "note": "Enterprise–Control System Integration: Enterprise → Site → Area → Unit → Equipment."},
        ],
        "isa95": ISA95,
        "equipment": equipment,
        "equipment_by_class": by_class,
        "failure_modes": failure_modes,
        "unclassified_tags": unclassified,
        "coverage": {
            "tags_total": len(tags),
            "tags_classified": len(equipment),
            "modes_total": len(modes),
            "modes_classified": len(failure_modes),
            "pct_tags": round(100 * len(equipment) / len(tags)) if tags else 0,
            "pct_modes": round(100 * len(failure_modes) / len(modes)) if modes else 0,
        },
        "schema": {
            "node_types": ["document", "equipment", "standard", "failure_mode", "person"],
            "relation_types": [
                "mentions", "cites", "involves", "describes", "references", "exhibits",
                "connected_to",          # P&ID-digitised equipment topology (vision.py -> graph.py)
                "caused_by",             # failure_mode -> failure_mode, from "root cause / due to" clauses
                "root_cause_condition",  # failure_mode -> equipment, from the same clauses
            ],
        },
    }
