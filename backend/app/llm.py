"""LLM provider adapter behind a minimal Anthropic-Messages-shaped interface.

Why an adapter: rag.py's synthesis and agent.py's tool-calling loop were
written against the Anthropic SDK and are covered by tests that mock exactly
that shape (`client.messages.create(...)` returning `.content` blocks, and
`client.messages.stream(...)` yielding `.text_stream`). This module presents
that same tiny surface over whichever provider is configured, so the proven
retrieval / streaming / plan-loop logic and its tests stay untouched — only
the small, well-defined translation between message/tool formats lives here.

Two providers are supported, auto-detected from the API key:
  - **OpenAI-compatible** (Groq / OpenRouter / OpenAI) — spoken over plain
    `urllib` (no extra dependency; the same stdlib alerts.py already uses),
    with a real User-Agent so Groq's Cloudflare front doesn't 403 the default
    `Python-urllib` one. This is the recommended free path: a Groq key
    (`gsk_...`, free at https://console.groq.com, no card) has generous
    quota and supports tool calling.
  - **Google Gemini** (`AIza...` key + `google-genai`), kept as an option.

Gating is unchanged: no key configured -> `build_client()` returns None ->
everything degrades to extractive answers (and the agent reports itself
unavailable). Never a crash, never a fabricated answer. The provider is not
named in any user-facing string beyond configuration — the app calls this an
"AI synthesis" / model path, an honest "grounded synthesis by an LLM" claim
rather than a vendor badge that could drift.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("atlas.llm")

_HTTP_TIMEOUT_S = 60
# A non-default User-Agent: Groq sits behind Cloudflare, which 403s the stock
# "Python-urllib/x.y" agent (observed error 1010). Any normal UA passes.
_USER_AGENT = "atlas-industrial-knowledge/1.0"

# Provider defaults (base URL + a tool-calling-capable model). The model is
# overridable per provider via LLM_MODEL without a code change.
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"
OPENAI_BASE = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# Set by build_client() for display/debug (e.g. the smoke test).
ACTIVE_PROVIDER: str | None = None
ACTIVE_MODEL: str | None = None

try:
    from google import genai
    _GENAI_AVAILABLE = True
except Exception:  # pragma: no cover - import guard, exercised only when the SDK is absent
    genai = None
    _GENAI_AVAILABLE = False

try:
    from google.genai import types as _genai_types
except Exception:  # pragma: no cover
    _genai_types = None


# --- Anthropic-shaped result objects the callers already expect -------------
class _Block:
    """A text block (`.type == "text"`, `.text`) or a tool-use block
    (`.type == "tool_use"`, `.id`, `.name`, `.input`) — the attributes
    rag.compose_llm and agent.run_agent read off `response.content`."""

    def __init__(self, type: str, *, text=None, id=None, name=None, input=None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input


class _Response:
    def __init__(self, content: list):
        self.content = content


class _StreamCtx:
    """Mimics `with client.messages.stream(...) as s: for t in s.text_stream`."""

    def __init__(self, text_iter):
        self._text_iter = text_iter

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return self._text_iter


# ============================================================================
# OpenAI-compatible provider (Groq / OpenRouter / OpenAI) over stdlib urllib
# ============================================================================
def _http_post_json(url: str, key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_sse(url: str, key: str, payload: dict):
    """POST with stream=True and yield each token's text as it arrives,
    parsing the OpenAI Server-Sent-Events `data: {...}` frames."""
    body = json.dumps({**payload, "stream": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    })
    resp = urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S)
    try:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choices = obj.get("choices") or [{}]
            delta = (choices[0].get("delta") or {}).get("content")
            if delta:
                yield delta
    finally:
        resp.close()


def _to_openai_messages(system, messages: list) -> list:
    """Anthropic-shaped messages -> OpenAI chat messages. Handles the three
    shapes the callers produce: a plain string turn, an assistant turn that
    is a list of `_Block`s (text + tool_use), and a user turn that is a list
    of tool_result dicts (which become OpenAI `role: "tool"` messages)."""
    out = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        role, content = m["role"], m["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif role == "assistant":
            text = " ".join(b.text for b in content
                            if getattr(b, "type", None) == "text" and b.text)
            tool_calls = [{
                "id": b.id, "type": "function",
                "function": {"name": b.name, "arguments": json.dumps(b.input or {})},
            } for b in content if getattr(b, "type", None) == "tool_use"]
            msg = {"role": "assistant", "content": text or None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)
        else:  # user turn carrying tool results
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    raw = b.get("content")
                    out.append({
                        "role": "tool", "tool_call_id": b.get("tool_use_id"),
                        "content": raw if isinstance(raw, str) else json.dumps(raw),
                    })
    return out


def _to_openai_tools(tools):
    if not tools:
        return None
    return [{
        "type": "function",
        "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
        },
    } for t in tools]


def _from_openai_message(msg: dict) -> list:
    blocks = []
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except (ValueError, TypeError):
            args = {}
        blocks.append(_Block("tool_use", id=tc.get("id"), name=fn.get("name"), input=args))
    if not blocks:
        content = msg.get("content")
        if content:
            blocks.append(_Block("text", text=content))
    return blocks


class _OpenAIMessages:
    def __init__(self, key: str, url: str, model: str):
        self._key, self._url, self._model = key, url, model

    def create(self, *, model=None, max_tokens=1024, system=None, messages=None, tools=None):
        payload = {
            "model": model or self._model,
            "messages": _to_openai_messages(system, messages or []),
            "max_tokens": max_tokens,
        }
        ot = _to_openai_tools(tools)
        if ot:
            payload["tools"] = ot
        data = _http_post_json(self._url, self._key, payload)
        return _Response(_from_openai_message(data["choices"][0]["message"]))

    def stream(self, *, model=None, max_tokens=1024, system=None, messages=None):
        payload = {
            "model": model or self._model,
            "messages": _to_openai_messages(system, messages or []),
            "max_tokens": max_tokens,
        }
        return _StreamCtx(_http_post_sse(self._url, self._key, payload))


class _OpenAIClient:
    def __init__(self, key: str, base_url: str, model: str):
        self.messages = _OpenAIMessages(key, base_url.rstrip("/") + "/chat/completions", model)


# ============================================================================
# Google Gemini provider (google-genai SDK)
# ============================================================================
def _to_gemini_contents(messages: list) -> list:
    id_to_name: dict[str, str] = {}
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                if getattr(b, "type", None) == "tool_use":
                    id_to_name[b.id] = b.name
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        parts: list = []
        if isinstance(content, str):
            parts.append({"text": content})
        else:
            for b in content:
                btype = getattr(b, "type", None)
                if btype == "text" and b.text:
                    parts.append({"text": b.text})
                elif btype == "tool_use":
                    parts.append({"function_call": {"name": b.name, "args": b.input or {}}})
                elif isinstance(b, dict) and b.get("type") == "tool_result":
                    name = id_to_name.get(b.get("tool_use_id"), "tool")
                    raw = b.get("content")
                    try:
                        payload = json.loads(raw) if isinstance(raw, str) else raw
                    except (ValueError, TypeError):
                        payload = raw
                    if not isinstance(payload, dict):
                        payload = {"result": payload}
                    parts.append({"function_response": {"name": name, "response": payload}})
        contents.append({"role": role, "parts": parts})
    return contents


def _to_gemini_tools(tools):
    if not tools:
        return None
    decls = []
    for t in tools:
        decl = {"name": t["name"], "description": t.get("description", "")}
        schema = t.get("input_schema") or {}
        if isinstance(schema, dict) and schema.get("properties"):
            decl["parameters"] = schema
        decls.append(decl)
    return decls


def _from_gemini_response(resp) -> list:
    blocks: list = []
    candidates = getattr(resp, "candidates", None) or []
    parts = []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = (getattr(content, "parts", None) or []) if content is not None else []
    n = 0
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is not None:
            n += 1
            args = getattr(fc, "args", None) or {}
            blocks.append(_Block("tool_use", id=f"gemini_call_{n}", name=fc.name, input=dict(args)))
            continue
        text = getattr(p, "text", None)
        if text:
            blocks.append(_Block("text", text=text))
    if not blocks:
        text = getattr(resp, "text", None)
        if text:
            blocks.append(_Block("text", text=text))
    return blocks


def _make_gemini_config(system, max_tokens, tool_decls):
    cfg = {"system_instruction": system, "max_output_tokens": max_tokens}
    if tool_decls:
        cfg["tools"] = [{"function_declarations": tool_decls}]
    if _genai_types is not None:
        try:
            return _genai_types.GenerateContentConfig(**cfg)
        except Exception:  # pragma: no cover - SDK version drift; dict is accepted too
            return cfg
    return cfg


class _GeminiMessages:
    def __init__(self, client, default_model: str):
        self._client = client
        self._default_model = default_model

    def create(self, *, model=None, max_tokens=1024, system=None, messages=None, tools=None):
        resp = self._client.models.generate_content(
            model=model or self._default_model,
            contents=_to_gemini_contents(messages or []),
            config=_make_gemini_config(system, max_tokens, _to_gemini_tools(tools)),
        )
        return _Response(_from_gemini_response(resp))

    def stream(self, *, model=None, max_tokens=1024, system=None, messages=None):
        iterator = self._client.models.generate_content_stream(
            model=model or self._default_model,
            contents=_to_gemini_contents(messages or []),
            config=_make_gemini_config(system, max_tokens, None),
        )
        return _StreamCtx(chunk.text for chunk in iterator if getattr(chunk, "text", None))


class _GeminiClient:
    def __init__(self, genai_client, default_model: str = GEMINI_MODEL):
        self.messages = _GeminiMessages(genai_client, default_model)


# ============================================================================
# Provider resolution + client construction
# ============================================================================
def _resolve():
    """Pick (provider, key, base_url, model) from the environment, or None.
    A key can live in any of the known env slots (GROQ_API_KEY,
    GEMINI_API_KEY, OPENAI_API_KEY, LLM_API_KEY); the provider is then
    detected from the key's prefix, so whatever the user pastes 'just works'
    regardless of which variable name they used."""
    if os.environ.get("GROQ_API_KEY"):
        return ("openai", os.environ["GROQ_API_KEY"].strip(), GROQ_BASE,
                os.environ.get("LLM_MODEL", GROQ_MODEL))

    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
           or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
    if not key:
        return None
    base_override = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL")
    if key.startswith("gsk_"):
        return ("openai", key, base_override or GROQ_BASE, os.environ.get("LLM_MODEL", GROQ_MODEL))
    if key.startswith("sk-or-"):
        return ("openai", key, base_override or OPENROUTER_BASE, os.environ.get("LLM_MODEL", OPENROUTER_MODEL))
    if key.startswith("AIza"):
        return ("gemini", key, None, os.environ.get("GEMINI_MODEL", GEMINI_MODEL))
    if key.startswith("sk-"):
        return ("openai", key, base_override or OPENAI_BASE, os.environ.get("LLM_MODEL", OPENAI_MODEL))
    # Unknown prefix: prefer Gemini if its SDK is present, else treat as an
    # OpenAI-compatible key against whatever base_url was provided.
    if _GENAI_AVAILABLE and not base_override:
        return ("gemini", key, None, os.environ.get("GEMINI_MODEL", GEMINI_MODEL))
    return ("openai", key, base_override or GROQ_BASE, os.environ.get("LLM_MODEL", GROQ_MODEL))


def build_client():
    """Return an LLM client, or None when no provider is configured — the
    same optional-capability contract the previous Anthropic path had."""
    global ACTIVE_PROVIDER, ACTIVE_MODEL
    resolved = _resolve()
    if not resolved:
        return None
    provider, key, base, model = resolved
    if provider == "openai":
        ACTIVE_PROVIDER, ACTIVE_MODEL = "openai-compatible", model
        logger.info("LLM enabled: OpenAI-compatible provider at %s, model=%s", base, model)
        return _OpenAIClient(key, base, model)
    if provider == "gemini":
        if not _GENAI_AVAILABLE:
            logger.warning("Gemini key set but google-genai not installed — run: pip install google-genai")
            return None
        try:
            ACTIVE_PROVIDER, ACTIVE_MODEL = "gemini", model
            logger.info("LLM enabled: Gemini, model=%s", model)
            return _GeminiClient(genai.Client(api_key=key), model)
        except Exception:
            logger.warning("could not initialise Gemini client — falling back to extractive", exc_info=True)
            return None
    return None


def active_model() -> str | None:
    return ACTIVE_MODEL
