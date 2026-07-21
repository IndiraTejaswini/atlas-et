import { useState } from "react";
import { api } from "../api.js";
import { Card, PageHeader, Badge } from "../components/ui.jsx";

const SUGGESTIONS = [
  "What should Rotating Equipment prioritise this week?",
  "Which asset has the worst combination of health and open compliance gaps?",
  "Where is the biggest avoidable-cost opportunity right now, and what would close it?",
  "Summarise the overdue statutory items and who they affect.",
];

const TOOL_META = {
  get_compliance_gaps: { label: "Compliance gaps", icon: "❖", color: "var(--c2)" },
  get_asset_health: { label: "Asset health", icon: "⚙", color: "var(--c6)" },
  search_documents: { label: "Document search", icon: "⌕", color: "var(--brand)" },
  get_fleet_patterns: { label: "Fleet patterns", icon: "◈", color: "var(--c7)" },
  get_roi_summary: { label: "ROI summary", icon: "◆", color: "var(--c4)" },
  get_pm_schedule: { label: "PM schedule", icon: "▤", color: "var(--c1)" },
};

function argsSummary(args) {
  if (!args || Object.keys(args).length === 0) return null;
  return Object.entries(args).map(([k, v]) => `${k}: ${v}`).join(", ");
}

function TraceStep({ step, n }) {
  const meta = TOOL_META[step.tool] || { label: step.tool, icon: "●", color: "var(--ink-3)" };
  const summary = argsSummary(step.args);
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center shrink-0">
        <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: meta.color }}>
          {n}
        </span>
        <span className="flex-1 w-px my-1" style={{ background: "var(--line-1)" }} />
      </div>
      <div className="pb-4 min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span>{meta.icon}</span>
          <span className="text-sm font-semibold" style={{ color: "var(--ink-1)" }}>{meta.label}</span>
          <span className="font-mono text-[11px]" style={{ color: "var(--ink-3)" }}>{step.tool}()</span>
        </div>
        {summary && <div className="text-xs mt-0.5 font-mono" style={{ color: "var(--ink-3)" }}>{summary}</div>}
        <div className="text-xs mt-1.5 p-2.5 rounded-[8px] font-mono leading-relaxed break-words" style={{ background: "var(--surface-inset)", color: "var(--ink-2)" }}>
          {step.result_preview}
        </div>
      </div>
    </div>
  );
}

function AnswerBody({ text }) {
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("* ");
        const content = line.replace(/^[-*]\s/, "").replace(/\*\*(.+?)\*\*/g, "$1");
        return (
          <div key={i} className={isBullet ? "flex gap-2.5 text-[15px] leading-relaxed" : "text-[15px] leading-relaxed"} style={{ color: "var(--ink-2)" }}>
            {isBullet && <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--brand)" }} />}
            <span>{content}</span>
          </div>
        );
      })}
    </div>
  );
}

function ResultBlock({ result }) {
  return (
    <Card className="p-6 animate-in">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <Badge color="var(--brand-strong)" wash="var(--brand-wash)">✳ Agent plan</Badge>
        <span className="text-xs" style={{ color: "var(--ink-3)" }}>
          {result.iterations} tool call{result.iterations === 1 ? "" : "s"}
          {result.truncated && " · hit the planning limit"}
        </span>
      </div>

      {result.trace.length > 0 && (
        <div className="mb-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>
            Plan trace — what it decided to check, in order
          </div>
          {result.trace.map((step, i) => <TraceStep key={i} step={step} n={i + 1} />)}
        </div>
      )}

      <div className="pt-4 border-t" style={{ borderColor: "var(--line-1)" }}>
        <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>Answer</div>
        <AnswerBody text={result.answer} />
      </div>
    </Card>
  );
}

function Unavailable() {
  return (
    <Card className="p-6 text-center">
      <div className="text-3xl mb-3 opacity-50">✳</div>
      <div className="font-semibold" style={{ color: "var(--ink-1)" }}>Agent unavailable</div>
      <p className="text-sm mt-1.5 max-w-md mx-auto" style={{ color: "var(--ink-3)" }}>
        Unlike the Copilot's retrieval, planning across tools has no honest offline fallback — it
        needs an LLM. Set a key (<code className="font-mono px-1 rounded" style={{ background: "var(--surface-2)" }}>GROQ_API_KEY</code> — free at console.groq.com) on
        the backend and restart (see README) to enable it.
      </p>
    </Card>
  );
}

export default function Agent() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState(false);

  async function submit(q) {
    const query = (q ?? question).trim();
    if (!query || loading) return;
    setLoading(true);
    setResult(null);
    setUnavailable(false);
    setError(false);
    try {
      const r = await api.agentAsk(query);
      setResult(r);
    } catch (e) {
      if (e.status === 503) setUnavailable(true);
      else setError(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Agentic AI · Maintenance & Compliance Planning"
        title="Ask the planning agent"
        subtitle="Distinct from the Copilot: here the model decides for itself which of the plant's live tools to call — compliance, asset health, ROI, PM schedule, document search — and in what order, then answers from what it found. Real orchestration, not a fixed pipeline."
      />

      <Card className="p-2 mb-4" style={{ boxShadow: "var(--shadow-2)" }}>
        <div className="flex items-center gap-2">
          <span className="pl-3 text-lg" style={{ color: "var(--ink-3)" }}>✳</span>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. What should Rotating Equipment prioritise this week?"
            className="flex-1 py-3 text-[15px] bg-transparent outline-none"
            style={{ color: "var(--ink-1)" }}
          />
          <button
            onClick={() => submit()}
            disabled={loading || !question.trim()}
            className="px-5 py-2.5 rounded-[10px] text-sm font-semibold text-white transition-all disabled:opacity-40"
            style={{ background: "var(--brand)" }}
          >
            {loading ? "Planning…" : "Ask"}
          </button>
        </div>
      </Card>

      {!result && !loading && !unavailable && !error && (
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

      {loading && (
        <Card className="p-6">
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--ink-3)" }}>
            <span className="w-2 h-2 rounded-full pulse" style={{ background: "var(--brand)" }} />
            Planning which tools to call…
          </div>
        </Card>
      )}

      {unavailable && <Unavailable />}
      {error && <Card className="p-5 text-sm" style={{ color: "var(--critical)" }}>Could not reach the agent service.</Card>}
      {result && <ResultBlock result={result} />}
    </>
  );
}
