import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.graph import KnowledgeGraph
from app.ingest import load_corpus
from app.main import CORPUS_DIR
from app.search import HybridIndex


@pytest.fixture(scope="session")
def corpus_docs():
    """The real 18-document seed corpus, loaded once per test session."""
    return load_corpus(CORPUS_DIR)


@pytest.fixture(scope="session")
def built_graph(corpus_docs):
    g = KnowledgeGraph()
    g.build(corpus_docs)
    return g


@pytest.fixture(scope="session")
def built_index(corpus_docs, built_graph):
    idx = HybridIndex()
    idx.build(corpus_docs, built_graph)
    return idx


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    """FastAPI TestClient against a fresh app instance. Raises the ingest
    rate limit so test runs (which upload repeatedly) don't trip it.

    Loads the real 18-document seed corpus into memory, but then repoints
    every module that persists to backend/data/ at scratch tmp_path files
    *before* returning — those modules read their *_PATH globals at call
    time (not at import time), so anything a test does through this client
    (ingest a document, ack an alert, trigger an audit log entry, ...)
    writes into isolated scratch files instead of the real corpus/data/
    directory on every test run.
    """
    from fastapi.testclient import TestClient

    from app import alerts as alerts_module, audit as audit_module
    from app.main import STATE, app, load_corpus as _load_corpus, CORPUS_DIR as _CORPUS_DIR
    import app.main as main_module

    main_module._INGEST_LIMITER.max = 10_000
    STATE.rebuild(_load_corpus(_CORPUS_DIR))
    monkeypatch.setattr(main_module, "CORPUS_DIR", tmp_path)
    monkeypatch.setattr(alerts_module, "_ACK_STORE_PATH", tmp_path / "alerts_ack.json")
    monkeypatch.setattr(alerts_module, "_ACK", {})
    monkeypatch.setattr(alerts_module, "_DISPATCH_STORE_PATH", tmp_path / "alerts_dispatched.json")
    monkeypatch.setattr(alerts_module, "_DISPATCHED", set())
    monkeypatch.setattr(audit_module, "_LOG_PATH", tmp_path / "audit_log.jsonl")
    return TestClient(app)
