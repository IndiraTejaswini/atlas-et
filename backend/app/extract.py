"""Entity extraction for industrial documents.

Deterministic, rule-based extraction tuned for plant documentation:
equipment tags, regulatory references, document cross-references,
personnel, failure modes, and process parameters.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

# Case-insensitive + trailing lookahead (not \b) so tags survive both
# reformatting ("p-101a") and OCR artifacts that run words together
# ("P-101ACrude Charge Pump" still yields P-101A). Matched text is
# canonicalised to uppercase below so "P-101A" and "p-101a" resolve to the
# same graph node instead of becoming two disconnected ones — the most
# common real-world "reformatted tag" case. This does not catch genuine
# typos (e.g. "P-1O1A" with a letter O) — that needs fuzzy/similarity
# matching, a different and larger feature, not attempted here.
EQUIPMENT_RE = re.compile(r"\b(?:PSV|MOV|TK|CML|HX|[PEVCKI])-\d{2,4}[A-Z]?(?![\d-])", re.I)
DOCREF_RE = re.compile(r"\b(?:WO|INC|NM|SOP|INSP|DWG|EML|DS)-[A-Z0-9][\w-]*\d\b", re.I)
PARAM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:barg|bar\b|°C|mm/s|RPM|kW|m3/hr|m3\b|mm\b|micron|ppm|hr\b|hours)"
)

STANDARD_PATTERNS = [
    (re.compile(r"\bOISD-STD-(\d+)\b", re.I), lambda m: f"OISD-STD-{m.group(1)}"),
    (re.compile(r"\bOISD-GDN-(\d+)\b", re.I), lambda m: f"OISD-GDN-{m.group(1)}"),
    (re.compile(r"\bAPI\s?(610|Plan\s?\d+)\b", re.I), lambda m: f"API {m.group(1)}"),
    (re.compile(r"\bISO\s?(10816|VG\s?68)\b", re.I), lambda m: f"ISO {m.group(1)}"),
    (re.compile(r"\bSection\s(31|36)\b", re.I), lambda m: f"Factories Act Sec {m.group(1)}"),
    (re.compile(r"\bFactories Act\b", re.I), lambda m: "Factories Act 1948"),
    (re.compile(r"\bPESO\b", re.I), lambda m: "PESO Petroleum Rules"),
    (re.compile(r"\bHazardous Waste Rules \d{4}\b", re.I), lambda m: m.group(0)),
]

# Person names in "Initial. Surname" form — the shape every author/
# approver field in this corpus actually uses ("R. Sharma", "M. Khan", the
# "Technician:"/"Approved by:" lines). This used to be a fixed list of the
# six names that happen to appear in the seed corpus, which meant a
# document naming anyone else produced zero person entities — a real
# generalisation gap. A statistical NER model was rejected for the same
# reason as equipment/doc-id extraction (ARCHITECTURE.md §8: 0 GPU, 0
# training data, fully auditable); this is that same trade-off applied to
# the *pattern* a name follows rather than an enumerated instance list.
# Deliberately narrow (won't catch "John Smith" with no initial, or
# multi-word surnames) — broadening risks false positives on abbreviations
# ("Fig. 6" doesn't match because "Fig" isn't a single letter; "U.S." does
# match today, a real remaining edge case with no local instance of it).
# The (?<![°\d]) guard is load-bearing, not speculative: "design 28 barg @
# 240 °C. Insulated, hot service." genuinely matched "C. Insulated" as a
# person before this was added — a temperature unit ending a sentence,
# immediately followed by a capitalised new sentence, is indistinguishable
# from "C. Surname" without it. Found by checking this pattern's actual
# output against the real corpus, not assumed safe from the regex alone.
PERSON_RE = re.compile(r"(?<![°\d])\b[A-Z]\.\s?[A-Z][a-z]+\b")

FAILURE_MODE_LEXICON = [
    (re.compile(r"mechanical seal failure|seal failure|seal face|seal vapor leak|seal gland", re.I),
     "Mechanical seal failure"),
    (re.compile(r"bearing failure|bearing distress|spalling|bearing housing", re.I), "Bearing failure"),
    (re.compile(r"\bcavitation\b", re.I), "Cavitation"),
    (re.compile(r"corrosion under insulation|\bCUI\b", re.I), "Corrosion under insulation"),
    (re.compile(r"\bfouling\b|asphaltene", re.I), "Fouling"),
    (re.compile(r"\bwax(?:y|ing|ed)?\b", re.I), "Wax blockage"),
    (re.compile(r"\bvibration\b", re.I), "High vibration"),
    (re.compile(r"\berosion\b", re.I), "Erosion"),
    (re.compile(r"overheat(?:ing|ed)|heat checking", re.I), "Overheating"),
]

# Known document ids that don't match the generic doc-ref pattern (their
# prefix — OEM, MEMO, REG — isn't one DOCREF_RE recognises). Checked
# unconditionally, zero-context or not, as a small built-in floor; when a
# caller *does* have corpus context (see `known_doc_ids` below), that
# mechanism generalises this same idea to every actual document in the
# corpus instead of just these six.
SPECIAL_DOC_IDS = ["OEM-SLZ-OHH", "MEMO-HND-01", "REG-IDX-01", "DWG-300-001", "EML-0124", "DS-P101"]


def _count_literal_ci(text: str, needle: str) -> int:
    """Case-insensitive, word-bounded count of a literal string — used for
    doc ids whose shape isn't covered by DOCREF_RE's prefix pattern."""
    if not needle:
        return 0
    return len(re.findall(r"\b" + re.escape(needle) + r"\b", text, re.I))


def extract_entities(text: str, known_doc_ids: Iterable[str] | None = None) -> dict:
    """Return {type: Counter(canonical_name -> mention count)}.

    `known_doc_ids`, when given, is the full set of ids actually present in
    the corpus (or, for a single upload, the corpus it's about to join) —
    every one of them is matched as a literal (case-insensitive) substring,
    so a document referencing another by name links correctly even when its
    id doesn't fit DOCREF_RE's prefix-based pattern. This replaces having to
    special-case a fixed list for every corpus this runs against; callers
    with no corpus context (e.g. graph.py's short cause-clause parsing) pass
    nothing and fall back to SPECIAL_DOC_IDS alone, same as before.
    """
    out = {
        "equipment": Counter(),
        "standard": Counter(),
        "docref": Counter(),
        "person": Counter(),
        "failure_mode": Counter(),
        "parameter": Counter(),
    }
    for m in EQUIPMENT_RE.finditer(text):
        out["equipment"][m.group(0).upper()] += 1
    for pattern, canon in STANDARD_PATTERNS:
        for m in pattern.finditer(text):
            out["standard"][canon(m)] += 1
    for m in DOCREF_RE.finditer(text):
        out["docref"][m.group(0).upper()] += 1
    for special in SPECIAL_DOC_IDS:
        n = _count_literal_ci(text, special)
        if n:
            out["docref"][special] += n
    if known_doc_ids:
        for doc_id in known_doc_ids:
            n = _count_literal_ci(text, doc_id)
            if n:
                out["docref"][doc_id.upper()] += n
    for m in PERSON_RE.finditer(text):
        out["person"][m.group(0)] += 1
    for pattern, canon in FAILURE_MODE_LEXICON:
        n = len(pattern.findall(text))
        if n:
            out["failure_mode"][canon] += n
    for m in PARAM_RE.finditer(text):
        out["parameter"][m.group(0).strip()] += 1
    return out


def merge_entities(a: dict, b: dict) -> dict:
    for k, counter in b.items():
        a.setdefault(k, Counter()).update(counter)
    return a
