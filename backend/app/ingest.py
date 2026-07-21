"""Document ingestion: frontmatter parsing, chunking, entity extraction."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .extract import extract_entities

logger = logging.getLogger("atlas.ingest")

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

DOC_TYPE_LABELS = {
    "drawing": "P&ID / Drawing",
    "datasheet": "Datasheet",
    "oem_manual": "OEM Manual",
    "procedure": "Procedure (SOP)",
    "work_order": "Work Order",
    "inspection": "Inspection Report",
    "incident": "Incident / Near-Miss",
    "memo": "Memo / Handover",
    "regulatory": "Regulatory",
    "email": "Email",
    "uploaded": "Uploaded",
}


@dataclass
class Chunk:
    id: str
    doc_id: str
    text: str
    entities: dict = field(default_factory=dict)


@dataclass
class Document:
    id: str
    title: str
    type: str
    date: str
    author: str
    meta: dict
    body: str
    entities: dict = field(default_factory=dict)
    chunks: list = field(default_factory=list)

    @property
    def type_label(self) -> str:
        return DOC_TYPE_LABELS.get(self.type, self.type.title())


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, raw[m.end():]


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_long_paragraph(para: str, max_chars: int) -> list[str]:
    """Force-split a single paragraph that alone exceeds max_chars: pack
    sentences greedily, and hard-slice any individual sentence that is still
    too long (e.g. OCR output or a data blob with no terminal punctuation).
    This is what guarantees no chunk is ever unbounded — previously a single
    paragraph with no blank lines (routine in extracted PDF/OCR text) became
    one giant chunk regardless of max_chars."""
    sentences = [s for s in SENTENCE_SPLIT_RE.split(para) if s.strip()] or [para]
    pieces, buf = [], ""
    for s in sentences:
        if len(s) > max_chars:
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.extend(s[i:i + max_chars] for i in range(0, len(s), max_chars))
            continue
        if buf and len(buf) + 1 + len(s) > max_chars:
            pieces.append(buf)
            buf = s
        else:
            buf = f"{buf} {s}" if buf else s
    if buf:
        pieces.append(buf)
    return pieces


def chunk_body(doc_id: str, body: str, max_chars: int = 700, overlap_chars: int = 100) -> list[Chunk]:
    """Split on blank lines, then greedily pack paragraphs into ~max_chars
    chunks. Paragraphs longer than max_chars are force-split (§_split_long_paragraph)
    so max_chars is a real hard cap, not just a guideline. Consecutive chunks
    share a small word-aligned overlap so a fact sitting on a chunk boundary
    isn't severed from the context that explains it.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces: list[str] = []
    for para in paragraphs:
        if len(para) > max_chars:
            pieces.extend(_split_long_paragraph(para, max_chars))
        else:
            pieces.append(para)

    chunks, buf = [], ""
    for piece in pieces:
        if buf and len(buf) + 2 + len(piece) > max_chars:
            chunks.append(buf)
            buf = piece
        else:
            buf = f"{buf}\n\n{piece}" if buf else piece
    if buf:
        chunks.append(buf)

    overlapped = []
    for i, text in enumerate(chunks):
        if i > 0 and overlap_chars > 0:
            tail = chunks[i - 1][-overlap_chars:]
            sp = tail.find(" ")  # start the carried-over tail on a word boundary
            tail = tail[sp + 1:] if sp != -1 else tail
            if tail:
                text = f"…{tail}  {text}"
        overlapped.append(text)

    return [Chunk(id=f"{doc_id}::c{i}", doc_id=doc_id, text=t) for i, t in enumerate(overlapped)]


