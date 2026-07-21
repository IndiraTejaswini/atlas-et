import { useEffect, useState, useMemo } from "react";
import { api } from "../api.js";
import { Card, PageHeader, StatusBadge, SeverityDot, DocRefLink, Skeleton, statusMeta, Tabs, Badge } from "../components/ui.jsx";

const DEV_KIND = {
  process: { label: "Process", color: "var(--c1)" },
  realtime: { label: "Real-time", color: "var(--c6)" },
  control: { label: "Control of work", color: "var(--c7)" },
};
const DEV_SEV = {
  critical: { color: "var(--critical)", wash: "var(--critical-wash)" },
  high: { color: "var(--serious)", wash: "var(--serious-wash)" },
  medium: { color: "var(--warn)", wash: "var(--warn-wash)" },
  low: { color: "var(--ink-3)", wash: "var(--neutral-wash)" },
};

function DeviationsView() {
  const [data, setData] = useState(null);
  useEffect(() => { api.deviations().then(setData); }, []);
  if (!data) return <Skeleton className="h-[300px]" />;
  return (
    <>
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <div className="text-sm" style={{ color: "var(--ink-2)" }}>
          <b className="tnum text-base">{data.total}</b> active quality/process deviations flagged before escalation
        </div>
        <div className="flex gap-1.5">
          {Object.entries(data.by_kind).map(([k, n]) => (
            <Badge key={k} color={DEV_KIND[k]?.color || "var(--ink-2)"} wash="var(--surface-2)">{DEV_KIND[k]?.label || k}: {n}</Badge>
          ))}
        </div>
      </div>
      <div className="space-y-2.5">
        {data.deviations.map((d, i) => {
          const sev = DEV_SEV[d.severity] || DEV_SEV.low;
          const kind = DEV_KIND[d.kind] || { label: d.kind, color: "var(--ink-3)" };
          return (
            <Card key={i} className="p-4 border-l-[3px]" style={{ borderLeftColor: sev.color }}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-[15px]" style={{ color: "var(--ink-1)" }}>{d.title}</span>
                  <Badge color={kind.color} wash="var(--surface-2)">{kind.label}</Badge>
                </div>
                {d.asset && <span className="font-mono text-xs px-2 py-0.5 rounded shrink-0" style={{ background: "var(--surface-2)", color: "var(--ink-2)" }}>{d.asset}</span>}
              </div>
              <div className="flex items-center gap-4 mb-2 text-sm flex-wrap">
                <span className="px-2.5 py-1 rounded-[8px]" style={{ background: "var(--good-wash)", color: "var(--good)" }}>Expected: <b>{d.expected}</b></span>
                <span className="px-2.5 py-1 rounded-[8px]" style={{ background: sev.wash, color: sev.color }}>Observed: <b>{d.observed}</b></span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>{d.detail}</p>
              {d.docs?.length > 0 && <div className="flex gap-1.5 mt-2.5 flex-wrap">{d.docs.map((x) => <DocRefLink key={x} id={x} />)}</div>}
            </Card>
          );
        })}
      </div>
    </>
  );
}

function ScoreRing({ score }) {
  const color = score >= 75 ? "var(--good)" : score >= 50 ? "var(--warn)" : "var(--critical)";
  const r = 52, circ = 2 * Math.PI * r;
  return (
    <div className="relative w-[132px] h-[132px]">
      <svg width="132" height="132" className="-rotate-90">
        <circle cx="66" cy="66" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="11" />
        <circle cx="66" cy="66" r={r} fill="none" stroke={color} strokeWidth="11" strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - score / 100)}
          style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.22,1,0.36,1)" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tnum text-3xl font-bold" style={{ color }}>{score}</span>
        <span className="text-[11px] font-semibold" style={{ color: "var(--ink-3)" }}>SCORE</span>
      </div>
    </div>
  );
}

