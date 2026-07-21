"""State.cached() — generation-keyed memoization for expensive derived
endpoints. The correctness property that matters: a cached value must never
be served once the underlying corpus has changed (rebuild() bumps the
generation and clears the cache), and must be reused (not recomputed) within
the same generation.
"""
from app.main import State


def test_cached_computes_once_within_a_generation():
    state = State()
    state.rebuild([])
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return "result"

    assert state.cached("k", compute) == "result"
    assert state.cached("k", compute) == "result"
    assert state.cached("k", compute) == "result"
    assert calls["n"] == 1


def test_cache_invalidates_on_rebuild():
    state = State()
    state.rebuild([])
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"result-{calls['n']}"

    first = state.cached("k", compute)
    state.rebuild([])  # simulates an ingest changing the corpus
    second = state.cached("k", compute)

    assert first == "result-1"
    assert second == "result-2"  # recomputed, not the stale first value
    assert calls["n"] == 2


def test_different_keys_are_independent():
    state = State()
    state.rebuild([])
    assert state.cached("a", lambda: "A") == "A"
    assert state.cached("b", lambda: "B") == "B"
    assert state.cached("a", lambda: "SHOULD NOT SEE THIS") == "A"


def test_rebuild_clears_all_cached_keys_not_just_touched_ones():
    state = State()
    state.rebuild([])
    state.cached("a", lambda: "A1")
    state.cached("b", lambda: "B1")
    state.rebuild([])
    assert state.cached("a", lambda: "A2") == "A2"
    assert state.cached("b", lambda: "B2") == "B2"
