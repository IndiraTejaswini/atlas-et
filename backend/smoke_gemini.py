"""Pre-demo smoke test for the optional LLM path (Groq / Gemini / any
OpenAI-compatible provider).

Run this AFTER setting your key, to confirm the Copilot synthesis and the
Planning Agent actually work end-to-end with your key *before* you rely on
them in a live demo:

    cd backend
    # Windows PowerShell — Groq (free, recommended):
    #   $env:GEMINI_API_KEY = "gsk_...your-groq-key..."   # any key slot works
    #   .venv\\Scripts\\python smoke_gemini.py

It makes real (free-tier) calls and prints PASS/FAIL for each stage. This is
a throwaway dev utility — safe to delete before submission.
"""
import sys


def main() -> int:
    from app import agent, llm, rag
    from app.ingest import load_corpus
    from app.main import CORPUS_DIR, STATE

    ok = True

    client = llm.build_client()
    print("1. LLM client built (key present) ...", "PASS" if client
          else "FAIL  -> set a key (GROQ_API_KEY / GEMINI_API_KEY). Groq: https://console.groq.com")
    if not client:
        return 1
    print(f"   provider = {llm.ACTIVE_PROVIDER}, model = {llm.ACTIVE_MODEL}")

    try:
        resp = client.messages.create(
            max_tokens=64, system="You reply with a single short word.",
            messages=[{"role": "user", "content": "Say hello."}])
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        print("2. raw text generation .............", "PASS" if text else "FAIL (empty response)",
              "->", repr(text[:60]))
        ok = ok and bool(text)
    except Exception as e:
        print("2. raw text generation ............. FAIL ->", repr(e)[:200])
        return 1

    print("3. Copilot LLM path enabled ........", "PASS" if rag._LLM is not None
          else "FAIL (rag._LLM is None — key must be set before the process starts)")

    STATE.rebuild(load_corpus(CORPUS_DIR))
    try:
        result = agent.run_agent("What should Rotating Equipment prioritise this week?", STATE)
        if not result:
            print("4. Planning Agent end-to-end .......  FAIL (returned None — check the key/model)")
            return 1
        tools = [t["tool"] for t in result["trace"]]
        print("4. Planning Agent end-to-end .......  PASS")
        print("   tools the model chose to call:", tools or "(answered without tools)")
        print("   answer:", (result["answer"] or "")[:180].replace("\n", " "))
        ok = ok and bool(result["answer"])
    except Exception as e:
        print("4. Planning Agent end-to-end .......  FAIL ->", repr(e)[:200])
        return 1

    print("\n" + ("ALL PASS — the LLM path works. Safe to demo the Planning Agent."
                  if ok else "Some stages FAILED — see above; the app still runs in free extractive mode."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
