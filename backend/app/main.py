"""ATLAS — Industrial Knowledge Intelligence API."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from . import agent as agent_engine
from . import alerts as alerts_engine
from . import audit as audit_engine
from . import bench as bench_engine
from . import compliance as compliance_engine
from . import maintenance, ocr, ontology, qms, quality, rag, roi, sample_pid, schedule, telemetry, vision
from .evidence import build_evidence_pack
from .formats import SUPPORTED, read_any
from .graph import KnowledgeGraph
from .ingest import load_corpus, load_document, parse_frontmatter, save_document_to_corpus
from .lessons import analyze as lessons_analyze
from .search import HybridIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("atlas")

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "corpus"
_STARTED_AT = time.time()

# --- Config (env-overridable; sensible defaults for local/demo use) --------
MAX_UPLOAD_MB = float(os.environ.get("ATLAS_MAX_UPLOAD_MB", "15"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
INGEST_RATE_PER_MIN = int(os.environ.get("ATLAS_INGEST_RATE_PER_MIN", "12"))
API_KEY = os.environ.get("ATLAS_API_KEY")  # unset => write endpoints stay open (dev/demo mode)
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [o.strip() for o in os.environ.get("ATLAS_CORS_ORIGINS", _default_origins).split(",") if o.strip()]

# Extensions we will never index, regardless of what SUPPORTED/text-fallback
# would otherwise do with them — executables and scripts have no business in
# a document corpus, and "unknown extension -> treat as text" (formats.py)
# would otherwise happily ingest one.
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".bat", ".cmd", ".com",
    ".scr", ".ps1", ".sh", ".jar", ".apk", ".app", ".vbs", ".js", ".jse",
    ".wsf", ".gadget", ".iso", ".deb", ".rpm",
}

# --- Role-based access -------------------------------------------------
# Two roles, because two is what this API's actual surface supports today:
#   viewer   — read-only. Not enforced anywhere by default (the demo stays
#              publicly readable unless ATLAS_REQUIRE_READ_AUTH is set) but
#              the role exists so read-gating is a config change, not a code
#              change, if/when a deployment wants it.
#   operator — may mutate state: ingest documents, acknowledge alerts.
# There is deliberately no third "admin" tier: nothing in this API is more
# privileged than "operator" today, and adding one with no actual capability
# to gate would be a fake feature — exactly what this whole audit is about
# not doing. Add it when there's a real admin-only action.
ROLE_RANK = {"viewer": 0, "operator": 1}


def _parse_api_keys() -> tuple[dict[str, str], dict[str, str]]:
    """(key -> role, key -> display name) from ATLAS_API_KEYS
    ("key1:operator:jsmith,key2:viewer") or the legacy single ATLAS_API_KEY
    (kept working, implicitly role=operator, no display name). The display
    name is purely attributional — it's what the audit log (GET /api/audit,
    audit.py) shows instead of a masked key prefix; it grants no capability
    a key doesn't already have from its role."""
    keys: dict[str, str] = {}
    names: dict[str, str] = {}
    for pair in os.environ.get("ATLAS_API_KEYS", "").split(","):
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(":", 2)
        key = parts[0].strip()
        role = (parts[1].strip().lower() if len(parts) > 1 and parts[1].strip() else "operator")
        name = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        if key and role in ROLE_RANK:
            keys[key] = role
            if name:
                names[key] = name
        elif key:
            logger.warning("ATLAS_API_KEYS: ignoring key with unknown role %r", role)
    if API_KEY and API_KEY not in keys:
        keys[API_KEY] = "operator"
    return keys, names


API_KEYS, API_KEY_NAMES = _parse_api_keys()  # key -> role, key -> display name
REQUIRE_READ_AUTH = os.environ.get("ATLAS_REQUIRE_READ_AUTH", "").lower() in ("1", "true", "yes")

if not API_KEYS:
    logger.warning(
        "No API keys configured (ATLAS_API_KEYS / ATLAS_API_KEY) — /api/ingest and "
        "alert-ack endpoints are UNAUTHENTICATED. Set one before exposing this service "
        "beyond localhost."
    )
elif REQUIRE_READ_AUTH:
    logger.info("ATLAS_REQUIRE_READ_AUTH set — read endpoints now require at least 'viewer'.")


