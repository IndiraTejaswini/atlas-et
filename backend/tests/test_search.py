"""Hybrid retrieval — metadata filtering (search.py: HybridIndex.query).

Uses the real 18-document seed corpus (via the built_index/corpus_docs
fixtures in conftest.py) so filter behaviour is checked against actual
document types and dates, not a synthetic stand-in.
"""


def test_doc_type_filter_only_returns_matching_documents(built_index, corpus_docs):
    by_id = {d.id: d for d in corpus_docs}
    result = built_index.query("pump seal flush", top_k=8, doc_types={"work_order"})
    returned_types = {by_id[h["chunk"].doc_id].type for h in result["hits"]}
    assert returned_types <= {"work_order"}
    assert result["hits"], "expected at least one work_order hit for this query"


def test_doc_type_filter_excludes_a_type_present_in_unfiltered_results(built_index):
    unfiltered = built_index.query("pump seal flush", top_k=8)
    unfiltered_types = {h["chunk"].doc_id[:2] for h in unfiltered["hits"]}
    assert unfiltered_types  # sanity: the unfiltered query actually returns something

    filtered = built_index.query("pump seal flush", top_k=8, doc_types={"regulatory"})
    # OEM manuals / work orders that normally answer this query are excluded
    assert all(h["chunk"].doc_id != "OEM-SLZ-OHH" for h in filtered["hits"])


def test_date_range_filter_excludes_documents_outside_range(built_index, corpus_docs):
    by_id = {d.id: d for d in corpus_docs}
    result = built_index.query("crude slate change seal failure", top_k=10,
                               date_from="2025-01-01", date_to="2025-12-31")
    for h in result["hits"]:
        doc = by_id[h["chunk"].doc_id]
        assert doc.date and "2025-01-01" <= doc.date <= "2025-12-31"


def test_date_range_filter_can_produce_empty_results_honestly(built_index):
    # A range with nothing in it must return no hits, not silently ignore
    # the filter and return unfiltered results.
    result = built_index.query("pump seal failure", top_k=8, date_from="1999-01-01", date_to="1999-12-31")
    assert result["hits"] == []


def test_no_filter_args_behaves_exactly_as_before(built_index):
    a = built_index.query("Why does P-101A keep failing?", top_k=5)
    b = built_index.query("Why does P-101A keep failing?", top_k=5, doc_types=None, date_from=None, date_to=None)
    a_ids = [h["chunk"].doc_id for h in a["hits"]]
    b_ids = [h["chunk"].doc_id for h in b["hits"]]
    assert a_ids == b_ids


def test_combined_type_and_date_filter(built_index, corpus_docs):
    by_id = {d.id: d for d in corpus_docs}
    result = built_index.query("pump bearing vibration", top_k=8,
                               doc_types={"work_order"}, date_from="2024-01-01", date_to="2025-12-31")
    for h in result["hits"]:
        doc = by_id[h["chunk"].doc_id]
        assert doc.type == "work_order"
        assert "2024-01-01" <= doc.date <= "2025-12-31"


def test_graph_expansion_respects_the_filter(built_index):
    # Without a filter, "Why does P-101A keep failing?" pulls in the OEM
    # manual via graph expansion (shared failure mode). Restricting to
    # work_order only must exclude it even though the graph would
    # otherwise surface it.
    result = built_index.query("Why does P-101A keep failing?", top_k=8, doc_types={"work_order"})
    assert all(h["chunk"].doc_id != "OEM-SLZ-OHH" for h in result["hits"])
