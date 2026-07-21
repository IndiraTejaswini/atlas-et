const BASE = "/api";

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => get("/health"),
  stats: () => get("/stats"),
  documents: () => get("/documents"),
  document: (id) => get(`/documents/${encodeURIComponent(id)}`),
  graph: (focus, depth = 2) =>
    get(`/graph${focus ? `?focus=${encodeURIComponent(focus)}&depth=${depth}` : ""}`),
  assets: () => get("/assets"),
  asset: (tag) => get(`/assets/${encodeURIComponent(tag)}`),
  compliance: () => get("/compliance"),
  lessons: () => get("/lessons"),
  roi: () => get("/roi"),
  evaluation: () => get("/evaluation"),
  ontology: () => get("/ontology"),
  qmsNcr: () => get("/qms/ncr"),
  qmsCsvUrl: () => BASE + "/qms/ncr.csv",
  parseSamplePid: () => get("/vision/parse-sample"),
  samplePidUrl: () => BASE + "/vision/sample-pid",
  parsePid: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(BASE + "/vision/parse", { method: "POST", body: form });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
  },
  benchmark: (n = 5000) => get(`/benchmark?n=${n}`),
  telemetry: (tag) => get(`/telemetry${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`),
  // Real push transport (Server-Sent Events) — one held-open connection that
  // the server writes new frames into, instead of the client re-issuing a
  // full HTTP request every few seconds. EventSource auto-reconnects on
  // drop and ignores the server's `: heartbeat` comment lines automatically
  // (SSE spec: lines starting with `:` never fire onmessage). Returns an
  // unsubscribe function for the caller's useEffect cleanup.
  streamTelemetry: (tag, onData) => {
    const url = BASE + `/stream/telemetry${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`;
    const es = new EventSource(url);
    es.onmessage = (e) => onData(JSON.parse(e.data));
    return () => es.close();
  },
  streamAlerts: (onData) => {
    const es = new EventSource(BASE + "/stream/alerts");
    es.onmessage = (e) => onData(JSON.parse(e.data));
    return () => es.close();
  },
  schedule: () => get("/schedule"),
  deviations: () => get("/deviations"),
  alerts: () => get("/alerts"),
  ackAlert: (id) => fetch(`${BASE}/alerts/${id}/ack`, { method: "POST" }).then((r) => r.json()),
  unackAlert: (id) => fetch(`${BASE}/alerts/${id}/unack`, { method: "POST" }).then((r) => r.json()),
  testAlertWebhook: () => fetch(`${BASE}/alerts/webhook-test`, { method: "POST" }).then((r) => r.json()),
  supportedFormats: () => get("/supported-formats"),
  evidencePackUrl: () => BASE + "/compliance/evidence-pack",
  ask: async (question, context = null, filters = null) => {
    const res = await fetch(BASE + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, context, ...filters }),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
  },
  // Streams {type:"delta",text} frames as the model generates the answer, then
  // exactly one {type:"final", answer, citations, confidence, mode, trace,
  // ...} frame — same shape ask() returns, so callers can treat the final
  // event as the complete result. When no LLM is configured (or the
  // query isn't grounded), the extractive answer arrives as that one final
  // frame with no deltas — never a fake incremental replay. `filters` is
  // an optional {doc_types: string[], date_from, date_to} metadata filter,
  // applied inside retrieval itself, not trimmed from the results after.
  askStream: (question, context, onEvent, onError, filters = null) => {
    const params = new URLSearchParams({ question });
    if (context) params.set("context", context);
    if (filters?.doc_types?.length) params.set("doc_types", filters.doc_types.join(","));
    if (filters?.date_from) params.set("date_from", filters.date_from);
    if (filters?.date_to) params.set("date_to", filters.date_to);
    const es = new EventSource(`${BASE}/ask/stream?${params}`);
    let done = false;
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "final") { done = true; es.close(); }
      onEvent(data);
    };
    es.onerror = () => {
      es.close();
      if (!done) onError?.();
    };
    return () => es.close();
  },
  agentAsk: async (question) => {
    const res = await fetch(BASE + "/agent/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      const err = new Error(`${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  },
  ingest: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(BASE + "/ingest", { method: "POST", body: form });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
  },
};