def require_role(min_role: str):
    """Dependency factory: `Depends(require_role("operator"))`. No-op when no
    keys are configured at all (local/demo mode, same as before); once any
    key exists, the caller must present one whose role meets the bar."""
    min_rank = ROLE_RANK[min_role]

    def _dep(x_api_key: str | None = Header(default=None)) -> None:
        if not API_KEYS:
            return
        role = API_KEYS.get(x_api_key or "")
        if role is None or ROLE_RANK[role] < min_rank:
            raise HTTPException(401, f"Missing or insufficient X-API-Key (requires role >= {min_role!r})")

    return _dep


require_operator = require_role("operator")
require_viewer = require_role("viewer")


def get_actor(x_api_key: str | None = Header(default=None)) -> str:
    """Resolve the caller's audit-log identity — separate from require_role
    above (which only decides allow/deny) so routes can log *who* acted
    without changing how authorization itself works. A key with no
    configured display name is identified by a short masked prefix, never
    logged in full (it's still a secret) and never collapsed into an
    indistinguishable "operator" for every caller either."""
    if not x_api_key:
        return "anonymous"
    name = API_KEY_NAMES.get(x_api_key)
    if name:
        return name
    return f"key:{x_api_key[:4]}…" if len(x_api_key) > 4 else "key:***"


def get_role(x_api_key: str | None = Header(default=None)) -> str:
    """The caller's resolved role, for endpoints (like /api/vision/parse)
    that log an action without themselves requiring a specific role."""
    return API_KEYS.get(x_api_key or "", "none")


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield


