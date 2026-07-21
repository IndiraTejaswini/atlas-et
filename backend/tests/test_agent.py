"""Agentic tool-calling loop (app/agent.py).

No LLM key is configured in this environment, so these tests mock the LLM
adapter's non-streaming tool-use shape (rag._LLM) to exercise the actual
plan -> execute-tool -> feed-result -> replan loop — not just the
"unavailable" path, which the live server already demonstrates without any
mocking. The fake mimics the same `client.messages.create(...)` ->
`.content` blocks shape the Gemini adapter (app/llm.py) presents; mirrors
test_rag_streaming.py's approach for the streaming shape.
"""
from types import SimpleNamespace

import pytest

from app import agent, compliance as compliance_engine, maintenance, rag


class _Block:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeResponse:
    def __init__(self, content):
        self.content = content


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("no more fake responses queued — loop called Claude more times than expected")
        return self._responses.pop(0)


class _FakeAnthropic:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


@pytest.fixture
def state(corpus_docs, built_graph, built_index):
    comp = compliance_engine.evaluate(corpus_docs)
    assets = maintenance.build_assets(corpus_docs, comp)
    return SimpleNamespace(docs=corpus_docs, graph=built_graph, compliance=comp, assets=assets, index=built_index)


def test_available_reflects_rag_anthropic_client(monkeypatch):
    monkeypatch.setattr(rag, "_LLM", None)
    assert agent.available() is False
    monkeypatch.setattr(rag, "_LLM", object())
    assert agent.available() is True


def test_run_agent_returns_none_when_no_client(monkeypatch, state):
    monkeypatch.setattr(rag, "_LLM", None)
    assert agent.run_agent("What should we prioritise this week?", state) is None


def test_run_agent_executes_a_tool_then_returns_final_answer(monkeypatch, state):
    tool_call = _Block("tool_use", id="t1", name="get_compliance_gaps", input={})
    final_text = _Block("text", text="PSV-1104 is the top priority — it's overdue.")
    fake = _FakeAnthropic([_FakeResponse([tool_call]), _FakeResponse([final_text])])
    monkeypatch.setattr(rag, "_LLM", fake)

    result = agent.run_agent("What compliance gaps need attention?", state)

    assert result["answer"] == "PSV-1104 is the top priority — it's overdue."
    assert result["truncated"] is False
    assert result["iterations"] == 1
    assert result["trace"][0]["tool"] == "get_compliance_gaps"
    # The tool result actually made it back to Claude as part of the second
    # call's input. Index 2, not -1: `messages` is a single list `run_agent`
    # keeps mutating in place, and the fake's recorded kwargs hold a live
    # reference to it (not a snapshot) — by the time the loop returns, later
    # appends have moved what "-1" points to. Index 2 (the tool-result
    # message itself) is written once and never overwritten.
    second_call_messages = fake.messages.calls[1]["messages"]
    tool_result_msg = second_call_messages[2]
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "t1"


def test_run_agent_search_documents_tool_uses_real_retrieval(monkeypatch, state):
    """The search_documents tool must call the actual hybrid index, not a
    stub — grounding the agent's own tool results in genuine retrieval."""
    tool_call = _Block("tool_use", id="t1", name="search_documents", input={"query": "P-101A seal failure"})
    final_text = _Block("text", text="Seal failures trace to a degraded Plan 32 flush.")
    fake = _FakeAnthropic([_FakeResponse([tool_call]), _FakeResponse([final_text])])
    monkeypatch.setattr(rag, "_LLM", fake)

    result = agent.run_agent("Why does P-101A keep failing?", state)

    assert result["answer"]
    preview = result["trace"][0]["result_preview"]
    assert "WO-" in preview or "OEM-SLZ-OHH" in preview  # a real cited document surfaced


def test_run_agent_executes_multiple_tools_across_iterations(monkeypatch, state):
    call1 = _Block("tool_use", id="t1", name="get_asset_health", input={"tag": "P-101A"})
    call2 = _Block("tool_use", id="t2", name="get_roi_summary", input={})
    final_text = _Block("text", text="P-101A is the worst-health asset and its repeat failures are the main avoidable cost.")
    fake = _FakeAnthropic([_FakeResponse([call1]), _FakeResponse([call2]), _FakeResponse([final_text])])
    monkeypatch.setattr(rag, "_LLM", fake)

    result = agent.run_agent("What's driving avoidable cost on P-101A?", state)

    assert result["iterations"] == 2
    assert [t["tool"] for t in result["trace"]] == ["get_asset_health", "get_roi_summary"]
    assert result["truncated"] is False


def test_run_agent_stops_at_max_iters_with_truncated_flag(monkeypatch, state):
    always_tool_call = [_FakeResponse([_Block("tool_use", id=f"t{i}", name="get_compliance_gaps", input={})]) for i in range(10)]
    fake = _FakeAnthropic(always_tool_call)
    monkeypatch.setattr(rag, "_LLM", fake)

    result = agent.run_agent("Keep planning forever", state, max_iters=3)

    assert result["truncated"] is True
    assert result["iterations"] == 3
    assert "limit" in result["answer"].lower()


def test_run_agent_returns_none_on_client_exception(monkeypatch, state):
    class _Boom:
        def create(self, **kwargs):
            raise RuntimeError("simulated API failure")

    class _BoomClient:
        messages = _Boom()

    monkeypatch.setattr(rag, "_LLM", _BoomClient())
    assert agent.run_agent("Anything", state) is None


def test_execute_tool_unknown_name_returns_error_dict_not_crash(state):
    result = agent._execute_tool("not_a_real_tool", {}, state)
    assert "error" in result


def test_execute_tool_get_asset_health_with_tag(state):
    result = agent._execute_tool("get_asset_health", {"tag": "P-101A"}, state)
    assert result["tag"] == "P-101A"
    assert "health" in result


def test_execute_tool_get_asset_health_unknown_tag(state):
    result = agent._execute_tool("get_asset_health", {"tag": "NOT-A-REAL-TAG"}, state)
    assert "error" in result


def test_execute_tool_get_asset_health_without_tag_lists_all(state):
    result = agent._execute_tool("get_asset_health", {}, state)
    assert isinstance(result, list)
    assert len(result) > 0
    assert all("tag" in a and "health" in a for a in result)


def test_execute_tool_get_compliance_gaps_only_open_findings(state):
    result = agent._execute_tool("get_compliance_gaps", {}, state)
    assert all(f["status"] in ("gap", "due_soon") for f in result["findings"])


def test_execute_tool_get_pm_schedule_respects_limit(state):
    result = agent._execute_tool("get_pm_schedule", {"limit": 2}, state)
    assert len(result["tasks"]) <= 2


def test_execute_tool_get_roi_summary_returns_real_computation(state):
    result = agent._execute_tool("get_roi_summary", {}, state)
    assert "avoidable_cost_inr" in result


def test_execute_tool_get_fleet_patterns_returns_real_computation(state):
    result = agent._execute_tool("get_fleet_patterns", {}, state)
    assert "patterns" in result and "warnings" in result


# --- Prompt-injection mitigation (ARCHITECTURE.md §14) -------------------

def test_agent_system_prompt_warns_about_tool_result_injection():
    low = agent.AGENT_SYSTEM_PROMPT.lower()
    assert "not instructions" in low or "never as" in low or "do not follow" in low
    assert "tool result" in low
