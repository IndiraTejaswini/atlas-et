"""End-to-end equivalence at the State orchestration layer (main.py): a
corpus built by starting from an empty State and calling add_document()
once per document must match a State that loaded the same final documents
via a single rebuild() — this is what a live series of /api/ingest calls
actually exercises, one level up from the graph.py/search.py unit tests in
test_incremental.py.
"""
import copy

from app.main import State


def _edge_set(graph):
    return {(a, b, rel, frozenset(e["docs"])) for (a, b, rel), e in graph.edges.items()}


def test_state_seeded_then_incrementally_extended_matches_full_rebuild_of_the_same_set(corpus_docs):
    """The property that actually matters in production: startup() always
    loads the *whole* initial corpus in one rebuild() (correctly resolving
    every cross-reference among those documents via load_corpus()'s two-
    pass known-ids collection — see ingest.py), and only *single new*
    documents go through add_document() afterward, one at a time, onto
    that already-complete base. That's the scenario this test reproduces:
    seed with most of the corpus via rebuild(), then add the rest one at a
    time via add_document(), and compare against a full rebuild of the
    combined set."""
    docs = copy.deepcopy(corpus_docs)
    seed, rest = docs[:12], docs[12:]

    rebuilt = State()
    rebuilt.rebuild(docs)

    incremental = State()
    incremental.rebuild(seed)
    for d in rest:
        incremental.add_document(d)

    assert len(incremental.docs) == len(rebuilt.docs)
    assert incremental.graph.nodes.keys() == rebuilt.graph.nodes.keys()
    assert _edge_set(incremental.graph) == _edge_set(rebuilt.graph)
    assert len(incremental.index.chunks) == len(rebuilt.index.chunks)
    assert incremental.compliance["score"] == rebuilt.compliance["score"]
    assert incremental.compliance["counts"] == rebuilt.compliance["counts"]
    assert {a["tag"] for a in incremental.assets} == {a["tag"] for a in rebuilt.assets}


def test_backreference_fix_makes_even_the_adversarial_empty_start_case_exact(corpus_docs):
    """The harder scenario than the test above, and not one production
    actually needs (startup() always seeds the initial corpus via a single
    rebuild()) — building an ENTIRE corpus from empty by calling
    add_document() once per document, in whatever order load_corpus()
    happened to read the files. This is the case that originally exposed a
    real bug: an early document (e.g. an inspection report) can reference a
    document ingested later (e.g. the work order it's about) by id, and a
    naive "known_ids = documents seen so far" incremental design drops
    that edge forever, because the referenced id wasn't known yet at the
    time the referencing document was processed — proven by running
    exactly this and diffing against a full rebuild, which is how the gap
    was first found here, not assumed away.

    add_document()'s `existing_docs` back-reference check (graph.py) closes
    it completely, not just for the realistic seeded case: for every new
    document, it also checks already-added documents' own (already-
    extracted, not re-scanned) docref entities for a mention of the new
    document's id, and retroactively adds that edge. The two graphs come
    out with zero edge difference even in this adversarial ordering —
    verified below, not just claimed.
    """
    docs = copy.deepcopy(corpus_docs)

    rebuilt = State()
    rebuilt.rebuild(docs)

    incremental = State()
    incremental.rebuild([])
    for d in docs:
        incremental.add_document(d)

    assert _edge_set(incremental.graph) == _edge_set(rebuilt.graph)
    assert incremental.graph.nodes.keys() == rebuilt.graph.nodes.keys()


def test_incremental_add_bumps_generation_and_clears_cache():
    state = State()
    state.rebuild([])
    state.cached("k", lambda: "first")
    gen_before = state.generation

    from app.ingest import load_document
    doc = load_document({"id": "WO-GEN-TEST", "type": "work_order"}, "body text", fallback_id="WO-GEN-TEST")
    state.add_document(doc)

    assert state.generation == gen_before + 1
    assert state.cached("k", lambda: "second") == "second"  # not the stale cached "first"


def test_incremental_add_does_not_mutate_a_previously_returned_graph_reference(corpus_docs):
    """The exact property that motivated copy()-then-swap: code that grabbed
    a reference to state.graph *before* an ingest must keep seeing the
    graph as it was at that moment, not a graph that changed underneath it."""
    docs = copy.deepcopy(corpus_docs)
    state = State()
    state.rebuild(docs[:5])
    snapshot = state.graph
    node_count_before = len(snapshot.nodes)

    from app.ingest import load_document
    new_doc = load_document(
        {"id": "WO-SNAPSHOT-TEST", "type": "work_order", "equipment": "TK-999"},
        "A new tank TK-999 work order.", fallback_id="WO-SNAPSHOT-TEST",
    )
    state.add_document(new_doc)

    assert len(snapshot.nodes) == node_count_before  # untouched
    assert state.graph is not snapshot               # a new object was swapped in
    assert len(state.graph.nodes) > node_count_before
