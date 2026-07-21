"""Provider-adapter translation tests (app/llm.py).

Neither provider's live endpoint is called here: the Gemini adapter gets a
*fake* google-genai client injected, and the OpenAI-compatible adapter (Groq
/ OpenRouter / OpenAI) gets its `urllib` POST helpers monkeypatched. Both
directions of the translation are asserted — Anthropic-shaped messages/tools
in, provider request out; provider response back to Anthropic-shaped
`.content` blocks. This is the one genuinely new, provider-specific piece of
the port, so it gets direct coverage rather than relying on a live API call
the test environment can't make.
"""
from types import SimpleNamespace

import pytest

from app import llm


# ============================================================================
# OpenAI-compatible provider (Groq / OpenRouter / OpenAI) over urllib
# ============================================================================
def _oai_client():
    return llm._OpenAIClient("gsk_test", llm.GROQ_BASE, "test-model")


def test_openai_create_returns_text_block(monkeypatch):
    captured = {}

    def fake_post(url, key, payload):
        captured["url"], captured["payload"] = url, payload
        return {"choices": [{"message": {"role": "assistant", "content": "P-101A seal failed."}}]}

    monkeypatch.setattr(llm, "_http_post_json", fake_post)
    resp = _oai_client().messages.create(
        max_tokens=100, system="sys", messages=[{"role": "user", "content": "why?"}])
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "P-101A seal failed."
    # system prepended, user message carried through
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "why?"}
    assert captured["url"].endswith("/chat/completions")


def test_openai_create_returns_tool_use_block(monkeypatch):
    def fake_post(url, key, payload):
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "get_asset_health", "arguments": '{"tag":"P-101A"}'}}]}}]}

    monkeypatch.setattr(llm, "_http_post_json", fake_post)
    tools = [{"name": "get_asset_health", "description": "d",
              "input_schema": {"type": "object", "properties": {"tag": {"type": "string"}}}}]
    resp = _oai_client().messages.create(
        max_tokens=100, system="s", messages=[{"role": "user", "content": "health?"}], tools=tools)
    b = resp.content[0]
    assert b.type == "tool_use"
    assert b.name == "get_asset_health"
    assert b.input == {"tag": "P-101A"}
    assert b.id == "call_1"  # OpenAI supplies real tool-call ids (no synthesis needed)


def test_openai_tool_result_roundtrip(monkeypatch):
    """An assistant tool_use block + a user tool_result must become an OpenAI
    assistant message with tool_calls followed by a role:"tool" message with
    the matching tool_call_id."""
    captured = {}

    def fake_post(url, key, payload):
        captured["payload"] = payload
        return {"choices": [{"message": {"role": "assistant", "content": "done"}}]}

    monkeypatch.setattr(llm, "_http_post_json", fake_post)
    prior = llm._Block("tool_use", id="call_1", name="get_compliance_gaps", input={})
    messages = [
        {"role": "user", "content": "gaps?"},
        {"role": "assistant", "content": [prior]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1",
                                      "content": '{"score": 23}'}]},
    ]
    _oai_client().messages.create(max_tokens=100, system="s", messages=messages)
    msgs = captured["payload"]["messages"]
    assert msgs[1] == {"role": "user", "content": "gaps?"}
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["tool_calls"][0]["id"] == "call_1"
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "get_compliance_gaps"
    assert msgs[3] == {"role": "tool", "tool_call_id": "call_1", "content": '{"score": 23}'}


def test_openai_tools_translation_shape(monkeypatch):
    captured = {}

    def fake_post(url, key, payload):
        captured["payload"] = payload
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    monkeypatch.setattr(llm, "_http_post_json", fake_post)
    tools = [{"name": "get_roi_summary", "description": "d",
              "input_schema": {"type": "object", "properties": {}}}]
    _oai_client().messages.create(max_tokens=50, system="s",
                                  messages=[{"role": "user", "content": "x"}], tools=tools)
    t = captured["payload"]["tools"][0]
    assert t["type"] == "function"
    assert t["function"]["name"] == "get_roi_summary"


