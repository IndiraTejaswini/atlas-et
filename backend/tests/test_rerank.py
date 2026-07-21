"""Second-stage lexical/positional reranker (search.rerank)."""
from collections import Counter

from app.search import _proximity_bonus, rerank


class FakeChunk:
    def __init__(self, text):
        self.text = text


def test_proximity_bonus_rewards_clustered_terms():
    tokens = "the seal flush line was found partially plugged with wax".split()
    close = _proximity_bonus(tokens, ["seal", "flush"], window=8)
    tokens_far = ("seal " + "filler " * 20 + "flush").split()
    far = _proximity_bonus(tokens_far, ["seal", "flush"], window=8)
    assert close > far


def test_proximity_bonus_zero_for_single_term():
    tokens = ["seal", "failure", "observed"]
    assert _proximity_bonus(tokens, ["seal"]) == 0.0


def test_rerank_rewards_bigram_phrase_match():
    chunks = [
        FakeChunk("The mechanical seal failure was traced to a degraded flush line."),
        FakeChunk("Mechanical components were serviced. Seal replaced. Failure logged separately."),
    ]
    chunk_tokens = [Counter(c.text.lower().split()) for c in chunks]
    candidates = [(1.0, 0), (1.0, 1)]  # tied first-stage scores
    result = rerank(["mechanical", "seal", "failure"], [], candidates, chunk_tokens, chunks, top_n=2)
    # chunk 0 contains "mechanical seal failure" as a run of bigrams; chunk 1 has
    # the same words scattered — reranker must prefer the phrase match.
    assert result[0][1] == 0


def test_rerank_preserves_base_score_ordering_when_no_extra_signal():
    chunks = [FakeChunk("unrelated text"), FakeChunk("more unrelated text")]
    chunk_tokens = [Counter(c.text.lower().split()) for c in chunks]
    candidates = [(5.0, 0), (1.0, 1)]
    result = rerank(["seal"], [], candidates, chunk_tokens, chunks, top_n=2)
    assert result[0][1] == 0  # higher base score still wins absent any rerank signal


def test_rerank_empty_candidates_returns_empty():
    assert rerank(["x"], [], [], [], [], top_n=5) == []


def test_query_rerank_flag_does_not_error(built_index):
    r1 = built_index.query("Why does P-101A keep failing?", use_rerank=True)
    r2 = built_index.query("Why does P-101A keep failing?", use_rerank=False)
    assert r1["hits"] and r2["hits"]
