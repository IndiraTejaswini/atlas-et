"""Compliance engine: checks must be driven by document type/content shape,
not by literal document ids — this is what lets the same checks work on a
corpus with completely different document ids.
"""
import copy
from datetime import date

from app import compliance


def test_finds_overdue_psv_from_register_table(corpus_docs):
    result = compliance.evaluate(corpus_docs, today=date(2026, 7, 20))
    psv_gaps = [f for f in result["findings"] if f["id"] == "psv-PSV-1104"]
    assert len(psv_gaps) == 1
    assert psv_gaps[0]["status"] == "gap"
    assert "INSP-102" in psv_gaps[0]["evidence"]


def test_score_and_counts_are_internally_consistent(corpus_docs):
    result = compliance.evaluate(corpus_docs, today=date(2026, 7, 20))
    assert sum(result["counts"].values()) == result["total_checks"]
    assert 0 <= result["score"] <= 100


def test_every_finding_carries_evidence(corpus_docs):
    result = compliance.evaluate(corpus_docs, today=date(2026, 7, 20))
    for f in result["findings"]:
        assert f["evidence"], f"finding {f['id']} has no evidence documents"


def test_checks_are_id_independent_not_hardcoded(corpus_docs):
    """The regression test for the doc-ID-binding fix: rename every document
    id in the corpus (and fix up cross-references in the bodies) and confirm
    the same checks still fire. Under the old by_id.get("INSP-102")-style
    implementation this would silently collapse to just the 3 unconditional
    no-evidence stubs."""
    renamed = copy.deepcopy(corpus_docs)
    rename_map = {d.id: f"PLANT2-DOC-{i:03d}" for i, d in enumerate(renamed)}
    for d in renamed:
        d.id = rename_map[d.id]
    for d in renamed:
        for old, new in rename_map.items():
            d.body = d.body.replace(old, new)

    original = compliance.evaluate(corpus_docs, today=date(2026, 7, 20))
    renamed_result = compliance.evaluate(renamed, today=date(2026, 7, 20))

    assert renamed_result["total_checks"] == original["total_checks"]
    assert renamed_result["counts"] == original["counts"]
    assert renamed_result["score"] == original["score"]
    # and it must not have degenerated to only the always-on no-evidence stubs
    assert renamed_result["counts"]["gap"] >= 5


def test_no_evidence_requirement_not_silently_dropped(corpus_docs):
    """Regression test for a specific bug found while generalizing this
    module: an early version suppressed the OISD-STD-105 'quarterly permit
    audit' requirement because OISD-STD-105 is *also* the standard for the
    separately-evidenced 3-yearly SOP review — collapsing on standard code
    alone hid a real, distinct, unevidenced requirement."""
    result = compliance.evaluate(corpus_docs, today=date(2026, 7, 20))
    no_evidence_standards = [f["standard"] for f in result["findings"] if f["status"] == "no_evidence"]
    assert any("OISD-STD-105" in s for s in no_evidence_standards)
