import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Card, PageHeader, DocTypeBadge, Badge, docTypeMeta } from "../components/ui.jsx";

const FILTERABLE_TYPES = ["drawing", "datasheet", "oem_manual", "procedure", "work_order",
                          "inspection", "incident", "memo", "regulatory", "email"];

const SUGGESTIONS = [
  "Why does P-101A keep failing?",
  "What are the pre-start checks for the crude charge pumps?",
  "Which relief valves are overdue for testing?",
  "What did the crude slate change cause?",
  "What are the confined space entry requirements for V-302?",
  "Show the failure history of exchanger E-104",
];

const NODE_COLOR = {
  equipment: "var(--c6)", failure_mode: "var(--c8)", document: "var(--c1)",
  standard: "var(--c2)", person: "var(--c7)",
};

/* Renders WHY a source surfaced: the graph path from the query's entity to
   the document, e.g.  P-101A ─exhibits→ Mechanical seal failure ─describes→ OEM manual */
function GraphPath({ path }) {
  if (!path?.length) return null;
  const nodes = [{ label: path[0].from, type: path[0].from_type },
                 ...path.map((h) => ({ label: h.to, type: h.to_type }))];
  return (
    <div className="flex items-center gap-1.5 flex-wrap mt-2 pt-2 border-t" style={{ borderColor: "var(--line-1)" }}>
      <span className="text-[10px] font-semibold uppercase tracking-wider mr-1" style={{ color: "var(--ink-3)" }}>
        why
      </span>
      {nodes.map((n, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && (
            <span className="flex items-center gap-1 text-[10px]" style={{ color: "var(--ink-3)" }}>
              <span>─</span>
              <span className="italic">{path[i - 1].relation}</span>
              <span>→</span>
            </span>
          )}
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium"
            style={{ background: "var(--surface-2)", color: "var(--ink-1)" }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: NODE_COLOR[n.type] || "var(--ink-3)" }} />
            {n.label}
          </span>
        </span>
      ))}
    </div>
  );
}

function ConfidenceMeter({ value }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "var(--good)" : pct >= 50 ? "var(--warn)" : "var(--serious)";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold" style={{ color: "var(--ink-3)" }}>Confidence</span>
      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="tnum text-xs font-bold" style={{ color }}>{pct}%</span>
    </div>
  );
}

/* Render markdown-ish answer with [n] citation chips */
function AnswerBody({ text, citations }) {
  const byN = Object.fromEntries(citations.map((c) => [c.n, c]));
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        const isBullet = line.trim().startsWith("- ");
        let content = line.replace(/^- /, "");
        const parts = [];
        const regex = /\*\*(.+?)\*\*|\[(\d+)\]/g;
        let last = 0, m;
        while ((m = regex.exec(content))) {
          if (m.index > last) parts.push(content.slice(last, m.index));
          if (m[1] !== undefined) parts.push(<strong key={parts.length} style={{ color: "var(--ink-1)" }}>{m[1]}</strong>);
          else {
            const c = byN[m[2]];
            parts.push(
              c ? (
                <Link
                  key={parts.length}
                  to={`/documents/${encodeURIComponent(c.doc_id)}`}
                  title={c.title}
                  className="inline-flex items-center justify-center align-middle mx-0.5 min-w-[18px] h-[18px] px-1 rounded-[5px] text-[11px] font-bold transition-colors hover:opacity-80"
                  style={{ color: "#fff", background: "var(--brand)" }}
                >
                  {m[2]}
                </Link>
              ) : `[${m[2]}]`
            );
          }
          last = regex.lastIndex;
        }
        if (last < content.length) parts.push(content.slice(last));
        return (
          <div key={i} className={isBullet ? "flex gap-2.5 text-[15px] leading-relaxed" : "text-[15px] leading-relaxed"} style={{ color: "var(--ink-2)" }}>
            {isBullet && <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--brand)" }} />}
            <span>{parts}</span>
          </div>
        );
      })}
    </div>
  );
}