export default function Compliance() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("requirements");
  const [devCount, setDevCount] = useState(null);

  useEffect(() => { api.compliance().then(setData); api.deviations().then((d) => setDevCount(d.total)); }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    return filter === "all" ? data.findings : data.findings.filter((f) => f.status === filter);
  }, [data, filter]);

  const STATUS_ORDER = [
    ["gap", "Gaps"],
    ["no_evidence", "No evidence"],
    ["due_soon", "Due soon"],
    ["compliant", "Compliant"],
  ];

  return (
    <>
      <PageHeader
        eyebrow="Quality & Regulatory Intelligence"
        title="Compliance posture"
        subtitle="Regulatory requirements (OISD, Factories Act, PESO, environmental) mapped against current procedures, inspection records and equipment state — every gap computed from dates found in the documents, ready for an audit evidence pack."
        actions={
          <a
            href={api.evidencePackUrl()}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold text-white transition-all hover:opacity-90"
            style={{ background: "var(--brand)", boxShadow: "var(--shadow-1)" }}
          >
            ⬇ Generate evidence pack
          </a>
        }
      />

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { key: "requirements", label: "Requirements", badge: data?.counts.gap, badgeColor: "var(--critical)" },
          { key: "deviations", label: "Quality Deviations", badge: devCount, badgeColor: "var(--serious)" },
        ]}
      />

      {tab === "deviations" ? (
        <DeviationsView />
      ) : !data ? (
        <Skeleton className="h-[400px]" />
      ) : (
        <>
          <Card className="p-6 mb-4">
            <div className="flex items-center gap-8 flex-wrap">
              <ScoreRing score={data.score} />
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 min-w-[280px]">
                {STATUS_ORDER.map(([key, label]) => {
                  const m = statusMeta(key);
                  return (
                    <div key={key} className="text-center p-3 rounded-[12px]" style={{ background: m.wash }}>
                      <div className="tnum text-2xl font-bold" style={{ color: m.color }}>{data.counts[key] || 0}</div>
                      <div className="text-xs font-medium mt-0.5" style={{ color: "var(--ink-2)" }}>{label}</div>
                    </div>
                  );
                })}
              </div>
              <div className="text-xs" style={{ color: "var(--ink-3)" }}>
                <div>As of {data.as_of}</div>
                <div className="mt-0.5">{data.total_checks} requirements evaluated</div>
              </div>
            </div>
          </Card>

          <div className="flex items-center gap-1.5 mb-4 flex-wrap">
            <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>All ({data.total_checks})</FilterChip>
            {STATUS_ORDER.map(([key, label]) => (
              <FilterChip key={key} active={filter === key} onClick={() => setFilter(key)} status={key}>
                {label} ({data.counts[key] || 0})
              </FilterChip>
            ))}
          </div>

          <Card className="overflow-hidden">
           <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)", background: "var(--surface-inset)" }}>
                  <th className="px-5 py-3 w-8"></th>
                  <th className="px-2 py-3">Requirement</th>
                  <th className="px-2 py-3">Standard</th>
                  <th className="px-2 py-3">Status</th>
                  <th className="px-2 py-3">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr key={f.id} className="border-t align-top" style={{ borderColor: "var(--line-1)" }}>
                    <td className="px-5 py-4"><SeverityDot severity={f.severity} /></td>
                    <td className="px-2 py-4 max-w-md">
                      <div className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>{f.title}</div>
                      <div className="text-xs mt-0.5 leading-relaxed" style={{ color: "var(--ink-2)" }}>{f.detail}</div>
                      {f.equipment?.length > 0 && (
                        <div className="flex gap-1 mt-1.5">
                          {f.equipment.map((e) => <span key={e} className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}>{e}</span>)}
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-4"><span className="text-xs font-medium" style={{ color: "var(--ink-2)" }}>{f.standard}</span></td>
                    <td className="px-2 py-4"><StatusBadge status={f.status} /></td>
                    <td className="px-2 py-4">
                      <div className="flex flex-wrap gap-1">
                        {f.evidence.map((d) => <DocRefLink key={d} id={d} />)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
           </div>
          </Card>
        </>
      )}
    </>
  );
}

function FilterChip({ active, onClick, children, status }) {
  const m = status ? statusMeta(status) : null;
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
      style={{
        borderColor: active ? "transparent" : "var(--line-1)",
        // FIX: Replaced var(--ink-1) with #3b82f6
        background: active ? (m?.color || "#3b82f6") : "var(--surface-1)",
        color: active ? "#fff" : "var(--ink-2)",
      }}
    >
      {children}
    </button>
  );
}
