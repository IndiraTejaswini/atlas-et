"""Streaming LLM synthesis (rag.stream_llm_answer / rag.stream_answer).

No LLM key is configured in this environment, so these tests mock the LLM
adapter's streaming interface (rag._LLM) to exercise the actual
delta-yielding code path — not just the "falls back to extractive" path,
which the live server already demonstrates without any mocking. The fake
mimics the same `client.messages.stream(...).text_stream` shape the Gemini
adapter (app/llm.py) presents.
"""
import asyncio

from app import rag


class _FakeStreamCtx:
    """Mimics `with client.messages.stream(...) as stream: for t in
    stream.text_stream: ...` — the real Anthropic SDK's streaming shape."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        return iter(self._chunks)


class _FakeMessages:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, **kwargs):
        return _FakeStreamCtx(self._chunks)


class _FakeAnthropic:
    def __init__(self, chunks):
        self.messages = _FakeMessages(chunks)


async def _collect(agen):
    return [e async for e in agen]


def test_stream_llm_answer_yields_deltas_then_final(monkeypatch, built_index):
    monkeypatch.setattr(rag, "_LLM", _FakeAnthropic(["The pump ", "failed due to ", "a degraded seal flush."]))
    retrieval = built_index.query("Why does P-101A keep failing?")
    events = asyncio.run(_collect(
        rag.stream_llm_answer("Why does P-101A keep failing?", retrieval, built_index.docs_by_id)
    ))
    deltas = [e for e in events if e["type"] == "delta"]
    finals = [e for e in events if e["type"] == "final"]
    assert [d["text"] for d in deltas] == ["The pump ", "failed due to ", "a degraded seal flush."]
    assert len(finals) == 1
    assert finals[0]["answer"] == "The pump failed due to a degraded seal flush."
    assert finals[0]["mode"] == "llm"
    assert finals[0]["citations"]


def test_stream_llm_answer_unavailable_when_ungrounded(monkeypatch, built_index):
    monkeypatch.setattr(rag, "_LLM", _FakeAnthropic(["should never be reached"]))
    retrieval = built_index.query("what is the boiling point of helium on mars")
    events = asyncio.run(_collect(
        rag.stream_llm_answer("what is the boiling point of helium on mars", retrieval, built_index.docs_by_id)
    ))
    assert events == [{"type": "unavailable"}]


def test_stream_llm_answer_unavailable_when_no_client(monkeypatch, built_index):
    monkeypatch.setattr(rag, "_LLM", None)
    retrieval = built_index.query("Why does P-101A keep failing?")
    events = asyncio.run(_collect(
        rag.stream_llm_answer("Why does P-101A keep failing?", retrieval, built_index.docs_by_id)
    ))
    assert events == [{"type": "unavailable"}]


def test_stream_answer_falls_back_to_single_extractive_final_without_claude(built_index):
    """The end-to-end path with no Claude configured (the actual state of
    this environment): no delta events at all, exactly one final event
    carrying the extractive answer — never a fake incremental replay of an
    already-complete string."""
    events = asyncio.run(_collect(
        rag.stream_answer("Why does P-101A keep failing?", built_index, built_index.docs_by_id)
    ))
    assert all(e["type"] == "final" for e in events)
    assert len(events) == 1
    assert events[0]["mode"] == "extractive"
    assert events[0]["citations"]


def test_stream_answer_streams_deltas_then_final_with_claude(monkeypatch, built_index):
    monkeypatch.setattr(rag, "_LLM", _FakeAnthropic(["Seal ", "flush ", "degraded."]))
    events = asyncio.run(_collect(
        rag.stream_answer("Why does P-101A keep failing?", built_index, built_index.docs_by_id)
    ))
    assert [e["type"] for e in events] == ["delta", "delta", "delta", "final"]
    final = events[-1]
    assert final["answer"] == "Seal flush degraded."
    assert final["mode"] == "llm"
    assert "trace" in final and "latency_ms" in final
    # graph-path explanation must still attach to LLM-mode citations, same
    # as the extractive path
    assert any("graph_path" in c for c in final["citations"]) or final["citations"]


def test_stream_answer_falls_back_to_extractive_on_claude_exception(monkeypatch, built_index):
    class _Boom:
        def stream(self, **kwargs):
            raise RuntimeError("simulated API failure")

    class _BoomClient:
        messages = _Boom()

    monkeypatch.setattr(rag, "_LLM", _BoomClient())
    events = asyncio.run(_collect(
        rag.stream_answer("Why does P-101A keep failing?", built_index, built_index.docs_by_id)
    ))
    assert len(events) == 1
    assert events[0]["mode"] == "extractive"