def test_openai_stream_yields_text_chunks(monkeypatch):
    def fake_sse(url, key, payload):
        yield from ["Seal ", "flush ", "degraded."]

    monkeypatch.setattr(llm, "_http_post_sse", fake_sse)
    with _oai_client().messages.stream(
            max_tokens=50, system="s", messages=[{"role": "user", "content": "why?"}]) as s:
        out = list(s.text_stream)
    assert out == ["Seal ", "flush ", "degraded."]


# ============================================================================
# Gemini provider (fake injected google-genai client)
# ============================================================================
def _part(text=None, function_call=None):
    return SimpleNamespace(text=text, function_call=function_call)


def _resp(parts, text=None):
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))], text=text)


class _FakeModels:
    def __init__(self, response=None, stream_chunks=None):
        self._response = response
        self._stream_chunks = stream_chunks or []
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self._response

    def generate_content_stream(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config, "stream": True})
        return iter([SimpleNamespace(text=t) for t in self._stream_chunks])


class _FakeGenai:
    def __init__(self, response=None, stream_chunks=None):
        self.models = _FakeModels(response, stream_chunks)


def _gemini_client(response=None, stream_chunks=None):
    fake = _FakeGenai(response, stream_chunks)
    return llm._GeminiClient(fake, "gemini-test"), fake


def test_gemini_create_returns_text_block():
    client, _ = _gemini_client(response=_resp([_part(text="P-101A seal failed.")]))
    resp = client.messages.create(max_tokens=100, system="s",
                                  messages=[{"role": "user", "content": "why?"}])
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "P-101A seal failed."


def test_gemini_create_returns_tool_use_block():
    fc = SimpleNamespace(name="get_asset_health", args={"tag": "P-101A"})
    client, _ = _gemini_client(response=_resp([_part(function_call=fc)]))
    resp = client.messages.create(max_tokens=100, system="s",
                                  messages=[{"role": "user", "content": "health?"}])
    block = resp.content[0]
    assert block.type == "tool_use"
    assert block.name == "get_asset_health"
    assert block.input == {"tag": "P-101A"}
    assert block.id


def test_gemini_tool_result_roundtrip_recovers_function_name():
    client, fake = _gemini_client(response=_resp([_part(text="done")]))
    prior = llm._Block("tool_use", id="c1", name="get_compliance_gaps", input={})
    messages = [
        {"role": "user", "content": "what gaps?"},
        {"role": "assistant", "content": [prior]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1",
                                      "content": '{"score": 23}'}]},
    ]
    client.messages.create(max_tokens=100, system="s", messages=messages)
    contents = fake.models.calls[-1]["contents"]
    assert contents[1] == {"role": "model", "parts": [{"function_call": {"name": "get_compliance_gaps", "args": {}}}]}
    assert contents[2] == {"role": "user", "parts": [
        {"function_response": {"name": "get_compliance_gaps", "response": {"score": 23}}}]}


def test_gemini_stream_yields_text_chunks():
    client, _ = _gemini_client(stream_chunks=["Seal ", "flush ", "degraded."])
    with client.messages.stream(max_tokens=100, system="s",
                                messages=[{"role": "user", "content": "why?"}]) as stream:
        out = list(stream.text_stream)
    assert out == ["Seal ", "flush ", "degraded."]


# ============================================================================
# Provider resolution + gating
# ============================================================================
_KEY_VARS = ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY")


@pytest.fixture
def _no_keys(monkeypatch):
    for var in _KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)


def test_build_client_is_none_without_any_key(_no_keys):
    assert llm.build_client() is None


def test_groq_key_selects_openai_compatible_provider(_no_keys, monkeypatch):
    # A gsk_ key pasted into the generic GEMINI_API_KEY slot must still be
    # detected as Groq (OpenAI-compatible), not sent to Gemini.
    monkeypatch.setenv("GEMINI_API_KEY", "gsk_faketestkey")
    client = llm.build_client()
    assert isinstance(client.messages, llm._OpenAIMessages)


def test_openrouter_key_selects_openai_compatible_provider(_no_keys, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-v1-faketestkey")
    client = llm.build_client()
    assert isinstance(client.messages, llm._OpenAIMessages)
