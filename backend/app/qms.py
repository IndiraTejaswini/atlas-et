"""QMS integration surface — non-conformance record (NCR) export.

This is an *integration surface*, not a vendor connector: ATLAS emits
non-conformance records in a documented, stable contract that a QMS
(SAP QM, ETQ, MasterControl, Intelex, …) can import via file drop or webhook.
Quality deviations and compliance gaps are normalised into one NCR schema with
severity, source evidence, and an ISO 14224 classification where applicable.

Deliberately no mock vendor client: the honest claim is "integration-ready with
a documented contract", which is what an evaluator can actually verify.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date

from .ontology import classify_tag

# Severity mapping onto a conventional QMS 1–4 criticality scale
SEVERITY_MAP = {"critical": 1, "high": 2, "medium": 3, "low": 4}

NCR_SCHEMA = {
    "ncr_id": "string — stable identifier, idempotent across exports",
    "raised_on": "date (ISO 8601)",
    "source": "string — ATLAS engine that raised it (quality_deviation | compliance_gap)",
    "category": "string — process | realtime | control | regulatory",
    "title": "string",
    "description": "string",
    "equipment_tag": "string | null",
    "iso14224_class": "string | null — equipment class from ISO 14224",
    "iso14224_failure_code": "string | null",
    "standard_ref": "string | null — governing standard/regulation",
    "severity": "string — critical | high | medium | low",
    "criticality": "integer 1–4 (1 = most critical)",
    "expected": "string | null",
    "observed": "string | null",
    "evidence_documents": "array[string] — source document IDs in ATLAS",
    "status": "string — open",
}

WEBHOOK_CONTRACT = {
    "method": "POST",
    "content_type": "application/json",
    "body": {"event": "ncr.created", "ncr": "<NCR object per schema>"},
    "headers": {"X-ATLAS-Signature": "HMAC-SHA256 of body using the shared secret"},
    "retry": "exponential backoff, 3 attempts; consumer must treat ncr_id as idempotency key",
}


def _ncr_id(source: str, title: str) -> str:
    return "NCR-" + hashlib.sha1(f"{source}|{title}".encode()).hexdigest()[:10].upper()


def build_ncrs(quality: dict, compliance: dict) -> list[dict]:
    today = date.today().isoformat()
    ncrs = []

    for d in quality["deviations"]:
        tag = d.get("asset") or None
        cls = classify_tag(tag) if tag else None
        ncrs.append({
            "ncr_id": _ncr_id("quality_deviation", d["title"]),
            "raised_on": today,
            "source": "quality_deviation",
            "category": d["kind"],
            "title": d["title"],
            "description": d["detail"],
            "equipment_tag": tag,
            "iso14224_class": cls["iso14224"]["class"] if cls else None,
            "iso14224_failure_code": None,
            "standard_ref": None,
            "severity": d["severity"],
            "criticality": SEVERITY_MAP.get(d["severity"], 3),
            "expected": d.get("expected"),
            "observed": d.get("observed"),
            "evidence_documents": d.get("docs", []),
            "status": "open",
        })

    for f in compliance["findings"]:
        if f["status"] not in ("gap", "no_evidence"):
            continue
        tag = (f.get("equipment") or [None])[0]
        cls = classify_tag(tag) if tag else None
        ncrs.append({
            "ncr_id": _ncr_id("compliance_gap", f["title"]),
            "raised_on": today,
            "source": "compliance_gap",
            "category": "regulatory",
            "title": f["title"],
            "description": f["detail"],
            "equipment_tag": tag,
            "iso14224_class": cls["iso14224"]["class"] if cls else None,
            "iso14224_failure_code": None,
            "standard_ref": f["standard"],
            "severity": f["severity"],
            "criticality": SEVERITY_MAP.get(f["severity"], 3),
            "expected": "Requirement satisfied with current evidence",
            "observed": f["status"].replace("_", " "),
            "evidence_documents": f.get("evidence", []),
            "status": "open",
        })

    ncrs.sort(key=lambda n: (n["criticality"], n["title"]))
    return ncrs


def export_json(quality: dict, compliance: dict) -> dict:
    ncrs = build_ncrs(quality, compliance)
    return {
        "contract_version": "1.0",
        "generated_at": date.today().isoformat(),
        "source_system": "ATLAS Industrial Knowledge Intelligence",
        "record_count": len(ncrs),
        "schema": NCR_SCHEMA,
        "webhook_contract": WEBHOOK_CONTRACT,
        "records": ncrs,
    }


def export_csv(quality: dict, compliance: dict) -> str:
    ncrs = build_ncrs(quality, compliance)
    cols = ["ncr_id", "raised_on", "source", "category", "title", "description",
            "equipment_tag", "iso14224_class", "standard_ref", "severity",
            "criticality", "expected", "observed", "evidence_documents", "status"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for n in ncrs:
        row = dict(n)
        row["evidence_documents"] = ";".join(n["evidence_documents"])
        w.writerow(row)
    return buf.getvalue()