function TraceDisclosure({ trace, latency, mode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 pt-3 border-t" style={{ borderColor: "var(--line-1)" }}>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--ink-3)" }}>
        <span className="transition-transform" style={{ transform: open ? "rotate(90deg)" : "none" }}>▸</span>
        Retrieval trace · {latency}ms · {mode === "llm" ? "AI synthesis" : "extractive"}
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-xs animate-in" style={{ color: "var(--ink-2)" }}>
          <div>
            <span style={{ color: "var(--ink-3)" }}>Query terms: </span>
            {trace.query_terms.join(", ") || "—"}
          </div>
          <div>
            <span style={{ color: "var(--ink-3)" }}>Chunks scanned: </span>
            <span className="tnum">{trace.chunks_considered}</span> → {trace.chunks_returned} returned
          </div>
          <div className="col-span-2">
            <span style={{ color: "var(--ink-3)" }}>Graph-matched entities: </span>
            {trace.matched_entities.length
              ? trace.matched_entities.map((e) => (
                  <Badge key={e.id} color="var(--brand-strong)" wash="var(--brand-wash)" className="mr-1">{e.label}</Badge>
                ))
              : "none"}
          </div>
          {trace.semantic_dims > 0 && (
            <div className="col-span-2">
              <span style={{ color: "var(--ink-3)" }}>Semantic vector signal: </span>
              <Badge color="var(--c7)" wash="#ecebf7" className="mr-1">LSA · {trace.semantic_dims}-dim</Badge>
              {trace.semantic_top && (
                <span>
                  closest by meaning →{" "}
                  <Link to={`/documents/${trace.semantic_top.doc_id}`} className="font-mono font-semibold" style={{ color: "var(--c7)" }}>
                    {trace.semantic_top.doc_id}
                  </Link>{" "}
                  <span style={{ color: "var(--ink-3)" }}>(cos {trace.semantic_top.score}{trace.semantic_top.lexical_miss ? ", keyword-miss" : ""})</span>
                </span>
              )}
            </div>
          )}
          {trace.graph_expanded_docs.length > 0 && (
            <div className="col-span-2">
              <span style={{ color: "var(--ink-3)" }}>Surfaced via graph (shared failure mode): </span>
              {trace.graph_expanded_docs.map((d) => (
                <Link key={d} to={`/documents/${d}`} className="font-mono font-semibold mr-1.5" style={{ color: "var(--brand-strong)" }}>{d}</Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultBlock({ result }) {
  return (
    <Card className="p-6 animate-in">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Badge color="var(--brand-strong)" wash="var(--brand-wash)">✦ Copilot answer</Badge>
          {result.carried_context?.length > 0 && (
            <Badge color="var(--c7)" wash="#ecebf7">
              ↩ follow-up · carried {result.carried_context.join(", ")}
            </Badge>
          )}
          {result.streaming && (
            <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--ink-3)" }}>
              <span className="w-1.5 h-1.5 rounded-full pulse" style={{ background: "var(--brand)" }} />
              streaming…
            </span>
          )}
        </div>
        {typeof result.confidence === "number" && <ConfidenceMeter value={result.confidence} />}
      </div>
      <AnswerBody text={result.answer} citations={result.citations || []} />

      {result.citations?.length > 0 && (
        <div className="mt-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-2.5" style={{ color: "var(--ink-3)" }}>
            Sources ({result.citations.length})
          </div>
          <div className="space-y-2">
            {result.citations.map((c) => (
              <Link
                key={c.n}
                to={`/documents/${encodeURIComponent(c.doc_id)}`}
                className="flex items-start gap-3 p-3 rounded-[10px] border transition-all hover:shadow-[var(--shadow-1)]"
                style={{ borderColor: "var(--line-1)", background: "var(--surface-inset)" }}
              >
                <span
                  className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold text-white"
                  style={{ background: "var(--brand)" }}
                >
                  {c.n}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold truncate" style={{ color: "var(--ink-1)" }}>{c.title}</span>
                    <DocTypeBadge type={c.type} />
                  </div>
                  <div className="text-xs mt-1 line-clamp-2" style={{ color: "var(--ink-3)" }}>{c.snippet}</div>
                  {c.graph_path && <GraphPath path={c.graph_path} />}
                </div>
                <span className="tnum text-[11px] shrink-0" style={{ color: "var(--ink-3)" }}>{c.date}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {result.trace && <TraceDisclosure trace={result.trace} latency={result.latency_ms} mode={result.mode} />}
    </Card>
  );
}

function FilterBar({ open, filters, setFilters }) {
  if (!open) return null;
  const toggleType = (t) => setFilters((f) => ({
    ...f,
    doc_types: f.doc_types.includes(t) ? f.doc_types.filter((x) => x !== t) : [...f.doc_types, t],
  }));
  return (
    <Card className="p-4 mb-4 animate-in">
      <div className="mb-3">
        <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>
          Document type
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERABLE_TYPES.map((t) => {
            const m = docTypeMeta(t);
            const active = filters.doc_types.includes(t);
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className="px-2.5 py-1 rounded-full text-xs font-semibold border transition-all"
                style={active
                  ? { background: m.color, borderColor: "transparent", color: "#fff" }
                  : { background: "var(--surface-1)", borderColor: "var(--line-1)", color: "var(--ink-2)" }}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--ink-3)" }}>From</div>
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
            className="px-2.5 py-1.5 rounded-[8px] border text-sm bg-transparent"
            style={{ borderColor: "var(--line-1)", color: "var(--ink-1)" }}
          />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--ink-3)" }}>To</div>
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
            className="px-2.5 py-1.5 rounded-[8px] border text-sm bg-transparent"
            style={{ borderColor: "var(--line-1)", color: "var(--ink-1)" }}
          />
        </div>
        {(filters.doc_types.length > 0 || filters.date_from || filters.date_to) && (
          <button
            onClick={() => setFilters({ doc_types: [], date_from: "", date_to: "" })}
            className="text-xs font-semibold self-end pb-2"
            style={{ color: "var(--brand-strong)" }}
          >
            Clear filters
          </button>
        )}
      </div>
    </Card>
  );
}

export default function Copilot() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [llmMode, setLlmMode] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState({ doc_types: [], date_from: "", date_to: "" });
  const scrollRef = useRef(null);

  useEffect(() => {
    api.stats().then((s) => setLlmMode(s.llm_mode));
  }, []);

  const activeFilterCount = filters.doc_types.length + (filters.date_from ? 1 : 0) + (filters.date_to ? 1 : 0);

  function submit(q) {
    const query = (q ?? question).trim();
    if (!query || loading) return;
    setQuestion("");
    setLoading(true);
    // Carry the previous turn so follow-ups like "what about the B pump?" resolve
    const priorQuestion = history[0]?.question || null;
    const activeFilters = {
      doc_types: filters.doc_types.length ? filters.doc_types : null,
      date_from: filters.date_from || null,
      date_to: filters.date_to || null,
    };
    setHistory((h) => [{ question: query, result: { answer: "", citations: [], streaming: true } }, ...h]);

    api.askStream(
      query, priorQuestion,
      (event) => {
        if (event.type === "delta") {
          setHistory((h) => h.map((item, i) => (
            i === 0 ? { ...item, result: { ...item.result, answer: item.result.answer + event.text } } : item
          )));
        } else if (event.type === "final") {
          const { type, ...result } = event;
          setHistory((h) => h.map((item, i) => (i === 0 ? { ...item, result } : item)));
          setLoading(false);
        }
      },
      () => {
        // If nothing ever streamed, show the hard error card (matches the
        // pre-streaming "could not reach the service" UX — result must go
        // back to null since ResultBlock is only rendered when it's truthy).
        // If some text already arrived before the drop, keep it rather than
        // discard a partial answer the user already saw.
        setHistory((h) => h.map((item, i) => {
          if (i !== 0) return item;
          return item.result?.answer
            ? { ...item, result: { ...item.result, streaming: false } }
            : { ...item, result: null, error: true };
        }));
        setLoading(false);
      },
      activeFilters,
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Expert Knowledge Copilot"
        title="Ask anything about the plant"
        subtitle="Retrieval-augmented answers grounded in the full document corpus — every claim carries a citation and confidence score, and the graph surfaces documents that never share a keyword."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFiltersOpen((o) => !o)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
              style={filtersOpen || activeFilterCount
                ? { background: "var(--brand-wash)", borderColor: "transparent", color: "var(--brand-strong)" }
                : { background: "var(--surface-1)", borderColor: "var(--line-1)", color: "var(--ink-2)" }}
            >
              ⚗ Filters{activeFilterCount > 0 && ` (${activeFilterCount})`}
            </button>
            <Badge color={llmMode ? "var(--good)" : "var(--ink-2)"} wash={llmMode ? "var(--good-wash)" : "var(--surface-2)"}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: llmMode ? "var(--good)" : "var(--ink-3)" }} />
              {llmMode ? "AI synthesis on" : "Extractive mode"}
            </Badge>
          </div>
        }
      />

      <FilterBar open={filtersOpen} filters={filters} setFilters={setFilters} />

      <Card className="p-2 mb-4" style={{ boxShadow: "var(--shadow-2)" }}>
        <div className="flex items-center gap-2">
          <span className="pl-3 text-lg" style={{ color: "var(--ink-3)" }}>✦</span>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. Why does P-101A keep failing?"
            className="flex-1 py-3 text-[15px] bg-transparent outline-none"
            style={{ color: "var(--ink-1)" }}
          />
          <button
            onClick={() => submit()}
            disabled={loading || !question.trim()}
            className="px-5 py-2.5 rounded-[10px] text-sm font-semibold text-white transition-all disabled:opacity-40"
            style={{ background: "var(--brand)" }}
          >
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </Card>

      {history.length === 0 && (
        <div className="mb-6">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>Try asking</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => submit(s)}
                className="text-left px-4 py-3 rounded-[12px] text-sm border transition-all hover:shadow-[var(--shadow-1)] hover:border-[var(--brand)]"
                style={{ borderColor: "var(--line-1)", background: "var(--surface-1)", color: "var(--ink-2)" }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div ref={scrollRef} className="space-y-4">
        {history.map((item, i) => (
          <div key={i}>
            <div className="flex items-center gap-2.5 mb-2.5">
              <span className="text-sm font-semibold px-3 py-1.5 rounded-full" style={{ background: "var(--surface-2)", color: "var(--ink-1)" }}>
                {item.question}
              </span>
            </div>
            {item.result ? (
              <ResultBlock result={item.result} />
            ) : item.error ? (
              <Card className="p-5 text-sm" style={{ color: "var(--critical)" }}>Could not reach the knowledge service.</Card>
            ) : (
              <Card className="p-6">
                <div className="flex items-center gap-2 text-sm" style={{ color: "var(--ink-3)" }}>
                  <span className="w-2 h-2 rounded-full pulse" style={{ background: "var(--brand)" }} />
                  Retrieving and grounding…
                </div>
              </Card>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
