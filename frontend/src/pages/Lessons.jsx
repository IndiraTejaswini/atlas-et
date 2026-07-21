import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, PageHeader, Badge, DocRefLink, Skeleton, SeverityDot } from "../components/ui.jsx";

const SEV_META = {
  high: { color: "var(--critical)", wash: "var(--critical-wash)", label: "High priority" },
  medium: { color: "var(--warn)", wash: "var(--warn-wash)", label: "Medium priority" },
  low: { color: "var(--ink-3)", wash: "var(--neutral-wash)", label: "Low" },
};

function WarningCard({ w }) {
  const m = SEV_META[w.severity] || SEV_META.low;
  return (
    <Card className="p-5 border-l-[3px]" style={{ borderLeftColor: m.color }}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚠</span>
          <h3 className="font-semibold text-[15px]" style={{ color: "var(--ink-1)" }}>{w.title}</h3>
        </div>
        <Badge color={m.color} wash={m.wash}>{m.label}</Badge>
      </div>
      <p className="text-sm leading-relaxed mb-3" style={{ color: "var(--ink-2)" }}>{w.text}</p>
      <div className="flex items-center gap-2 flex-wrap">
        {[...new Set(w.docs)].map((d) => <DocRefLink key={d} id={d} />)}
        {w.matches_signature && (
          <Badge color="#a78bfa" wash="#2e1065">↔ {w.matches_signature}</Badge>
        )}
      </div>
    </Card>
  );
}

export default function Lessons() {
  const [data, setData] = useState(null);

  useEffect(() => { api.lessons().then(setData); }, []);

  return (
    <>
      <PageHeader
        eyebrow="Lessons Learned & Failure Intelligence"
        title="Systemic patterns & proactive warnings"
        subtitle="Analyses every incident, near-miss and failure record across the plant's history at once — surfacing recurring patterns invisible to any single review, matching them to known industry failure signatures, and pushing warnings before conditions recur."
      />

      {!data ? (
        <Skeleton className="h-[500px]" />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {[
              ["Incidents analysed", data.stats.incidents_analysed, "#ef4444"], 
              ["Systemic patterns", data.stats.patterns_found, "#f59e0b"],      
              ["Active warnings", data.stats.warnings_active, "var(--critical)"],
              ["Industry signatures matched", data.stats.signatures_matched, "#8b5cf6"], 
            ].map(([label, val, color]) => (
              <Card key={label} className="p-4">
                <div className="tnum text-[28px] font-bold" style={{ color }}>{val}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>{label}</div>
              </Card>
            ))}
          </div>

          {/* Proactive warnings */}
          <div className="mb-6">
            <h2 className="text-sm font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: "var(--ink-2)" }}>
              <span className="w-2 h-2 rounded-full pulse" style={{ background: "var(--critical)" }} />
              Proactive warnings — pushed before recurrence
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {data.warnings.map((w, i) => <WarningCard key={i} w={w} />)}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Recurring failure patterns */}
            <Card className="p-5">
              <h3 className="font-semibold mb-1" style={{ color: "var(--ink-1)" }}>Fleet-wide failure patterns</h3>
              <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Failure modes recurring across multiple documents and assets</p>
              <div className="space-y-2.5">
                {data.patterns.map((p) => (
                  <div key={p.mode} className="p-3 rounded-[12px]" style={{ background: "var(--surface-inset)" }}>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>{p.mode}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="tnum text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: "var(--critical-wash)", color: "var(--critical)" }}>
                          {p.doc_count} docs
                        </span>
                        {p.asset_count > 0 && (
                          <span className="tnum text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: "#fdeee7", color: "#f59e0b" }}>
                            {p.asset_count} assets
                          </span>
                        )}
                      </div>
                    </div>
                    {p.assets.length > 0 && (
                      <div className="flex gap-1 flex-wrap mb-1.5">
                        {p.assets.map((a) => <span key={a} className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "#fff", color: "var(--ink-3)" }}>{a}</span>)}
                      </div>
                    )}
                    {p.industry_match.length > 0 && (
                      <div className="text-[11px] mt-1" style={{ color: "#8b5cf6" }}>↔ matches industry signature: {p.industry_match.join(", ")}</div>
                    )}
                    <div className="flex gap-1 flex-wrap mt-2">
                      {p.docs.slice(0, 6).map((d) => <DocRefLink key={d} id={d} />)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <div className="space-y-4">
              {/* Systemic themes */}
              <Card className="p-5">
                <h3 className="font-semibold mb-1" style={{ color: "var(--ink-1)" }}>Systemic organisational themes</h3>
                <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Root causes that repeat beneath individual events</p>
                <div className="space-y-3">
                  {data.themes.map((t) => (
                    <div key={t.name}>
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>{t.name}</span>
                        <span className="tnum text-xs" style={{ color: "var(--ink-3)" }}>{t.count} docs</span>
                      </div>
                      <p className="text-xs mt-0.5 mb-1.5" style={{ color: "var(--ink-2)" }}>{t.description}</p>
                      <div className="flex gap-1 flex-wrap">{t.docs.map((d) => <DocRefLink key={d} id={d} />)}</div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Extracted learnings */}
              <Card className="p-5">
                <h3 className="font-semibold mb-1" style={{ color: "var(--ink-1)" }}>Captured learnings</h3>
                <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Lessons extracted verbatim from incident investigations</p>
                <div className="space-y-3">
                  {data.learnings.map((l, i) => (
                    <div key={i} className="pl-3 border-l-2" style={{ borderColor: "#10b981" }}>
                      <p className="text-sm italic leading-relaxed" style={{ color: "var(--ink-2)" }}>"{l.text}"</p>
                      <div className="mt-1.5"><DocRefLink id={l.doc} /></div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>

          {/* Reference signatures */}
          <Card className="p-5 mt-4">
            <h3 className="font-semibold mb-1" style={{ color: "var(--ink-1)" }}>Reference failure-signature library</h3>
            <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Known industry cause→effect patterns (OISD / API / OEM) that internal findings are matched against</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.industry_signatures.map((s) => (
                <div key={s.id} className="p-3 rounded-[10px] flex gap-3" style={{ background: "var(--surface-inset)" }}>
                  <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded h-fit" style={{ background: "#2e1065", color: "#a78bfa" }}>{s.id}</span>
                  <div>
                    <div className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>{s.name}</div>
                    <div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>{s.note}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </>
  );
}