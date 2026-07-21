"""Named-key audit trail (audit.py)."""
import json

import pytest

from app import audit


@pytest.fixture
def isolated_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "_LOG_PATH", tmp_path / "audit_log.jsonl")
    return tmp_path / "audit_log.jsonl"


def test_log_action_writes_a_jsonl_entry(isolated_audit_log):
    audit.log_action("jsmith", "operator", "ingest", "WO-9999 (markdown, test.md)")
    assert isolated_audit_log.exists()
    line = isolated_audit_log.read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["actor"] == "jsmith"
    assert entry["role"] == "operator"
    assert entry["action"] == "ingest"
    assert entry["detail"] == "WO-9999 (markdown, test.md)"
    assert "ts" in entry


def test_recent_returns_most_recent_first(isolated_audit_log):
    audit.log_action("a", "operator", "ingest", "first")
    audit.log_action("b", "operator", "ingest", "second")
    audit.log_action("c", "operator", "ingest", "third")
    entries = audit.recent()
    assert [e["detail"] for e in entries] == ["third", "second", "first"]


def test_recent_respects_limit(isolated_audit_log):
    for i in range(10):
        audit.log_action("a", "operator", "ingest", str(i))
    entries = audit.recent(limit=3)
    assert len(entries) == 3
    assert entries[0]["detail"] == "9"


def test_recent_tolerates_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "_LOG_PATH", tmp_path / "does-not-exist.jsonl")
    assert audit.recent() == []


def test_recent_tolerates_corrupt_lines(isolated_audit_log):
    isolated_audit_log.write_text('{"actor": "a", "role": "operator", "action": "ingest", "detail": "ok", "ts": "x"}\nnot valid json\n', encoding="utf-8")
    entries = audit.recent()
    assert len(entries) == 1
    assert entries[0]["detail"] == "ok"


def test_log_action_never_raises_when_disk_write_fails(tmp_path, monkeypatch):
    # Point the log at a path whose *parent* is an existing plain file, not
    # a directory — mkdir(parents=True) on that must raise an OSError
    # subclass, which log_action() is required to swallow, not propagate.
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("x", encoding="utf-8")
    monkeypatch.setattr(audit, "_LOG_PATH", blocking_file / "audit.jsonl")
    audit.log_action("a", "operator", "ingest", "should not raise")  # must not raise
