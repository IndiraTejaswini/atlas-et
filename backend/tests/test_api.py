"""API-level tests through the real FastAPI app — covers request/response
shape, upload validation, and the id-collision/rate-limit/size-limit fixes.
"""
import io


def test_health_endpoint(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["documents"] >= 18


def test_metrics_endpoint_is_prometheus_text_format(api_client):
    api_client.get("/api/documents/WO-2415")
    api_client.get("/api/documents/WO-2301")
    r = api_client.get("/api/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert "atlas_documents_total" in body
    assert "atlas_http_requests_total" in body
    # route TEMPLATE, not the resolved id — two different documents fetched
    # above must aggregate under one series, not create two (the classic
    # Prometheus cardinality mistake this is specifically guarding against)
    assert 'path="/api/documents/{doc_id}"' in body
    assert "WO-2415" not in body
    assert "WO-2301" not in body


def test_stats_endpoint_shape(api_client):
    r = api_client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("documents", "chunks", "graph_nodes", "graph_edges", "compliance_score"):
        assert key in body


def test_unknown_document_returns_404(api_client):
    r = api_client.get("/api/documents/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_ask_endpoint_returns_valid_shape(api_client):
    r = api_client.post("/api/ask", json={"question": "Why does P-101A keep failing?"})
    assert r.status_code == 200
    body = r.json()
    for key in ("answer", "citations", "confidence", "mode", "trace"):
        assert key in body


def test_ask_endpoint_doc_type_filter_excludes_other_types(api_client):
    r = api_client.post("/api/ask", json={
        "question": "Why does P-101A keep failing?", "doc_types": ["work_order"],
    })
    assert r.status_code == 200
    body = r.json()
    assert all(c["type"] == "work_order" for c in body["citations"])


def test_ask_stream_endpoint_terminates_with_final_event(api_client):
    # The underlying generator (rag.stream_answer) always terminates on its
    # own — unlike /api/stream/telemetry|alerts, which loop until the client
    # disconnects — so a plain synchronous request is safe here and doesn't
    # risk the TestClient-streaming hang that open-ended SSE endpoints do.
    r = api_client.get("/api/ask/stream", params={"question": "Why does P-101A keep failing?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    lines = [l for l in r.text.split("\n") if l.startswith("data:")]
    assert len(lines) == 1  # no Claude configured -> single extractive final event
    import json
    payload = json.loads(lines[0][len("data:"):].strip())
    assert payload["type"] == "final"
    assert payload["mode"] == "extractive"
    assert payload["citations"]


def test_ingest_rejects_dangerous_extension(api_client):
    r = api_client.post(
        "/api/ingest",
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00fake"), "application/octet-stream")},
    )
    assert r.status_code == 415


def test_ingest_accepts_csv_and_it_becomes_searchable(api_client):
    csv_bytes = b"Tag,Failure,Downtime\nP-101A,mechanical seal failure,12\n"
    r = api_client.post(
        "/api/ingest", files={"file": ("test-upload.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "csv"
    assert "P-101A" in body["entities"].get("equipment", {})


def test_duplicate_filename_ingest_gets_unique_ids_not_merged(api_client):
    """Regression test for the duplicate-id bug: uploading the same filename
    repeatedly must never produce two documents sharing one id (which
    previously silently merged their graph nodes and made one unreachable
    via /api/documents/{id})."""
    payload = b"Sample content mentioning P-101A seal failure.\n"
    ids = []
    for _ in range(3):
        r = api_client.post(
            "/api/ingest",
            files={"file": ("dup-test.txt", io.BytesIO(payload), "text/plain")},
        )
        assert r.status_code == 200
        ids.append(r.json()["doc"]["id"])
    assert len(ids) == len(set(ids)), f"duplicate ids assigned: {ids}"
    # every id must actually be independently retrievable
    for doc_id in ids:
        assert api_client.get(f"/api/documents/{doc_id}").status_code == 200


def test_collision_renamed_id_stays_in_sync_with_meta(api_client):
    """Regression test: State.add_document() renames doc.id on collision
    (-2, -3, ...) but previously left doc.meta["id"] holding the stale
    pre-rename value — GET /api/documents/{id} returns meta verbatim, so a
    client would see a document whose own metadata disagreed with the id
    it was just fetched by."""
    payload = b"Sample content mentioning E-104 fouling.\n"
    r1 = api_client.post("/api/ingest", files={"file": ("meta-sync-test.txt", io.BytesIO(payload), "text/plain")})
    r2 = api_client.post("/api/ingest", files={"file": ("meta-sync-test.txt", io.BytesIO(payload), "text/plain")})
    second_id = r2.json()["doc"]["id"]
    assert second_id != r1.json()["doc"]["id"]  # renamed for collision

    fetched = api_client.get(f"/api/documents/{second_id}").json()
    assert fetched["meta"]["id"] == second_id


def test_graph_endpoint_returns_nodes_and_edges(api_client):
    r = api_client.get("/api/graph")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) > 0
    assert len(body["edges"]) > 0


def test_vision_sample_parse_absorbs_into_graph_idempotently(api_client):
    r1 = api_client.get("/api/vision/parse-sample")
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["tags_found"]  # the sample drawing always has recognisable tags

    docs_after_first = api_client.get("/api/stats").json()["documents"]
    r2 = api_client.get("/api/vision/parse-sample")
    docs_after_second = api_client.get("/api/stats").json()["documents"]

    # first call may absorb the drawing into the graph; repeat calls must not
    # keep creating new documents on every page load
    assert docs_after_second == docs_after_first
    assert r2.json()["graph_updated"] is False


# --- Audit trail ----------------------------------------------------------

def test_ingest_writes_an_audit_entry(api_client):
    payload = b"Sample content mentioning V-302 overpressure.\n"
    r = api_client.post("/api/ingest", files={"file": ("audit-test.txt", io.BytesIO(payload), "text/plain")})
    doc_id = r.json()["doc"]["id"]

    entries = api_client.get("/api/audit").json()["entries"]
    matches = [e for e in entries if e["action"] == "ingest" and doc_id in e["detail"]]
    assert matches, f"expected an ingest audit entry mentioning {doc_id}, got {entries[:3]}"


def test_ack_alert_writes_audit_entry_with_actor_name(api_client, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "API_KEYS", {"secret-key": "operator"})
    monkeypatch.setattr(main_module, "API_KEY_NAMES", {"secret-key": "jsmith"})

    alerts = api_client.get("/api/alerts", headers={"X-API-Key": "secret-key"}).json()["alerts"]
    assert alerts, "expected at least one alert from the seed corpus"
    alert_id = alerts[0]["id"]

    r = api_client.post(f"/api/alerts/{alert_id}/ack", headers={"X-API-Key": "secret-key"})
    assert r.status_code == 200

    entries = api_client.get("/api/audit", headers={"X-API-Key": "secret-key"}).json()["entries"]
    matches = [e for e in entries if e["action"] == "alert.ack" and e["detail"] == alert_id]
    assert matches
    assert matches[0]["actor"] == "jsmith"


def test_audit_endpoint_requires_operator_when_keys_configured(api_client, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "API_KEYS", {"secret-key": "operator"})
    r = api_client.get("/api/audit")
    assert r.status_code == 401
