
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Card, StatusBadge, HealthBar, Skeleton, DocRefLink } from "../components/ui.jsx";

function fmtINR(n) {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function KpiCard({ label, value, sub, accent, to }) {
  const inner = (
    <Card className="relative p-6 h-full flex flex-col justify-between group cursor-pointer overflow-hidden bg-gradient-to-b from-[var(--surface-1)] to-[#0B1121] border border-white/5 hover:border-[var(--brand)]/40 hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)] transition-all duration-500">
      <div className="absolute -bottom-16 -right-16 w-40 h-40 rounded-full opacity-0 group-hover:opacity-20 blur-[50px] transition-opacity duration-700 pointer-events-none" style={{ backgroundColor: accent || "var(--brand)" }} />
      <div className="relative z-10">
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--ink-3)] group-hover:text-white transition-colors duration-300">{label}</div>
        <div className="tnum text-5xl font-extrabold tracking-tighter mt-3 text-transparent bg-clip-text bg-gradient-to-b from-white to-white/70" style={{ filter: accent ? `drop-shadow(0 0 15px ${accent}30)` : 'none' }}>
          {value}
        </div>
      </div>
      <div className="relative z-10 text-xs font-medium mt-6 pt-4 border-t border-white/5 text-[var(--ink-2)] group-hover:text-[var(--ink-1)] transition-colors duration-300 flex items-center justify-between">
        {sub}
        <span className="opacity-0 -translate-x-3 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 text-[var(--brand)]">→</span>
      </div>
    </Card>
  );
  return to ? <Link to={to} className="block h-full outline-none">{inner}</Link> : inner;
}

