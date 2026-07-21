"""Incremental indexing must produce the same graph and the same lexical
retrieval results as a full rebuild over the same final document set —
that equivalence is the whole safety argument for skipping re-processing
of documents that didn't change, so it's proven here directly rather than
just asserted in a docstring.

The semantic (LSA/FAISS) layer is the one deliberate exception: adding a
document incrementally projects it through the basis already fit on
earlier documents, while a full rebuild refits SVD over everyone at once —
those are genuinely different bases, so bit-identical semantic scores are
NOT expected or asserted here. What IS asserted for that layer is that it
keeps working (stays aligned, returns sane results) after incremental adds.
"""
import copy
from collections import Counter

from app.graph import KnowledgeGraph
from app.search import HybridIndex


def _edge_set(graph):
    return {
        (a, b, rel, frozenset(e["docs"]), e["count"])
        for (a, b, rel), e in graph.edges.items()
    }


def _node_snapshot(graph):
    return {nid: (n["type"], n["label"], n["weight"]) for nid, n in graph.nodes.items()}


class TestGraphIncrementalEquivalence:
    def test_incremental_add_produces_identical_nodes_to_full_build(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        known_ids = {d.id for d in docs}

        full = KnowledgeGraph()
        full.build(docs)

        incremental = KnowledgeGraph()
        for d in docs:
            incremental.add_document(d, known_ids)

        assert _node_snapshot(full) == _node_snapshot(incremental)

    def test_incremental_add_produces_identical_edges_to_full_build(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        known_ids = {d.id for d in docs}

        full = KnowledgeGraph()
        full.build(docs)

        incremental = KnowledgeGraph()
        for d in docs:
            incremental.add_document(d, known_ids)

        assert _edge_set(full) == _edge_set(incremental)

    def test_incremental_add_produces_identical_adjacency(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        known_ids = {d.id for d in docs}

        full = KnowledgeGraph()
        full.build(docs)
        incremental = KnowledgeGraph()
        for d in docs:
            incremental.add_document(d, known_ids)

        assert full.adj.keys() == incremental.adj.keys()
        for key in full.adj:
            assert full.adj[key] == incremental.adj[key]

    def test_order_of_incremental_adds_does_not_matter(self, corpus_docs):
        """A document that references another one added *later* must still
        link correctly, because known_ids is the full final set on every
        call, not just "ids seen so far"."""
        docs = copy.deepcopy(corpus_docs)
        known_ids = {d.id for d in docs}

        forward = KnowledgeGraph()
        for d in docs:
            forward.add_document(d, known_ids)

        reversed_graph = KnowledgeGraph()
        for d in reversed(docs):
            reversed_graph.add_document(d, known_ids)

        assert _edge_set(forward) == _edge_set(reversed_graph)


class TestHybridIndexIncrementalEquivalence:
    def test_incremental_lexical_stats_match_full_build(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        graph = KnowledgeGraph()
        graph.build(docs)

        full = HybridIndex()
        full.build(docs, graph, semantic=False)

        incremental = HybridIndex()
        incremental.build([], graph, semantic=False)
        for d in docs:
            incremental.add_document(d, graph)

        assert len(full.chunks) == len(incremental.chunks)
        assert full.doc_freq == incremental.doc_freq
        assert abs(full.avg_len - incremental.avg_len) < 1e-9
        assert full._idf.keys() == incremental._idf.keys()
        for term in full._idf:
            assert abs(full._idf[term] - incremental._idf[term]) < 1e-9

    def test_incremental_query_results_match_full_build_lexical_and_graph_only(self, corpus_docs):
        """The end-to-end check: with the semantic signal excluded (the one
        layer that's allowed to differ — see module docstring), a query
        against the incrementally-built index must return exactly the same
        ranked hits as the same query against a fully-rebuilt one."""
        docs = copy.deepcopy(corpus_docs)
        graph_full = KnowledgeGraph()
        graph_full.build(docs)
        full = HybridIndex()
        full.build(docs, graph_full, semantic=False)

        graph_inc = KnowledgeGraph()
        incremental = HybridIndex()
        incremental.build([], graph_inc, semantic=False)
        known_ids = {d.id for d in docs}
        for d in docs:
            graph_inc.add_document(d, known_ids)
            incremental.add_document(d, graph_inc)

        queries = [
            "Why does P-101A keep failing?",
            "Which relief valves are overdue for testing?",
            "confined space entry requirements",
            "crude slate change",
        ]
        for q in queries:
            r_full = full.query(q, top_k=8, use_semantic=False)
            r_inc = incremental.query(q, top_k=8, use_semantic=False)
            ids_full = [h["chunk"].id for h in r_full["hits"]]
            ids_inc = [h["chunk"].id for h in r_inc["hits"]]
            assert ids_full == ids_inc, f"mismatch for query {q!r}: {ids_full} != {ids_inc}"

    def test_incremental_semantic_layer_stays_functional_after_adds(self, corpus_docs):
        """Not equivalence (see module docstring) — just that the semantic
        signal keeps returning sane, aligned results after incremental
        adds, rather than crashing or silently going stale."""
        docs = copy.deepcopy(corpus_docs)
        graph = KnowledgeGraph()
        index = HybridIndex()
        index.build([], graph, semantic=True)
        known_ids = {d.id for d in docs}
        for d in docs:
            graph.add_document(d, known_ids)
            index.add_document(d, graph)

        assert index.semantic is not None
        assert index.semantic.ready
        assert index.semantic.faiss_index.ntotal == len(index.chunks)

        result = index.query("Why does P-101A keep failing?", top_k=5)
        assert result["hits"]
        for h in result["hits"]:
            assert 0 <= index.chunks.index(h["chunk"]) < len(index.chunks)

    def test_add_document_updates_docs_by_id(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        graph = KnowledgeGraph()
        index = HybridIndex()
        index.build([], graph, semantic=False)
        known_ids = {d.id for d in docs}
        for d in docs:
            graph.add_document(d, known_ids)
            index.add_document(d, graph)
        for d in docs:
            assert index.docs_by_id[d.id] is d


class TestHybridIndexCopy:
    """The property main.py's State.add_document() relies on for
    atomicity: copy(), mutate the copy, only then swap the reference —
    never mutate the live self.index in place, or a concurrent GET
    request could observe a half-updated index."""

    def test_copy_is_equal_but_independent(self, built_index):
        dup = built_index.copy()
        assert dup.chunks == built_index.chunks
        assert dup.doc_freq == built_index.doc_freq
        assert dup is not built_index
        assert dup.chunks is not built_index.chunks
        assert dup.postings is not built_index.postings

    def test_mutating_the_copy_never_changes_the_original(self, corpus_docs):
        docs = copy.deepcopy(corpus_docs)
        graph = KnowledgeGraph()
        graph.build(docs)
        original = HybridIndex()
        original.build(docs, graph, semantic=False)
        before_chunk_count = len(original.chunks)
        before_doc_freq = Counter(original.doc_freq)

        from app.ingest import load_document
        extra_doc = load_document(
            {"id": "WO-EXTRA-2", "type": "work_order", "equipment": "P-101A"},
            "A brand new corrective work order body about the crude pump.",
            fallback_id="WO-EXTRA-2",
        )
        known_ids = {d.id for d in docs} | {"WO-EXTRA-2"}
        graph_copy = graph.copy()
        graph_copy.add_document(extra_doc, known_ids)
        duplicated = original.copy()
        duplicated.add_document(extra_doc, graph_copy)

        assert len(duplicated.chunks) > before_chunk_count
        assert len(original.chunks) == before_chunk_count
        assert original.doc_freq == before_doc_freq
        assert "WO-EXTRA-2" not in original.doc_chunk_idx

    def test_postings_lists_are_not_aliased_between_copies(self, built_index):
        dup = built_index.copy()
        some_term = next(t for t, plist in built_index.postings.items() if plist)
        before = list(built_index.postings[some_term])

        dup.postings[some_term].append((999999, 1))

        assert built_index.postings[some_term] == before
        assert (999999, 1) not in built_index.postings[some_term]