def load_document(meta: dict, body: str, fallback_id: str, known_doc_ids=None) -> Document:
    doc = Document(
        id=meta.get("id", fallback_id),
        title=meta.get("title", fallback_id),
        type=meta.get("type", "uploaded"),
        date=meta.get("date", ""),
        author=meta.get("author", ""),
        meta=meta,
        body=body.strip(),
    )
    doc.entities = extract_entities(doc.title + "\n" + doc.body, known_doc_ids=known_doc_ids)
    # Equipment listed in frontmatter counts as a strong mention —
    # uppercased for the same reason extract_entities() canonicalises regex
    # matches: "p-101a" in frontmatter and "P-101A" in the body must resolve
    # to the same graph node, not two.
    for tag in re.split(r",\s*", meta.get("equipment", "")):
        if tag:
            doc.entities["equipment"][tag.upper()] += 3
    doc.chunks = chunk_body(doc.id, doc.body)
    for chunk in doc.chunks:
        chunk.entities = extract_entities(chunk.text, known_doc_ids=known_doc_ids)
    return doc


def load_corpus(corpus_dir: Path) -> list[Document]:
    # Two passes: first collect every document's id (cheap — just the
    # frontmatter), then load with the full known-id set available, so
    # extract_entities() can recognise a reference to *any* corpus document
    # by name, not only ones matching DOCREF_RE's prefix pattern or the
    # small SPECIAL_DOC_IDS fallback (see extract.py).
    paths = sorted(corpus_dir.glob("*.md"))
    parsed = []
    known_ids = set()
    for path in paths:
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        fallback_id = path.stem.upper()
        parsed.append((meta, body, fallback_id))
        known_ids.add(meta.get("id", fallback_id))
    return [
        load_document(meta, body, fallback_id=fallback_id, known_doc_ids=known_ids)
        for meta, body, fallback_id in parsed
    ]


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _safe_corpus_filename(doc_id: str) -> str | None:
    """Collapse a document id to a filesystem-safe basename — letters,
    digits, underscore, hyphen only, nothing else survives. Returns None if
    nothing safe is left (e.g. an id that was entirely punctuation/unicode),
    so the caller can skip persistence rather than write a mangled name.

    Deliberately conservative — no dots, no slashes, no path separators of
    any kind pass through — because doc.id ultimately traces back to
    untrusted input (an uploaded filename, or a frontmatter `id:` field
    inside the uploaded file itself; see main.py's ingest()), and this is
    what keeps a crafted id from resolving outside the corpus directory.
    """
    safe = _SAFE_ID_RE.sub("-", doc_id).strip("-")
    return safe or None


def save_document_to_corpus(doc, corpus_dir: Path) -> Path | None:
    """Write an accepted document back to the seed-corpus directory as a
    plain frontmatter + body .md file, so it survives a process restart —
    load_corpus() picks it up next boot exactly like any seed document.
    This is the fix for the previously-disclosed gap (ARCHITECTURE.md §11):
    uploaded documents used to live only in process memory.

    Best-effort and never raises: returns the written path on success, None
    on any failure (including an unsafe id) — a disk-persistence problem
    must not fail the ingest request that's already live in memory, same
    "log and continue" pattern as alerts.py's ack/dispatch stores.
    """
    safe_name = _safe_corpus_filename(doc.id)
    if not safe_name:
        logger.warning("refusing to persist document with no filesystem-safe id: %r", doc.id)
        return None
    try:
        corpus_dir_resolved = corpus_dir.resolve()
        target = (corpus_dir_resolved / f"{safe_name}.md").resolve()
        # Defense in depth beyond the character allowlist above: the write
        # target must land directly inside corpus_dir, no exceptions.
        if target.parent != corpus_dir_resolved:
            logger.warning("refusing to persist document outside corpus dir: %s", target)
            return None
        lines = ["---"]
        for key, value in doc.meta.items():
            value = str(value).replace("\n", " ").replace("\r", " ").strip()
            lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(doc.body)
        corpus_dir_resolved.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines), encoding="utf-8")
        return target
    except OSError:
        logger.warning("could not persist document %s to corpus dir (non-fatal)", doc.id, exc_info=True)
        return None