function DowntimeChart({ data }) {
  if (!data?.length) return null;
  const max = Math.max(...data.map((d) => d.hours), 1);
  const total = data.reduce((s, d) => s + d.hours, 0);
  
  return (
    <Card className="p-6 h-full flex flex-col bg-gradient-to-b from-[var(--surface-1)] to-transparent border border-white/5">
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="font-semibold text-lg text-white tracking-tight">Unplanned Downtime</h3>
        <span className="tnum text-[10px] uppercase tracking-wider font-bold px-3 py-1 bg-[#121C2D] border border-white/10 rounded-full text-[var(--ink-2)] shadow-inner">{total} hrs total</span>
      </div>
      <p className="text-xs mb-8 text-[var(--ink-3)]">Hours lost per event month across tracked assets</p>
      
      <div className="flex items-end gap-2 sm:gap-6 h-[180px] px-2 mt-auto relative">
        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-[0.03]">
          <div className="w-full h-px bg-white" />
          <div className="w-full h-px bg-white" />
          <div className="w-full h-px bg-white" />
        </div>
        
        {data.map((d) => (
          <div key={d.month} className="flex-1 flex flex-col items-center gap-3 group relative z-10">
            <span className="opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:-translate-y-1 bg-[#1A263B] text-white tnum text-xs font-bold px-2.5 py-1 rounded-md shadow-xl border border-[var(--brand)]/50 absolute -top-10 backdrop-blur-md">
              {d.hours}h
            </span>
            <div className="w-full flex justify-center h-[140px]">
              <div
                className="w-full max-w-[40px] rounded-t-md transition-all duration-500 group-hover:brightness-125 group-hover:shadow-[0_0_20px_var(--brand-glow)]"
                style={{
                  height: `${(d.hours / max) * 100}%`,
                  alignSelf: "flex-end",
                  background: "linear-gradient(180deg, var(--brand) 0%, rgba(79, 143, 232, 0.05) 100%)",
                }}
              />
            </div>
            <span className="tnum text-[10px] font-bold text-[var(--ink-3)] group-hover:text-[var(--brand)] transition-colors uppercase tracking-widest">{d.month}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function fmtLakh(n) {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function RoiBanner({ roi }) {
  if (!roi || roi.recurrence_count === 0) return null;
  return (
    <div className="relative rounded-[16px] p-[1px] mb-10 overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--brand)] to-transparent opacity-20 group-hover:opacity-60 transition-opacity duration-1000" />
      
      <div className="relative bg-[#070B14] p-8 md:p-10 rounded-[15px] z-10 overflow-hidden border border-white/5">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-96 h-96 rounded-full bg-[var(--brand)] blur-[130px] opacity-[0.15] pointer-events-none group-hover:opacity-30 transition-opacity duration-1000" />
        
        <div className="relative z-10 flex items-start justify-between gap-8 flex-wrap animate-in" style={{ animationDelay: '0.1s' }}>
          <div className="w-full">
            <div className="flex items-center gap-3 mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_12px_#34D399] animate-pulse" />
              <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#34D399]">Quantified Business Impact</div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
              <div>
                <div className="tnum text-6xl md:text-7xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/50">{fmtLakh(roi.avoidable_cost_inr)}</div>
                <div className="text-xs uppercase tracking-wider mt-4 text-[var(--ink-3)] font-semibold">Avoidable maintenance cost</div>
              </div>
              <div>
                <div className="tnum text-6xl md:text-7xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/50">{roi.avoidable_downtime_hours}<span className="text-4xl text-white/30 ml-1 font-normal tracking-normal">h</span></div>
                <div className="text-xs uppercase tracking-wider mt-4 text-[var(--ink-3)] font-semibold">Avoidable downtime</div>
              </div>
              <div>
                <div className="tnum text-6xl md:text-7xl font-extrabold tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/50">{roi.avoided_incidents}</div>
                <div className="text-xs uppercase tracking-wider mt-4 text-[var(--ink-3)] font-semibold">Incident{roi.avoided_incidents === 1 ? "" : "s"} avoided</div>
              </div>
            </div>
            
            <div className="mt-10 pt-6 border-t border-white/10 flex items-start gap-4">
              <div className="w-1 h-full bg-[var(--brand)] rounded-full shadow-[0_0_10px_var(--brand)] opacity-80" />
              <p className="text-sm font-medium leading-relaxed text-[var(--ink-2)] max-w-4xl">{roi.headline}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScaleCard() {
  const [bench, setBench] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.benchmark(5000).then(setBench); }, []);
  const rerun = (n) => { setBusy(true); api.benchmark(n).then((b) => { setBench(b); setBusy(false); }); };
  
  return (
    <Card className="p-6 border border-white/5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg text-white tracking-tight">Proven at Scale</h3>
        <div className="flex gap-1 bg-[#0A101C] p-1 rounded-lg border border-white/5 shadow-inner">
          {[1000, 5000, 10000].map((n) => (
            <button 
              key={n} 
              onClick={() => rerun(n)} 
              className={`tnum text-[10px] uppercase tracking-wider font-bold px-3 py-1.5 rounded-md transition-all duration-300 ${bench?.n_docs === n ? 'bg-[#1A263B] text-white shadow-sm border border-white/10' : 'text-[var(--ink-3)] hover:text-white'}`}
            >
              {n >= 1000 ? `${n / 1000}k` : n}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs mb-8 text-[var(--ink-3)]">Live benchmark — synthetic corpus through the real pipeline</p>
      
      {!bench ? (
        <Skeleton className="h-[200px]" />
      ) : (
        <div className={`transition-opacity duration-500 ${busy ? "opacity-30 filter blur-[2px]" : "opacity-100"}`}>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-5 rounded-xl bg-gradient-to-b from-[#121C2D] to-transparent border border-white/5">
              <div className="tnum text-3xl font-bold text-[var(--brand)]">{bench.query_p50_ms}<span className="text-sm ml-1 text-white/40 font-normal">ms</span></div>
              <div className="text-[10px] uppercase tracking-widest font-bold text-[var(--ink-3)] mt-2">Median Query</div>
            </div>
            <div className="p-5 rounded-xl bg-gradient-to-b from-[#121C2D] to-transparent border border-white/5">
              <div className="tnum text-3xl font-bold text-white">{(bench.build_ms / 1000).toFixed(1)}<span className="text-sm ml-1 text-white/40 font-normal">s</span></div>
              <div className="text-[10px] uppercase tracking-widest font-bold text-[var(--ink-3)] mt-2">Cold Build</div>
            </div>
          </div>
          <div className="space-y-3 text-sm text-[var(--ink-2)]">
            <Row label="Documents indexed" value={bench.n_docs.toLocaleString()} />
            <Row label="Graph size" value={`${bench.graph_nodes.toLocaleString()} nodes · ${bench.graph_edges.toLocaleString()} edges`} />
            <Row label="p95 query" value={`${bench.query_p95_ms} ms`} />
            <Row label="Peak memory" value={`${bench.peak_mem_mb} MB`} />
          </div>
        </div>
      )}
    </Card>
  );
}

function EvalCard() {
  const [ev, setEv] = useState(null);
  const [split, setSplit] = useState("tuning");
  useEffect(() => { api.evaluation().then(setEv).catch(() => {}); }, []);

  const aq = ev && (split === "tuning" ? ev.answer_quality : ev.answer_quality_held_out);
  const ent = ev && (split === "tuning" ? ev.entity_extraction : ev.entity_extraction_held_out);
  const lift = ev && (split === "tuning" ? ev.hybrid_lift : ev.hybrid_lift_held_out);

  return (
    <Card className="p-6 border border-white/5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg text-white tracking-tight">Measured Accuracy</h3>
        {ev && (
          <div className="flex gap-1 bg-[#0A101C] p-1 rounded-lg border border-white/5 shadow-inner">
            {[["tuning", "Tuning"], ["heldout", "Held-out"]].map(([key, label]) => (
              <button 
                key={key} 
                onClick={() => setSplit(key)} 
                className={`text-[10px] uppercase tracking-wider font-bold px-3 py-1.5 rounded-md transition-all duration-300 ${split === key ? 'bg-[#1A263B] text-white shadow-sm border border-white/10' : 'text-[var(--ink-3)] hover:text-white'}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="text-xs mb-8 text-[var(--ink-3)] h-4">
        {split === "tuning"
          ? "Benchmarked on gold set used during build phase"
          : `Benchmarked on ${ev?.validation.held_out_questions ?? "a"} new questions`}
      </p>
      
      {!ev ? <Skeleton className="h-[200px]" /> : (
        <div className="animate-in" style={{ animationDelay: '0.1s' }}>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-5 rounded-xl bg-gradient-to-b from-[#121C2D] to-transparent border border-white/5">
              <div className="tnum text-3xl font-bold text-[#34D399] drop-shadow-[0_0_15px_rgba(52,211,153,0.2)]">{aq.hit_at_1}%</div>
              <div className="text-[10px] uppercase tracking-widest font-bold text-[var(--ink-3)] mt-2">Answer hit@1</div>
            </div>
            <div className="p-5 rounded-xl bg-gradient-to-b from-[#121C2D] to-transparent border border-white/5">
              <div className="tnum text-3xl font-bold text-[#34D399] drop-shadow-[0_0_15px_rgba(52,211,153,0.2)]">{ent.f1}%</div>
              <div className="text-[10px] uppercase tracking-widest font-bold text-[var(--ink-3)] mt-2">Entity F1</div>
            </div>
          </div>
          <div className="space-y-3 text-sm text-[var(--ink-2)]">
            <Row label="Expert questions" value={aq.questions} />
            <Row label="Graph linkage completeness" value={`${ev.graph_linkage.completeness_pct}%`} />
            <Row label="Compliance traceability" value={`${ev.compliance_detection.evidence_traceability_pct}%`} />
            <Row label="Hybrid lift" value={`${lift.indirect.hit_at_1 >= 0 ? "+" : ""}${lift.indirect.hit_at_1} pts`} highlight />
          </div>
        </div>
      )}
    </Card>
  );
}

function Row({ label, value, highlight }) {
  return (
    <div className="flex items-center justify-between pb-3 border-b border-white/5 last:border-0 last:pb-0">
      <span className="text-[var(--ink-2)]">{label}</span>
      <span className={`tnum font-semibold ${highlight ? 'text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]' : 'text-white'}`}>{value}</span>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [assets, setAssets] = useState([]);
  const [compliance, setCompliance] = useState(null);
  const [roi, setRoi] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.stats().then(setStats);
    api.assets().then(setAssets);
    api.compliance().then(setCompliance);
    api.roi().then(setRoi);
  }, []);

  const topGaps = compliance?.findings.filter((f) => f.status === "gap").slice(0, 4) || [];
  const riskAssets = assets.filter((a) => a.health < 70).slice(0, 4);

  return (
    <div className="p-6 md:p-10 max-w-[1600px] mx-auto">
      
      <div className="relative mb-12 pb-8 border-b border-white/5 flex flex-col md:flex-row md:items-end justify-between gap-8">
        <div className="absolute top-0 left-0 w-96 h-64 bg-[var(--brand)] opacity-[0.06] blur-[100px] pointer-events-none" />
        <div className="relative z-10 max-w-3xl">
          <div className="flex items-center gap-3 mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--brand)] shadow-[0_0_8px_var(--brand)] animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-[var(--brand)]">Operations Intelligence</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white via-white to-white/40 tracking-tight mb-4">
            Plant Knowledge Overview
          </h1>
          <p className="text-sm md:text-base text-[var(--ink-2)] font-medium leading-relaxed max-w-2xl">
            One queryable brain over every drawing, work order, procedure, inspection, and incident — connecting what no single team can see alone.
          </p>
        </div>
        <div className="relative z-10 shrink-0">
          <Link
            to="/copilot"
            className="group relative inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl text-sm font-bold text-white overflow-hidden transition-all duration-300 border border-white/10 hover:border-[var(--brand)]/50 bg-[#121C2D] hover:bg-[#1A263B] shadow-[0_4px_20px_rgba(0,0,0,0.5)] hover:shadow-[0_0_30px_rgba(79,143,232,0.3)]"
          >
            <div className="absolute top-0 left-0 w-[200%] h-full bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:animate-sweep pointer-events-none" />
            <span className="relative z-10 text-[var(--brand)] group-hover:text-white transition-colors duration-300 drop-shadow-[0_0_8px_var(--brand)]">✦</span> 
            <span className="relative z-10">Ask the Copilot</span>
          </Link>
        </div>
      </div>

      <RoiBanner roi={roi} />

      {!stats ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[190px]" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10 animate-in" style={{ animationDelay: '0.2s' }}>
          <KpiCard label="Documents Unified" value={stats.documents.toLocaleString()} sub={`${stats.chunks.toLocaleString()} indexed passages`} to="/documents" />
          <KpiCard label="Knowledge Graph" value={stats.graph_nodes.toLocaleString()} sub={`${stats.graph_edges.toLocaleString()} relationships mapped`} to="/graph" />
          <KpiCard
            label="Compliance Score"
            value={`${stats.compliance_score}%`}
            sub={`${stats.open_gaps} open gaps`}
            accent={stats.compliance_score < 50 ? "var(--critical)" : stats.compliance_score < 75 ? "var(--warn)" : "var(--good)"}
            to="/compliance"
          />
          <KpiCard
            label="Assets at Risk"
            value={stats.assets_at_risk}
            sub={`${fmtINR(stats.total_cost_inr)} maintenance spend`}
            accent={stats.assets_at_risk > 0 ? "var(--serious)" : "var(--good)"}
            to="/assets"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        <div className="lg:col-span-2">
          {stats ? <DowntimeChart data={stats.downtime_by_month} /> : <Skeleton className="h-full min-h-[350px]" />}
        </div>

        <Card className="p-6 bg-gradient-to-b from-[var(--surface-1)] to-transparent border border-white/5">
          <h3 className="font-semibold text-lg text-white tracking-tight mb-1">Corpus Coverage</h3>
          <p className="text-xs mb-8 text-[var(--ink-3)]">Entities extracted and cross-linked</p>
          {!stats ? <Skeleton className="h-[250px]" /> : (
            <div className="space-y-5 animate-in" style={{ animationDelay: '0.3s' }}>
              {[
                ["Equipment tags", stats.unique_entities.equipment, "#60A5FA"],
                ["Standards & regs", stats.unique_entities.standard, "#34D399"],
                ["Failure modes", stats.unique_entities.failure_mode, "#F97316"],
                ["Personnel", stats.unique_entities.person, "#A78BFA"],
              ].map(([label, val, color]) => (
                <div key={label} className="flex items-center justify-between group">
                  <div className="flex items-center gap-4">
                    <span className="w-2 h-2 rounded-full transition-all duration-300 group-hover:scale-[2]" style={{ background: color, boxShadow: `0 0 12px ${color}` }} />
                    <span className="text-sm font-medium text-[var(--ink-2)] group-hover:text-white transition-colors duration-300">{label}</span>
                  </div>
                  <span className="tnum text-xs font-bold text-white bg-[#0A101C] border border-white/5 px-3 py-1.5 rounded-md shadow-inner group-hover:border-white/10 transition-colors">{val.toLocaleString()}</span>
                </div>
              ))}
              <div className="pt-6 mt-4 border-t border-white/5 flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--ink-2)]">Total Mentions</span>
                <span className="tnum text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-[var(--brand)] to-blue-400 drop-shadow-[0_0_12px_rgba(79,143,232,0.4)]">{stats.entity_mentions.toLocaleString()}</span>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        <ScaleCard />
        <EvalCard />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-12">
        <Card className="p-6 flex flex-col border border-white/5">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold text-lg text-white tracking-tight">Priority Compliance Gaps</h3>
            <Link to="/compliance" className="text-[10px] font-bold uppercase tracking-widest text-[var(--brand)] hover:text-white transition-colors flex items-center gap-1.5 group">
              View all <span className="group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </div>
          <div className="space-y-3 flex-1">
            {!topGaps.length ? <Skeleton className="h-[250px]" /> : topGaps.map((f) => (
              <div key={f.id} className="flex items-center justify-between gap-4 p-4 rounded-xl bg-gradient-to-r from-[#121C2D] to-transparent border border-white/5 hover:border-[var(--brand)]/30 hover:bg-[#1A263B] transition-all duration-300 cursor-pointer group">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold truncate text-[var(--ink-1)] group-hover:text-white transition-colors">{f.title}</div>
                  <div className="text-[10px] uppercase tracking-widest mt-2 flex items-center gap-2 text-[var(--ink-3)] font-bold">
                    <span>{f.standard}</span>
                    {f.evidence?.[0] && <><span>•</span><DocRefLink id={f.evidence[0]} /></>}
                  </div>
                </div>
                <StatusBadge status={f.status} />
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6 flex flex-col border border-white/5">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold text-lg text-white tracking-tight">Assets Needing Attention</h3>
            <Link to="/assets" className="text-[10px] font-bold uppercase tracking-widest text-[var(--brand)] hover:text-white transition-colors flex items-center gap-1.5 group">
              View all <span className="group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </div>
          <div className="space-y-3 flex-1">
            {!riskAssets.length ? <Skeleton className="h-[250px]" /> : riskAssets.map((a) => (
              <button
                key={a.tag}
                onClick={() => navigate(`/assets?tag=${a.tag}`)}
                className="w-full flex items-center justify-between gap-4 p-4 rounded-xl bg-gradient-to-r from-[#121C2D] to-transparent border border-white/5 hover:border-[var(--brand)]/30 hover:bg-[#1A263B] transition-all duration-300 text-left group"
              >
                <div>
                  <div className="text-sm font-mono font-bold text-white group-hover:text-[var(--brand)] transition-colors drop-shadow-sm">{a.tag}</div>
                  <div className="text-[10px] uppercase tracking-widest mt-2 font-bold text-[var(--ink-3)]">
                    <span className="text-[var(--warn)]">{a.corrective_count} failures</span> <span className="mx-2 opacity-30">|</span> <span className="text-[var(--serious)]">{a.downtime_hours} hrs down</span>
                  </div>
                </div>
                <HealthBar value={a.health} />
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}