"""Chunking and document-loading behaviour."""
from app.ingest import (
    _safe_corpus_filename,
    chunk_body,
    load_corpus,
    load_document,
    parse_frontmatter,
    save_document_to_corpus,
)


def test_chunk_hard_cap_on_unbroken_paragraph():
    # One giant paragraph with no blank lines — the shape that previously
    # produced a single ~105,000-char chunk regardless of max_chars.
    body = "P-101A seal failure. " * 5000
    chunks = chunk_body("X", body, max_chars=700, overlap_chars=100)
    assert len(chunks) > 1
    assert max(len(c.text) for c in chunks) <= 700 + 100 + 5  # max_chars + overlap + small slack


def test_chunk_hard_cap_with_no_sentence_punctuation():
    # No '.', '!' or '?' anywhere — sentence splitting alone can't bound this.
    body = "abcdefghij" * 5000
    chunks = chunk_body("Y", body, max_chars=700, overlap_chars=100)
    assert len(chunks) > 1
    assert max(len(c.text) for c in chunks) <= 700 + 100 + 5


def test_chunk_overlap_carries_context_across_boundary():
    paras = [f"Paragraph {i} about pump seals and vibration limits at Unit 300." for i in range(20)]
    chunks = chunk_body("Z", "\n\n".join(paras), max_chars=700, overlap_chars=100)
    assert len(chunks) >= 2
    tail_of_first = chunks[0].text[-30:]
    # some suffix of chunk 0 should reappear at the start of chunk 1
    assert any(tail_of_first[-n:] in chunks[1].text for n in (10, 15, 20))


def test_short_document_is_not_artificially_split():
    body = "A short work order body.\n\nSecond paragraph here."
    chunks = chunk_body("W", body)
    assert len(chunks) == 1
    assert chunks[0].text == body


def test_parse_frontmatter_extracts_fields():
    raw = "---\nid: WO-9999\ntitle: Test order\ntype: work_order\n---\nBody text here."
    meta, body = parse_frontmatter(raw)
    assert meta == {"id": "WO-9999", "title": "Test order", "type": "work_order"}
    assert body.strip() == "Body text here."


def test_parse_frontmatter_no_frontmatter_returns_body_unchanged():
    raw = "Just a plain body, no YAML header."
    meta, body = parse_frontmatter(raw)
    assert meta == {}
    assert body == raw


def test_load_document_extracts_equipment_entities():
    doc = load_document(
        {"id": "WO-TEST", "title": "Test", "type": "work_order", "equipment": "P-101A"},
        "Seal failure observed on P-101A during routine inspection.",
        fallback_id="WO-TEST",
    )
    assert "P-101A" in doc.entities["equipment"]
    # frontmatter-listed equipment gets a mention-count boost (ingest.py)
    assert doc.entities["equipment"]["P-101A"] >= 3


# --- Upload persistence (save_document_to_corpus) -----------------------

def test_safe_corpus_filename_passes_through_normal_ids():
    assert _safe_corpus_filename("WO-2415") == "WO-2415"
    assert _safe_corpus_filename("UPLOAD-2") == "UPLOAD-2"


def test_safe_corpus_filename_strips_path_traversal_characters():
    # Every character that could build a path outside the corpus dir must
    # be gone: no dots, no slashes, no backslashes, no colons (Windows
    # drive letters), regardless of how deliberately it's crafted.
    dangerous = "../../../etc/passwd"
    safe = _safe_corpus_filename(dangerous)
    assert safe is not None
    assert "/" not in safe and ".." not in safe and "\\" not in safe


def test_safe_corpus_filename_returns_none_for_all_punctuation():
    assert _safe_corpus_filename("../../../") is None
    assert _safe_corpus_filename("::://\\\\") is None


def test_save_document_to_corpus_writes_a_reloadable_file(tmp_path):
    doc = load_document(
        {"id": "TESTDOC-1", "title": "Test Persisted Doc", "type": "work_order", "equipment": "P-101A"},
        "Seal failure observed on P-101A.",
        fallback_id="TESTDOC-1",
    )
    path = save_document_to_corpus(doc, tmp_path)
    assert path is not None
    assert path.exists()
    assert path.parent == tmp_path.resolve()

    # A fresh load_corpus() pass over the same directory (simulating a
    # process restart) must pick the document back up with the same id and
    # the same extracted entities — a real round trip, not just "a file
    # exists".
    reloaded = load_corpus(tmp_path)
    assert len(reloaded) == 1
    assert reloaded[0].id == "TESTDOC-1"
    assert "P-101A" in reloaded[0].entities["equipment"]


def test_save_document_to_corpus_refuses_path_traversal_id(tmp_path):
    doc = load_document(
        {"id": "../../evil", "title": "Malicious", "type": "work_order"},
        "body text", fallback_id="../../evil",
    )
    path = save_document_to_corpus(doc, tmp_path)
    # Either refused outright, or (since the sanitiser turns it into a safe
    # name like "evil") written *inside* tmp_path — never outside it.
    if path is not None:
        assert path.parent == tmp_path.resolve()
        assert path.resolve().is_relative_to(tmp_path.resolve())
    # The directories the traversal attempted to reach must not exist.
    assert not (tmp_path.parent.parent / "evil.md").exists()


def test_save_document_to_corpus_survives_multiline_meta_values(tmp_path):
    # A frontmatter value containing an embedded newline must not corrupt
    # the written file's frontmatter block (e.g. spawn a bogus extra key).
    doc = load_document(
        {"id": "TESTDOC-2", "title": "Multi\nline title", "type": "work_order"},
        "body", fallback_id="TESTDOC-2",
    )
    path = save_document_to_corpus(doc, tmp_path)
    assert path is not None
    reloaded = load_corpus(tmp_path)
    assert len(reloaded) == 1
    assert reloaded[0].id == "TESTDOC-2"