# Applying require_viewer as a global dependency (rather than per-route) is
# what makes ATLAS_REQUIRE_READ_AUTH a config change, not a code change —
# every GET is covered automatically, including any added later. It composes
# correctly with the per-route require_operator on write endpoints below: an
# operator-ranked key already satisfies the viewer bar, so no double auth is
# needed there.
app = FastAPI(
    title="ATLAS Industrial Knowledge Intelligence",
    lifespan=lifespan,
    dependencies=[Depends(require_viewer)] if REQUIRE_READ_AUTH else [],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# --- Metrics ----------------------------------------------------------------
# In-process counters, rendered as Prometheus text exposition format at
# /api/metrics — no external agent/exporter dependency, scrapable by any
# standard Prometheus-compatible collector.
_REQUEST_COUNTS: dict[tuple[str, str, int], int] = defaultdict(int)
_REQUEST_DURATIONS_MS: list[float] = []
_MAX_DURATION_SAMPLES = 2000  # bounded ring buffer — this is telemetry, not an audit log


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    dur_ms = (time.perf_counter() - t0) * 1000
    # The matched ROUTE TEMPLATE ("/api/documents/{doc_id}"), not the
    # resolved path — using the resolved path would give every distinct
    # document/asset/alert id its own metrics series, the classic
    # Prometheus cardinality mistake.
    route = request.scope.get("route")
    path_label = route.path if route else request.url.path
    _REQUEST_COUNTS[(request.method, path_label, response.status_code)] += 1
    _REQUEST_DURATIONS_MS.append(dur_ms)
    if len(_REQUEST_DURATIONS_MS) > _MAX_DURATION_SAMPLES:
        del _REQUEST_DURATIONS_MS[:len(_REQUEST_DURATIONS_MS) - _MAX_DURATION_SAMPLES]
    return response


class RateLimiter:
    """Simple in-process sliding-window limiter — no external infra needed at
    this scale, just enough to blunt a naive single-client flood."""

    def __init__(self, max_per_minute: int):
        self.max = max_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            window = [t for t in self._hits[key] if now - t < 60]
            if len(window) >= self.max:
                self._hits[key] = window
                return False
            window.append(now)
            self._hits[key] = window
            return True


_INGEST_LIMITER = RateLimiter(INGEST_RATE_PER_MIN)


async def _read_limited(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload in chunks, aborting as soon as it exceeds `limit` —
    bounds both memory and processing time instead of buffering an arbitrarily
    large body before checking its size."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_MB:g} MB upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _reject_dangerous_extension(filename: str) -> None:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(415, f"File type '{ext}' is not accepted")


class State:
    def __init__(self):
        self.docs = []
        self.graph = KnowledgeGraph()
        self.index = HybridIndex()
        self.compliance = {}
        self.assets = []
        self.build_ms = 0.0
        self.query_latencies = []
        # Bumped on every rebuild(); pairs with _cache below to memoize
        # expensive derived endpoints (lessons/schedule/ontology/evaluation)
        # without ever risking staleness — see cached().
        self.generation = 0
        self._cache: dict[str, tuple[int, object]] = {}
        # Reentrant: add_document() holds this across its own call into
        # rebuild() so id-collision-check + append + full rebuild is one
        # atomic unit relative to other threads (no lost updates, no
        # duplicate ids from two concurrent uploads).
        self._lock = threading.RLock()

    def rebuild(self, docs=None):
        with self._lock:
            t0 = time.perf_counter()
            docs = self.docs if docs is None else docs
            # Build into local variables first, then swap all derived state
            # in one go — readers never observe a graph built from `docs`
            # paired with an index or compliance result from the old docs.
            new_graph = KnowledgeGraph()
            new_graph.build(docs)
            new_index = HybridIndex()
            new_index.build(docs, new_graph)
            new_compliance = compliance_engine.evaluate(docs)
            new_assets = maintenance.build_assets(docs, new_compliance)
            build_ms = round((time.perf_counter() - t0) * 1000, 1)

            self.docs = docs
            self.graph = new_graph
            self.index = new_index
            self.compliance = new_compliance
            self.assets = new_assets
            self.build_ms = build_ms
            self.generation += 1
            self._cache.clear()
            logger.info(
                "rebuild: %d docs, %d chunks, %d graph nodes / %d edges in %.1fms",
                len(docs), len(new_index.chunks), len(new_graph.nodes), len(new_graph.edges), build_ms,
            )

    def cached(self, key: str, compute_fn):
        """Memoize compute_fn() for the current corpus generation — cleared
        automatically the instant rebuild() runs (ingest or restart), so
        this can never serve a result older than the data it's derived from.
        Only used for endpoints that are (a) pure functions of docs/graph/
        compliance/assets and (b) expensive enough to matter — lessons scans
        every document body with several regexes, evaluation re-runs the
        full gold-set ablation. Endpoints that also read live telemetry
        (alerts, deviations, qms/ncr) deliberately do NOT use this — caching
        them would freeze the "live conditions" signal the SSE work above
        exists to stream."""
        hit = self._cache.get(key)
        if hit and hit[0] == self.generation:
            return hit[1]
        result = compute_fn()
        self._cache[key] = (self.generation, result)
        return result

    def add_document(self, doc):
        """Append with a collision-safe id, then incrementally fold it into
        the live graph/index — no existing document is re-tokenised,
        re-embedded, or re-scanned by a regex a second time (see
        graph.KnowledgeGraph.add_document, search.HybridIndex.add_document,
        embeddings.SemanticIndex.add_chunks). This is the fix for the
        "full rebuild on every ingest" bottleneck named in ARCHITECTURE.md
        §10/§12 — at large corpus size, re-parsing every existing
        document's text on every single upload is what stops working, and
        this is what stops doing that. Equivalence with a full rebuild
        (same nodes, same edges, same lexical retrieval results) is proven
        directly in tests/test_incremental.py, not just asserted here.

        Copy-then-mutate-then-swap, exactly like rebuild() below: `copy()`
        on the graph/index is cheap (dict/set copying, O(existing V+E) —
        not O(document text)), and doing the actual add_document() calls
        on the *copies* before swapping self.graph/self.index at the end
        preserves rebuild()'s "a concurrent reader never observes a half-
        updated graph or index" guarantee. Mutating self.graph/self.index
        in place instead would have silently reintroduced exactly the
        torn-read risk that guarantee exists to prevent.

        Compliance and maintenance are still recomputed over the whole
        corpus on every call — both are O(docs) regex/date scans over
        already-parsed text, not O(chunks × tokens) work, and a new
        document can change ANY existing finding (e.g. newly satisfying a
        previously no_evidence requirement), not only add one — so unlike
        the graph/index, there is no safe partial update for them, only a
        cheap-enough full one.
        """
        with self._lock:
            t0 = time.perf_counter()
            existing = {d.id for d in self.docs}
            base_id, n = doc.id, 1
            while doc.id in existing:
                n += 1
                doc.id = f"{base_id}-{n}"
            # doc.meta["id"] must track a collision rename too — GET
            # /api/documents/{id} returns doc.meta verbatim, and it's what
            # gets round-tripped back to disk (ingest.save_document_to_corpus);
            # left stale, both would disagree with the actual doc.id.
            doc.meta["id"] = doc.id
            known_ids = existing | {doc.id}

            new_graph = self.graph.copy()
            # existing_docs=self.docs: an already-ingested document's text
            # can name this new one before it arrives (e.g. an older
            # inspection report that already says "see upcoming work order
            # WO-2734") — this is what retroactively creates that
            # "references" edge instead of losing it. Found and fixed via
            # tests/test_state_incremental.py, not assumed unnecessary.
            new_graph.add_document(doc, known_ids, existing_docs=self.docs)
            new_index = self.index.copy()
            new_index.add_document(doc, new_graph)
            new_docs = self.docs + [doc]
            new_compliance = compliance_engine.evaluate(new_docs)
            new_assets = maintenance.build_assets(new_docs, new_compliance)
            build_ms = round((time.perf_counter() - t0) * 1000, 1)

            self.docs = new_docs
            self.graph = new_graph
            self.index = new_index
            self.compliance = new_compliance
            self.assets = new_assets
            self.build_ms = build_ms
            self.generation += 1
            self._cache.clear()
            logger.info(
                "incremental add: %d docs, %d chunks, %d graph nodes / %d edges in %.1fms (doc=%s)",
                len(new_docs), len(new_index.chunks), len(new_graph.nodes), len(new_graph.edges),
                build_ms, doc.id,
            )
        return doc


STATE = State()


def startup():
    """Load the seed corpus into STATE. Called from the `lifespan` handler
    above on real app startup; kept as a plain callable (not an
    @app.on_event, which FastAPI deprecated in favour of lifespan handlers)
    so scripts and tests can also call it directly without spinning up ASGI
    lifespan machinery."""
    STATE.rebuild(load_corpus(CORPUS_DIR))
    logger.info("startup complete: %d seed documents loaded from %s", len(STATE.docs), CORPUS_DIR)


def _doc_summary(doc) -> dict:
    return {
        "id": doc.id, "title": doc.title, "type": doc.type, "type_label": doc.type_label,
        "date": doc.date, "author": doc.author, "unit": doc.meta.get("unit", ""),
        "entity_counts": {k: len(v) for k, v in doc.entities.items() if v},
    }


@app.get("/api/health")
def health():
    sem = STATE.index.semantic
    return {
        "status": "ok",
        "uptime_s": round(time.time() - _STARTED_AT, 1),
        "documents": len(STATE.docs),
        "graph_nodes": len(STATE.graph.nodes),
        "graph_edges": len(STATE.graph.edges),
        "llm_mode": rag._LLM is not None,
        "ocr_available": ocr.available(),
        "vision_available": vision.available(),
        "auth_enabled": bool(API_KEYS),
        "read_auth_required": REQUIRE_READ_AUTH,
        "roles_configured": sorted(set(API_KEYS.values())),
        "semantic_backend": "faiss-hnsw" if (sem and sem.faiss_index is not None) else "brute-force",
        "semantic_warm_started": bool(sem and sem.from_cache),
        "alert_webhook_configured": alerts_engine.webhook_configured(),
        "agent_available": agent_engine.available(),
    }


def _pctile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return round(sorted_vals[idx], 2)


@app.get("/api/metrics")
def metrics():
    """Prometheus text exposition format (no exporter dependency needed —
    any standard Prometheus-compatible collector can scrape this directly).
    Covers corpus/graph size, compliance score, copilot and HTTP request
    latency, and per-route request counts."""
    lines = []

    def gauge(name: str, help_text: str, value):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")

    gauge("atlas_uptime_seconds", "Process uptime in seconds", round(time.time() - _STARTED_AT, 1))
    gauge("atlas_documents_total", "Documents in the corpus", len(STATE.docs))
    gauge("atlas_chunks_total", "Indexed retrieval chunks", len(STATE.index.chunks))
    gauge("atlas_graph_nodes_total", "Knowledge graph nodes", len(STATE.graph.nodes))
    gauge("atlas_graph_edges_total", "Knowledge graph edges", len(STATE.graph.edges))
    gauge("atlas_generation", "Corpus rebuild generation counter (bumped on every ingest/restart)", STATE.generation)
    gauge("atlas_compliance_score", "Current compliance score, 0-100", STATE.compliance.get("score", 0))

    if STATE.query_latencies:
        lat = sorted(STATE.query_latencies)
        gauge("atlas_copilot_query_latency_ms_avg", "Average /api/ask latency (ms)", round(sum(lat) / len(lat), 2))
        gauge("atlas_copilot_query_latency_ms_p95", "p95 /api/ask latency (ms)", _pctile(lat, 0.95))
    if _REQUEST_DURATIONS_MS:
        dur = sorted(_REQUEST_DURATIONS_MS)
        gauge("atlas_http_request_duration_ms_avg", "Average HTTP request duration (ms)", round(sum(dur) / len(dur), 2))
        gauge("atlas_http_request_duration_ms_p95", "p95 HTTP request duration (ms)", _pctile(dur, 0.95))

    lines.append("# HELP atlas_http_requests_total Total HTTP requests handled, by method/route/status")
    lines.append("# TYPE atlas_http_requests_total counter")
    for (method, path, status), count in sorted(_REQUEST_COUNTS.items()):
        lines.append(f'atlas_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/api/stats")
def stats():
    entity_totals = Counter()
    unique = {"equipment": set(), "standard": set(), "person": set(), "failure_mode": set()}
    for doc in STATE.docs:
        for etype, counter in doc.entities.items():
            entity_totals[etype] += sum(counter.values())
            if etype in unique:
                unique[etype] |= set(counter)
    plant = maintenance.plant_summary(STATE.assets)
    avg_latency = (round(sum(STATE.query_latencies) / len(STATE.query_latencies), 1)
                   if STATE.query_latencies else None)
    return {
        "documents": len(STATE.docs),
        "chunks": len(STATE.index.chunks),
        "graph_nodes": len(STATE.graph.nodes),
        "graph_edges": len(STATE.graph.edges),
        "entity_mentions": sum(entity_totals.values()),
        "unique_entities": {k: len(v) for k, v in unique.items()},
        "compliance_score": STATE.compliance["score"],
        "open_gaps": STATE.compliance["counts"]["gap"],
        "assets_at_risk": plant["assets_at_risk"],
        "total_downtime_hours": plant["total_downtime_hours"],
        "total_cost_inr": plant["total_cost_inr"],
        "downtime_by_month": plant["downtime_by_month"],
        "index_build_ms": STATE.build_ms,
        "avg_query_ms": avg_latency,
        "llm_mode": rag._LLM is not None,
    }


@app.get("/api/documents")
def documents():
    return [_doc_summary(d) for d in sorted(STATE.docs, key=lambda d: d.date, reverse=True)]


@app.get("/api/documents/{doc_id}")
def document(doc_id: str):
    for doc in STATE.docs:
        if doc.id == doc_id:
            linked = STATE.graph.docs_linked_to_entity(f"doc:{doc.id}")
            return {
                **_doc_summary(doc),
                "body": doc.body,
                "meta": doc.meta,
                "entities": {k: dict(v) for k, v in doc.entities.items() if v},
                "linked_docs": sorted(linked),
            }
    raise HTTPException(404, f"document {doc_id} not found")


class AskRequest(BaseModel):
    question: str
    context: str | None = None      # previous question, for follow-ups
    # Metadata filter — a genuine pre-filter applied inside retrieval
    # (search.py: HybridIndex.query), not a trim of the answer afterward.
    doc_types: list[str] | None = None
    date_from: str | None = None    # ISO 8601, inclusive
    date_to: str | None = None      # ISO 8601, inclusive


@app.post("/api/ask")
def ask(req: AskRequest):
    result = rag.answer(
        req.question, STATE.index, STATE.index.docs_by_id, context=req.context,
        doc_types=set(req.doc_types) if req.doc_types else None,
        date_from=req.date_from, date_to=req.date_to,
    )
    STATE.query_latencies.append(result["latency_ms"])
    return result


@app.get("/api/ask/stream")
async def ask_stream(request: Request, question: str, context: str | None = None,
                     doc_types: str | None = None, date_from: str | None = None, date_to: str | None = None):
    """SSE counterpart to POST /api/ask. GET (not POST) so the browser's
    native EventSource can consume it directly — same reason /api/stream/*
    are GET. Emits {"type":"delta","text":...} frames as Claude generates
    the answer (when Claude is configured and the retrieval is grounded),
    then exactly one {"type":"final", ...} frame carrying the same shape
    POST /api/ask returns. When there's nothing to stream (extractive mode,
    or an ungrounded query), the extractive answer — already computed
    instantly — arrives as that one final frame; no fake incremental replay
    of a string that was never generated incrementally.

    `doc_types` is comma-separated (query strings don't have a native list
    shape) — same metadata filter POST /api/ask takes as a JSON list."""
    types_set = {t.strip() for t in doc_types.split(",") if t.strip()} if doc_types else None
    async def gen():
        async for event in rag.stream_answer(question, STATE.index, STATE.index.docs_by_id, context=context,
                                             doc_types=types_set, date_from=date_from, date_to=date_to):
            if await request.is_disconnected():
                break
            if event["type"] == "final":
                STATE.query_latencies.append(event["latency_ms"])
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


class AgentAskRequest(BaseModel):
    question: str


@app.post("/api/agent/ask")
async def agent_ask(req: AgentAskRequest):
    """Genuine agentic orchestration — distinct from /api/ask: here Claude
    plans which of get_compliance_gaps / get_asset_health / search_documents
    / get_fleet_patterns / get_roi_summary / get_pm_schedule to call, in
    what order, based on the question (see agent.py's module docstring for
    why this isn't just rag.py renamed). Each tool call is a real read
    against live STATE, so a full run is CPU/IO-bound across multiple engine
    calls plus network round-trips to Claude — run in a worker thread so it
    never blocks the event loop, same reasoning as ingest() below."""
    result = await asyncio.to_thread(agent_engine.run_agent, req.question, STATE)
    if result is None:
        raise HTTPException(503, "Agent unavailable — set GEMINI_API_KEY to enable it (see README).")
    return result


@app.get("/api/graph")
def graph(focus: str | None = None, depth: int = 2):
    if focus:
        if focus not in STATE.graph.nodes:
            raise HTTPException(404, f"node {focus} not found")
        return STATE.graph.subgraph(focus, depth)
    return STATE.graph.to_json()


@app.get("/api/assets")
def assets():
    return STATE.assets


@app.get("/api/assets/{tag}")
def asset(tag: str):
    for a in STATE.assets:
        if a["tag"] == tag:
            return a
    raise HTTPException(404, f"asset {tag} not found")


@app.get("/api/compliance")
def compliance():
    return STATE.compliance


@app.get("/api/lessons")
def lessons():
    return STATE.cached("lessons", lambda: lessons_analyze(STATE.docs, STATE.graph, STATE.compliance, STATE.assets))


@app.get("/api/telemetry")
def telemetry_feed(tag: str | None = None):
    return telemetry.snapshot([tag] if tag else None)


async def _sse_stream(request: Request, poll_fn, interval_s: float):
    """Shared SSE loop: re-evaluate `poll_fn()` on an interval, push a new
    `data:` frame only when the payload actually changed (a `:heartbeat`
    comment line otherwise, so proxies/browsers don't time the connection
    out), and stop cleanly the moment the client disconnects rather than
    looping forever server-side. This is a genuine push transport — the
    client holds one open connection instead of re-issuing a full HTTP
    request every few seconds (what Assets.jsx/Alerts.jsx did before) — not
    server-side polling relabelled as streaming."""
    last_payload = None
    try:
        while True:
            if await request.is_disconnected():
                break
            payload = json.dumps(poll_fn())
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        pass  # client disconnected mid-sleep — exit quietly, nothing to clean up


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


@app.get("/api/stream/telemetry")
async def stream_telemetry(request: Request, tag: str | None = None):
    return StreamingResponse(
        _sse_stream(request, lambda: telemetry.snapshot([tag] if tag else None), interval_s=2.0),
        media_type="text/event-stream", headers=_SSE_HEADERS,
    )


@app.get("/api/stream/alerts")
async def stream_alerts(request: Request):
    def poll():
        lessons_result = STATE.cached("lessons", lambda: lessons_analyze(STATE.docs, STATE.graph, STATE.compliance, STATE.assets))
        result = alerts_engine.build(
            lessons_result, quality.evaluate(STATE.docs, STATE.assets), STATE.compliance, telemetry,
        )
        # Real outbound delivery, tied to the live alert stream rather than
        # the on-demand GET below. dispatch_new() no-ops (no network call at
        # all) past the first tick for any alert already sent — disk-
        # persisted dedup — so in steady state this thread does a dict scan,
        # not a request. Fired on a background thread rather than awaited
        # inline: this poll() runs synchronously on the single event-loop
        # thread (see _sse_stream), so a blocking urlopen() here on a new
        # alert would stall every other concurrent request, not just this
        # connection, for up to _WEBHOOK_TIMEOUT_S.
        threading.Thread(target=alerts_engine.dispatch_new, args=(result,), daemon=True).start()
        return result
    return StreamingResponse(_sse_stream(request, poll, interval_s=3.0),
                             media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/schedule")
def pm_schedule():
    return STATE.cached("schedule", lambda: schedule.build(STATE.assets, STATE.docs, STATE.compliance))


@app.get("/api/deviations")
def deviations():
    return quality.evaluate(STATE.docs, STATE.assets)


@app.get("/api/alerts")
def alerts():
    # lessons is generation-cached (see lessons() above) and reused here
    # rather than recomputed — but quality.evaluate() reads live telemetry
    # breaches, so the alerts result as a whole is deliberately NOT cached.
    lessons_result = STATE.cached("lessons", lambda: lessons_analyze(STATE.docs, STATE.graph, STATE.compliance, STATE.assets))
    return alerts_engine.build(
        lessons_result, quality.evaluate(STATE.docs, STATE.assets), STATE.compliance, telemetry,
    )


@app.post("/api/alerts/{alert_id}/ack", dependencies=[Depends(require_operator)])
def ack_alert(alert_id: str, actor: str = Depends(get_actor)):
    alerts_engine.acknowledge(alert_id, by=actor)
    audit_engine.log_action(actor, "operator", "alert.ack", alert_id)
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/unack", dependencies=[Depends(require_operator)])
def unack_alert(alert_id: str, actor: str = Depends(get_actor)):
    alerts_engine.unacknowledge(alert_id)
    audit_engine.log_action(actor, "operator", "alert.unack", alert_id)
    return {"ok": True}


@app.post("/api/alerts/webhook-test", dependencies=[Depends(require_operator)])
def alerts_webhook_test(actor: str = Depends(get_actor)):
    """Sends one synthetic payload to the configured webhook immediately —
    lets an operator confirm delivery actually works without waiting for a
    genuine alert. Runs in a worker thread (see ingest()) since this is a
    real, potentially slow network call in an otherwise sync route."""
    audit_engine.log_action(actor, "operator", "alert.webhook_test", "")
    return alerts_engine.send_test_webhook()


@app.get("/api/roi")
def roi_impact():
    return roi.compute(STATE.docs)


@app.get("/api/benchmark")
def benchmark(n: int = 5000):
    n = max(100, min(n, 20000))
    return bench_engine.run(n)


@app.get("/api/evaluation")
def evaluation_report():
    from . import evaluation
    # By far the most expensive derived endpoint — re-runs the full gold-set
    # ablation (multiple retrieval passes per question) — and was being
    # recomputed on every Dashboard page load via EvalCard.
    return STATE.cached("evaluation", lambda: evaluation.run(STATE.index, STATE.docs, STATE.graph, STATE.compliance))


@app.get("/api/ontology")
def ontology_view():
    return STATE.cached("ontology", lambda: ontology.build(STATE.docs, STATE.graph))


@app.get("/api/qms/ncr")
def qms_ncr():
    return qms.export_json(quality.evaluate(STATE.docs, STATE.assets), STATE.compliance)


@app.get("/api/qms/ncr.csv")
def qms_ncr_csv():
    from fastapi.responses import Response
    body = qms.export_csv(quality.evaluate(STATE.docs, STATE.assets), STATE.compliance)
    return Response(content=body, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=atlas-ncr-export.csv"})


def _absorb_pid(result: dict, doc_id: str, title: str) -> dict:
    """Fold a digitised drawing's tags + connectivity into the corpus/graph
    so the frontend's "becomes a connected_to edge in the knowledge graph"
    claim (Drawings.jsx) is actually true. No-op (graph_updated: False) when
    the CV pipeline found no tags — an empty/failed parse shouldn't create a
    document with nothing in it."""
    tags = result.get("tags_found") or []
    if not tags:
        result["graph_updated"] = False
        return result
    body = vision.pid_to_document_body(result, result.get("source", doc_id))
    meta = {"id": doc_id, "title": title, "type": "drawing", "equipment": ",".join(tags)}
    doc = load_document(meta, body, fallback_id=doc_id, known_doc_ids={d.id for d in STATE.docs})
    before_nodes, before_edges = len(STATE.graph.nodes), len(STATE.graph.edges)
    STATE.add_document(doc)
    persisted_path = save_document_to_corpus(doc, CORPUS_DIR)
    result["graph_updated"] = True
    result["graph_doc_id"] = doc.id
    result["new_graph_nodes"] = len(STATE.graph.nodes) - before_nodes
    result["new_graph_edges"] = len(STATE.graph.edges) - before_edges
    result["persisted"] = persisted_path is not None
    return result


@app.get("/api/vision/sample-pid")
def vision_sample_image():
    from fastapi.responses import Response
    return Response(content=sample_pid.render_png(), media_type="image/png")


@app.get("/api/vision/parse-sample")
def vision_parse_sample():
    result = vision.parse_pid(sample_pid.render_png())
    result["source"] = "sample P&ID (DWG-300-001 style)"
    # Idempotent: the sample preview is fetched on every Drawings page load,
    # so only absorb it into the graph once rather than spawning a new
    # document on every visit.
    if any(d.id == "DWG-300-001-CV" for d in STATE.docs):
        result["graph_updated"] = False
        result["graph_doc_id"] = "DWG-300-001-CV"
        return result
    return _absorb_pid(result, "DWG-300-001-CV", "P&ID digitisation — Unit 300 sample drawing")


@app.post("/api/vision/parse")
async def vision_parse(file: UploadFile, request: Request,
                       actor: str = Depends(get_actor), role: str = Depends(get_role)):
    if not _INGEST_LIMITER.allow((request.client.host if request.client else None) or "unknown"):
        raise HTTPException(429, "Too many uploads from this client — try again shortly")
    _reject_dangerous_extension(file.filename or "")
    data = await _read_limited(file)
    result = vision.parse_pid(data)
    result["source"] = file.filename
    fallback_id = (file.filename or "PID-UPLOAD").rsplit(".", 1)[0].upper().replace(" ", "-") + "-CV"
    result = await asyncio.to_thread(_absorb_pid, result, fallback_id, f"P&ID digitisation — {file.filename}")
    if result.get("graph_updated"):
        audit_engine.log_action(actor, role, "vision.parse", file.filename or "")
    return result


@app.get("/api/supported-formats")
def supported_formats():
    return {"extensions": sorted(SUPPORTED.keys()), "ocr_available": ocr.available(),
            "vision_available": vision.available()}


@app.post("/api/ingest", dependencies=[Depends(require_operator)])
async def ingest(file: UploadFile, request: Request, actor: str = Depends(get_actor)):
    if not _INGEST_LIMITER.allow((request.client.host if request.client else None) or "unknown"):
        raise HTTPException(429, "Too many uploads from this client — try again in a minute")
    filename = file.filename or "upload.txt"
    _reject_dangerous_extension(filename)
    data = await _read_limited(file)

    extra_meta, body, fmt = read_any(filename, data)
    # Markdown/plain-text bodies may carry a YAML frontmatter block
    fm_meta, body = parse_frontmatter(body) if fmt in ("markdown", "text") else ({}, body)
    meta = {**extra_meta, **fm_meta}  # explicit frontmatter overrides format-inferred meta
    fallback_id = filename.rsplit(".", 1)[0].upper().replace(" ", "-") or "UPLOAD"
    doc = load_document(meta, body, fallback_id=fallback_id, known_doc_ids={d.id for d in STATE.docs})

    t0 = time.perf_counter()
    # Full rebuild is CPU-bound (O(N) over the whole corpus, not just the new
    # doc — see ARCHITECTURE.md §12); running it in a worker thread keeps the
    # event loop free to serve other requests while a large corpus reindexes.
    await asyncio.to_thread(STATE.add_document, doc)
    # Write the accepted document back to disk so it survives a restart —
    # previously uploads lived only in process memory (ARCHITECTURE.md §11).
    # Best-effort: a disk failure here doesn't undo the in-memory ingest,
    # it just means this one document won't survive a restart; `persisted`
    # in the response tells the caller which happened rather than staying
    # silent about it.
    persisted_path = await asyncio.to_thread(save_document_to_corpus, doc, CORPUS_DIR)
    logger.info("ingested %s (%s, %d chars) as document %s%s", filename, fmt, len(doc.body), doc.id,
               "" if persisted_path else " (NOT persisted to disk)")
    audit_engine.log_action(actor, "operator", "ingest", f"{doc.id} ({fmt}, {filename})")
    return {
        "doc": _doc_summary(doc),
        "format": fmt,
        "chars_extracted": len(doc.body),
        "entities": {k: dict(v) for k, v in doc.entities.items() if v},
        "new_graph_nodes": len(STATE.graph.nodes),
        "new_graph_edges": len(STATE.graph.edges),
        "reindex_ms": round((time.perf_counter() - t0) * 1000, 1),
        "persisted": persisted_path is not None,
    }


@app.get("/api/audit", dependencies=[Depends(require_operator)])
def audit_log(limit: int = 200):
    """Named-key audit trail for every mutating action (ingest, alert ack/
    unack, webhook test, vision-parse absorb) — most recent first. Operator-
    gated: an audit trail that anyone could read would defeat part of its
    own purpose. See audit.py for what this is and, just as importantly,
    what it isn't (a per-user identity/SSO system)."""
    return {"entries": audit_engine.recent(limit)}


@app.get("/api/compliance/evidence-pack")
def evidence_pack():
    from fastapi.responses import HTMLResponse
    html = build_evidence_pack(STATE.compliance, STATE.docs)
    return HTMLResponse(content=html)
