"""Alert acknowledgement persistence — acks must survive a process restart,
not just live in an in-memory dict that resets every time the API restarts.
"""
import importlib

import pytest

from app import alerts


@pytest.fixture
def isolated_ack_store(tmp_path, monkeypatch):
    """Point the module at a scratch file so tests never touch the real
    backend/data/alerts_ack.json, and reset its in-memory state each test."""
    store = tmp_path / "alerts_ack.json"
    monkeypatch.setattr(alerts, "_ACK_STORE_PATH", store)
    monkeypatch.setattr(alerts, "_ACK", {})
    return store


def test_acknowledge_persists_to_disk(isolated_ack_store):
    alerts.acknowledge("alert-abc123", by="Test Operator")
    assert isolated_ack_store.exists()
    import json
    saved = json.loads(isolated_ack_store.read_text())
    assert saved["alert-abc123"]["by"] == "Test Operator"


def test_unacknowledge_persists_removal(isolated_ack_store):
    alerts.acknowledge("alert-abc123")
    alerts.unacknowledge("alert-abc123")
    import json
    saved = json.loads(isolated_ack_store.read_text())
    assert "alert-abc123" not in saved


def test_acks_survive_a_simulated_restart(isolated_ack_store):
    """The actual regression test: acknowledge an alert, then reload the
    module fresh (simulating a process restart) and confirm the ack is
    still there — this is what was broken before (in-memory dict, gone on
    every restart)."""
    alerts.acknowledge("alert-persist-me", by="Shift Lead")

    reloaded = importlib.reload(alerts)
    try:
        reloaded._ACK_STORE_PATH = isolated_ack_store
        reloaded._ACK = reloaded._load_acks()
        assert "alert-persist-me" in reloaded._ACK
        assert reloaded._ACK["alert-persist-me"]["by"] == "Shift Lead"
    finally:
        importlib.reload(alerts)  # restore the module to its normal on-disk path for later tests


def test_load_acks_tolerates_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts, "_ACK_STORE_PATH", tmp_path / "does-not-exist.json")
    assert alerts._load_acks() == {}


def test_load_acks_tolerates_corrupt_file(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(alerts, "_ACK_STORE_PATH", bad)
    assert alerts._load_acks() == {}


def test_build_reflects_acknowledged_state(isolated_ack_store, corpus_docs, built_graph):
    from app import compliance as compliance_engine
    from app import lessons as lessons_analyze
    from app import quality, telemetry

    comp = compliance_engine.evaluate(corpus_docs)
    assets = []
    result = alerts.build(
        lessons_analyze.analyze(corpus_docs, built_graph, comp, assets),
        quality.evaluate(corpus_docs, assets),
        comp, telemetry,
    )
    assert result["alerts"], "expected at least one alert from this corpus"
    first_id = result["alerts"][0]["id"]
    alerts.acknowledge(first_id)

    result2 = alerts.build(
        lessons_analyze.analyze(corpus_docs, built_graph, comp, assets),
        quality.evaluate(corpus_docs, assets),
        comp, telemetry,
    )
    acked = next(a for a in result2["alerts"] if a["id"] == first_id)
    assert acked["acknowledged"] is not None


# --- Outbound webhook delivery -----------------------------------------

@pytest.fixture
def isolated_dispatch_store(tmp_path, monkeypatch):
    """Same isolation strategy as isolated_ack_store, for the dispatch
    (already-sent) history instead of the acknowledgement history."""
    store = tmp_path / "alerts_dispatched.json"
    monkeypatch.setattr(alerts, "_DISPATCH_STORE_PATH", store)
    monkeypatch.setattr(alerts, "_DISPATCHED", set())
    return store


def _sample_alert(aid="alert-abc123", acknowledged=None):
    return {
        "id": aid, "source": "Compliance", "severity": "high", "title": "PSV-1104 overdue",
        "detail": "Test overdue by 400 days.", "docs": ["INSP-102"], "equipment": ["PSV-1104"],
        "team": "Inspection & Integrity", "team_key": "integrity", "acknowledged": acknowledged,
    }


def test_dispatch_new_is_noop_when_unconfigured(isolated_dispatch_store):
    result = alerts.dispatch_new({"alerts": [_sample_alert()]}, url="")
    assert result == {"configured": False, "sent": 0, "failed": 0}


def test_dispatch_new_sends_active_alerts_via_injected_poster(isolated_dispatch_store):
    sent_payloads = []

    def fake_poster(url, payload):
        sent_payloads.append((url, payload))
        return True

    result = alerts.dispatch_new({"alerts": [_sample_alert()]}, url="https://hooks.example/x", poster=fake_poster)
    assert result == {"configured": True, "sent": 1, "failed": 0}
    assert len(sent_payloads) == 1
    assert sent_payloads[0][0] == "https://hooks.example/x"
    assert "PSV-1104 overdue" in sent_payloads[0][1]["text"]
    assert "Inspection & Integrity" in sent_payloads[0][1]["text"]


def test_dispatch_new_is_idempotent_across_calls(isolated_dispatch_store):
    """The core correctness property: re-running dispatch against the same
    alert must never re-send it — this is what makes it safe to call on
    every SSE tick instead of spamming the webhook every 3 seconds."""
    calls = {"n": 0}

    def counting_poster(url, payload):
        calls["n"] += 1
        return True

    alert_set = {"alerts": [_sample_alert()]}
    r1 = alerts.dispatch_new(alert_set, url="https://hooks.example/x", poster=counting_poster)
    r2 = alerts.dispatch_new(alert_set, url="https://hooks.example/x", poster=counting_poster)
    assert r1["sent"] == 1
    assert r2["sent"] == 0
    assert calls["n"] == 1


def test_dispatch_new_skips_acknowledged_alerts(isolated_dispatch_store):
    def failing_poster(url, payload):
        raise AssertionError("should never be called for an acknowledged alert")

    result = alerts.dispatch_new(
        {"alerts": [_sample_alert(acknowledged={"by": "Op", "at": "10:00:00"})]},
        url="https://hooks.example/x", poster=failing_poster,
    )
    assert result == {"configured": True, "sent": 0, "failed": 0}


def test_dispatch_new_counts_delivery_failures_without_raising(isolated_dispatch_store):
    result = alerts.dispatch_new({"alerts": [_sample_alert()]}, url="https://hooks.example/x", poster=lambda u, p: False)
    assert result == {"configured": True, "sent": 0, "failed": 1}


def test_dispatch_history_persists_to_disk(isolated_dispatch_store):
    alerts.dispatch_new({"alerts": [_sample_alert()]}, url="https://hooks.example/x", poster=lambda u, p: True)
    assert isolated_dispatch_store.exists()
    import json
    saved = json.loads(isolated_dispatch_store.read_text())
    assert "alert-abc123" in saved


def test_send_test_webhook_unconfigured(isolated_dispatch_store):
    assert alerts.send_test_webhook(url="") == {"configured": False, "sent": False}


def test_send_test_webhook_posts_a_synthetic_payload(isolated_dispatch_store):
    seen = []
    result = alerts.send_test_webhook(url="https://hooks.example/x", poster=lambda u, p: seen.append(p) or True)
    assert result == {"configured": True, "sent": True}
    assert "test alert" in seen[0]["text"].lower()
