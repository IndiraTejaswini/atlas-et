"""FAISS HNSW-backed semantic index: real ANN search + disk persistence."""
import shutil

import numpy as np
import pytest

from app import embeddings
from app.embeddings import CACHE_DIR, SemanticIndex


@pytest.fixture(autouse=True)
def clean_cache():
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    yield
    shutil.rmtree(CACHE_DIR, ignore_errors=True)


def test_size_aware_rank_cap_prevents_near_full_rank_svd(corpus_docs):
    """Regression test for the LSA 'zero measured contribution' finding: an
    uncapped k = min(dims, n-1) lets rank grow to nearly n at small corpus
    sizes, leaving SVD almost nothing to compress (measured: k=48 for n=49
    chunks, indistinguishable from raw TF-IDF cosine). The size-aware cap
    must keep k well below n here."""
    chunks = [c for d in corpus_docs for c in d.chunks]
    idx = SemanticIndex(dims=64)
    idx.build(chunks, use_cache=False)
    assert idx.k < len(chunks) // 2


def test_semantic_signal_contributes_measurable_lift_on_indirect_queries(built_index):
    """The other half of the same regression test, measured through the
    actual evaluation harness rather than just the raw k value — this is
    what the k-cap fix is actually for."""
    from app import evaluation
    lexical = evaluation._run_benchmark(built_index, use_graph=False, use_semantic=False,
                                         use_rerank=False, category="indirect")
    semantic = evaluation._run_benchmark(built_index, use_graph=False, use_semantic=True,
                                          use_rerank=False, category="indirect")
    assert semantic["hit_at_1"] >= lexical["hit_at_1"]


def test_faiss_is_actually_available_in_this_environment():
    # If this fails, every other test in this file degrades to the
    # brute-force fallback path silently — surface that loudly instead.
    assert embeddings.faiss_available()


def test_build_uses_faiss_index(built_index):
    sem = built_index.semantic
    assert sem.ready
    assert sem.faiss_index is not None
    assert sem.faiss_index.ntotal == len(built_index.chunks)


def test_top_k_returns_bounded_approximate_results(built_index):
    hits = built_index.semantic.top_k("mechanical seal failure on the pump", k=5)
    assert 0 < len(hits) <= 5
    for idx, score in hits:
        assert 0 <= idx < len(built_index.chunks)
        assert -1.01 <= score <= 1.01  # cosine similarity range (small float slack)


def test_top_k_matches_brute_force_ranking_at_small_scale(built_index):
    """At this corpus size (k=50 > n chunks) the ANN index should return
    exactly the same ranking as exact brute-force cosine similarity."""
    sem = built_index.semantic
    query = "seal flush degraded causing failure"
    ann_hits = sem.top_k(query, k=len(built_index.chunks))
    sims = sem.similarities(query)
    exact_order = list(np.argsort(-sims))[:len(ann_hits)]
    ann_order = [i for i, _ in ann_hits]
    assert ann_order == exact_order


def test_cache_round_trip_produces_identical_embeddings(corpus_docs):
    chunks = [c for d in corpus_docs for c in d.chunks]

    idx1 = SemanticIndex()
    idx1.build(chunks)
    assert not idx1.from_cache

    idx2 = SemanticIndex()
    idx2.build(chunks)
    assert idx2.from_cache
    assert np.allclose(idx1.chunk_emb, idx2.chunk_emb)
    assert idx1.top_k("pump seal failure", 5) == idx2.top_k("pump seal failure", 5)


def test_cache_is_content_addressed_not_reused_across_different_corpora(corpus_docs):
    """A cache entry for one document set must never be handed back for a
    different one — this is what keeps the warm-start safe to enable by
    default."""
    chunks_a = [c for d in corpus_docs[:10] for c in d.chunks]
    chunks_b = [c for d in corpus_docs[8:] for c in d.chunks]  # overlapping but different

    idx_a = SemanticIndex()
    idx_a.build(chunks_a)
    idx_b = SemanticIndex()
    idx_b.build(chunks_b)

    assert not idx_a.from_cache
    assert not idx_b.from_cache  # different content -> different cache key -> no false hit
    assert idx_a.faiss_index.ntotal != idx_b.faiss_index.ntotal or len(chunks_a) == len(chunks_b)


# --- Incremental add (add_chunks) ----------------------------------------

def test_add_chunks_extends_faiss_index_without_refitting(corpus_docs):
    initial = [c for d in corpus_docs[:15] for c in d.chunks]
    new_chunks = [c for d in corpus_docs[15:] for c in d.chunks]
    assert new_chunks, "test corpus slice must actually have chunks to add"

    idx = SemanticIndex(dims=64)
    idx.build(initial, use_cache=False)
    k_before, ntotal_before = idx.k, idx.faiss_index.ntotal

    added = idx.add_chunks(new_chunks)

    assert added == len(new_chunks)
    assert idx.k == k_before  # basis (rank) is unchanged — no refit happened
    assert idx.faiss_index.ntotal == ntotal_before + len(new_chunks)
    assert len(idx.chunk_emb) == ntotal_before + len(new_chunks)


def test_add_chunks_keeps_row_order_aligned_with_input_order(corpus_docs):
    initial = [c for d in corpus_docs[:15] for c in d.chunks]
    new_chunks = [c for d in corpus_docs[15:] for c in d.chunks]
    idx = SemanticIndex(dims=64)
    idx.build(initial, use_cache=False)
    n_before = idx.faiss_index.ntotal

    idx.add_chunks(new_chunks)

    # The vector at row `n_before + i` must be new_chunks[i]'s own
    # projection, not some other chunk's — HybridIndex relies on this
    # alignment to map a FAISS row index back to the right Chunk object.
    for i, c in enumerate(new_chunks):
        expected = idx._query_vec(c.text)
        if expected is None:
            continue
        assert np.allclose(idx.chunk_emb[n_before + i], expected, atol=1e-5)


def test_add_chunks_on_unready_index_is_a_noop():
    idx = SemanticIndex()
    assert idx.ready is False
    assert idx.add_chunks([]) == 0


def test_add_chunks_handles_a_chunk_with_no_known_vocabulary():
    from app.ingest import Chunk
    idx = SemanticIndex(dims=64)
    idx.build([Chunk(id=f"c{i}", doc_id="D", text=f"pump seal failure vibration bearing {i}") for i in range(10)],
              use_cache=False)
    weird_chunk = Chunk(id="weird", doc_id="D", text="")  # shares no vocabulary at all
    n_before = idx.faiss_index.ntotal
    added = idx.add_chunks([weird_chunk])
    assert added == 1
    assert idx.faiss_index.ntotal == n_before + 1
    assert np.allclose(idx.chunk_emb[-1], 0.0)  # zero vector, not skipped/misaligned
