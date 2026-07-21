"""RAG answer composition: confidence must reflect actual grounding quality,
not just how many citations happened to be assembled — this is the fix for
the bug where an unrelated query (e.g. "boiling point of helium on mars")
scored 95% confidence because it produced 6 citations, regardless of whether
any of them were relevant.
"""
from app import rag


def test_relevant_query_is_grounded_with_reasonable_confidence(built_index):
    result = rag.answer("Why does P-101A keep failing?", built_index, built_index.docs_by_id)
    assert not result.get("low_confidence")
    assert result["confidence"] >= 0.4
    assert len(result["citations"]) > 0
    assert result["mode"] == "extractive"


def test_unrelated_query_is_not_grounded(built_index):
    result = rag.answer(
        "what is the boiling point of helium on mars", built_index, built_index.docs_by_id
    )
    assert result.get("low_confidence")
    assert result["confidence"] <= 0.1
    assert result["citations"] == []


def test_nonsense_query_returns_zero_confidence(built_index):
    result = rag.answer("asdfghjkl qwerty zxcvbn", built_index, built_index.docs_by_id)
    assert result["confidence"] == 0.0
    assert result["citations"] == []


def test_confidence_discriminates_relevant_from_irrelevant(built_index):
    relevant = rag.answer("Which relief valves are overdue for testing?", built_index, built_index.docs_by_id)
    irrelevant = rag.answer("tell me about submarine warfare", built_index, built_index.docs_by_id)
    assert relevant["confidence"] > irrelevant["confidence"] + 0.3


def test_citations_carry_required_fields(built_index):
    result = rag.answer("What are the pre-start checks for the crude charge pumps?",
                        built_index, built_index.docs_by_id)
    assert result["citations"], "expected at least one citation for a well-covered question"
    for c in result["citations"]:
        assert c["doc_id"]
        assert c["title"]
        assert "snippet" in c


def test_graph_path_explains_at_least_one_citation(built_index):
    result = rag.answer("Why does P-101A keep failing?", built_index, built_index.docs_by_id)
    assert any("graph_path" in c for c in result["citations"])


# --- Prompt-injection mitigation (ARCHITECTURE.md §14) -------------------

def test_system_prompt_instructs_treating_excerpts_as_data_not_instructions():
    low = rag.LLM_SYSTEM_PROMPT.lower()
    assert "not as" in low or "not instructions" in low or "never as" in low
    assert "instruction" in low


def test_context_wraps_excerpts_in_document_delimiters(built_index):
    retrieval = built_index.query("Why does P-101A keep failing?")
    prepared = rag._prepare_llm_context("Why does P-101A keep failing?", retrieval, built_index.docs_by_id)
    assert prepared is not None
    _citations, messages, _confidence = prepared
    content = messages[0]["content"]
    assert "<document_excerpts>" in content
    assert "</document_excerpts>" in content
    # the question must sit outside the delimited block, not inside it
    assert content.index("</document_excerpts>") < content.index("QUESTION:")
