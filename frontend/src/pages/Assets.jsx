import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import {
  Card, PageHeader, HealthBar, DocRefLink, Badge, Skeleton, EmptyState, Tabs, Gauge, LiveDot,
} from "../components/ui.jsx";

function fmtINR(n) {
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

const PRIORITY_META = {
  critical: { color: "var(--critical)", wash: "var(--critical-wash)", label: "Critical" },
  high: { color: "var(--serious)", wash: "var(--serious-wash)", label: "High" },
  medium: { color: "var(--warn)", wash: "var(--warn-wash)", label: "Medium" },
  info: { color: "var(--brand)", wash: "var(--brand-wash)", label: "Insight" },
};

const SOURCE_META = {
  statutory: { label: "Statutory", color: "#0891b2" },
  predictive: { label: "Predictive", color: "var(--c1)" },
  oem: { label: "OEM", color: "var(--c5)" },
};

/* ---------------- Assets tab ---------------- */
function Timeline({ events }) {
  return (
    <div className="relative pl-5">
      <div className="absolute left-[7px] top-1 bottom-1 w-px" style={{ background: "var(--line-1)" }} />
      <div className="space-y-3">
        {[...events].reverse().map((e, i) => (
          <div key={i} className="relative">
            <div className="absolute -left-[18px] top-1 w-3.5 h-3.5 rounded-full border-2 border-white"
              style={{ background: e.type === "incident" ? "var(--critical)" : e.type === "inspection" ? "var(--c6)" : "var(--c4)" }} />
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <DocRefLink id={e.doc_id} />
                  <span className="text-[11px]" style={{ color: "var(--ink-3)" }}>{e.date}</span>
                </div>
                <div className="text-sm mt-0.5" style={{ color: "var(--ink-2)" }}>
                  {e.failure_mode && e.failure_mode !== "preventive"
                    ? <span className="font-medium" style={{ color: "var(--ink-1)" }}>{e.failure_mode}</span>
                    : <span>{e.type === "work_order" ? "Preventive maintenance" : e.title.split(" ").slice(1, 6).join(" ")}</span>}
                </div>
              </div>
              {e.downtime_hours > 0 && <span className="tnum text-xs font-semibold shrink-0" style={{ color: "var(--serious)" }}>{e.downtime_hours}h down</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LiveStrip({ tag }) {
  const [snap, setSnap] = useState(null);
  useEffect(() => {
    setSnap(null);
    return api.streamTelemetry(tag, (d) => setSnap(d[tag]));
  }, [tag]);
  if (!snap) return null;
  return (
    <div className="mb-5 p-4 rounded-[12px]" style={{ background: "var(--surface-inset)" }}>
      <div className="flex items-center gap-2 mb-2">
        <LiveDot status={snap.status} />
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Live operating conditions</span>
        <span className="tnum text-[11px] ml-auto" style={{ color: "var(--ink-3)" }}>{snap.ts}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-x-5">
        {snap.channels.map((c) => <Gauge key={c.label} channel={c} />)}
      </div>
    </div>
  );
}

function AssetDetail({ asset }) {
  return (
    <Card className="p-6 animate-in">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold font-mono" style={{ color: "var(--ink-1)" }}>{asset.tag}</h2>
            <HealthBar value={asset.health} />
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm flex-wrap" style={{ color: "var(--ink-2)" }}>
            <span><b className="tnum">{asset.corrective_count}</b> corrective events</span>
            <span><b className="tnum">{asset.downtime_hours}</b> hrs downtime</span>
            <span><b>{fmtINR(asset.cost_inr)}</b> spend</span>
            {asset.mtbf_days && <span>MTBF <b className="tnum">{asset.mtbf_days}</b> days</span>}
          </div>
        </div>
      </div>

      <LiveStrip tag={asset.tag} />

      {asset.recommendations.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>AI Recommendations & RCA</h3>
          <div className="space-y-2.5">
            {asset.recommendations.map((r, i) => {
              const m = PRIORITY_META[r.priority];
              return (
                <div key={i} className="p-4 rounded-[12px] border-l-[3px]" style={{ background: m.wash, borderColor: m.color }}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm leading-relaxed flex-1" style={{ color: "var(--ink-1)" }}>{r.text}</p>
                    <Badge color={m.color} wash="#fff">{m.label}</Badge>
                  </div>
                  {r.docs?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2.5">{[...new Set(r.docs)].map((d) => <DocRefLink key={d} id={d} />)}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>Failure timeline</h3>
          {asset.events.length ? <Timeline events={asset.events} /> : <p className="text-sm" style={{ color: "var(--ink-3)" }}>No recorded events.</p>}
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>Failure modes</h3>
          {Object.keys(asset.failure_modes).length ? (
            <div className="space-y-2 mb-5">
              {Object.entries(asset.failure_modes).map(([mode, n]) => (
                <div key={mode} className="flex items-center justify-between px-3 py-2 rounded-[10px]" style={{ background: "var(--surface-inset)" }}>
                  <span className="text-sm font-medium" style={{ color: "var(--ink-1)" }}>{mode}</span>
                  <span className="tnum text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: "var(--critical-wash)", color: "var(--critical)" }}>×{n}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-sm mb-5" style={{ color: "var(--ink-3)" }}>No corrective failures recorded.</p>}
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>All linked documents</h3>
          <div className="flex flex-wrap gap-1.5">{asset.related_docs.map((d) => <DocRefLink key={d} id={d} />)}</div>
        </div>
      </div>
    </Card>
  );
}

function AssetsTab({ assets, activeTag, setTag }) {
  const active = assets.find((a) => a.tag === activeTag) || assets[0];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
      <div className="space-y-2">
        {assets.map((a) => (
          <button key={a.tag} onClick={() => setTag(a.tag)} className="w-full text-left">
            <Card className="p-3.5 transition-all hover:shadow-[var(--shadow-2)]" style={active?.tag === a.tag ? { borderColor: "var(--brand)", boxShadow: "var(--shadow-2)" } : {}}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-sm" style={{ color: "var(--ink-1)" }}>{a.tag}</span>
                <span className="tnum text-xs font-bold px-2 py-0.5 rounded-full" style={{
                  color: a.health >= 75 ? "var(--good)" : a.health >= 55 ? "var(--warn)" : "var(--critical)",
                  background: a.health >= 75 ? "var(--good-wash)" : a.health >= 55 ? "var(--warn-wash)" : "var(--critical-wash)",
                }}>{a.health}</span>
              </div>
              <HealthBar value={a.health} />
              <div className="text-[11px] mt-2" style={{ color: "var(--ink-3)" }}>{a.corrective_count} failures · {a.recommendations.length} recommendations</div>
            </Card>
          </button>
        ))}
      </div>
      <div>{active ? <AssetDetail asset={active} /> : <EmptyState icon="⚙" title="No assets" />}</div>
    </div>
  );
}

/* ---------------- Live Conditions tab ---------------- */
function LiveConditionsTab() {
  const [snap, setSnap] = useState(null);
  const [ts, setTs] = useState("");
  useEffect(() => {
    return api.streamTelemetry(null, (d) => { setSnap(d); setTs(new Date().toLocaleTimeString()); });
  }, []);
  if (!snap) return <Skeleton className="h-[400px]" />;
  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        <span className="w-2 h-2 rounded-full pulse" style={{ background: "var(--good)" }} />
        <span className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Live via SSE from plant historian simulator</span>
        <span className="tnum text-xs ml-auto" style={{ color: "var(--ink-3)" }}>last update {ts}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {Object.values(snap).map((a) => (
          <Card key={a.asset} className="p-5" style={a.status === "breach" ? { borderColor: "var(--critical)" } : {}}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono font-bold" style={{ color: "var(--ink-1)" }}>{a.asset}</span>
              <div className="flex items-center gap-1.5">
                <LiveDot status={a.status} />
                <span className="text-xs font-semibold" style={{ color: a.status === "breach" ? "var(--critical)" : a.status === "warn" ? "var(--warn)" : "var(--good)" }}>
                  {a.status === "breach" ? "Alarm" : a.status === "warn" ? "Watch" : "Normal"}
                </span>
              </div>
            </div>
            {a.channels.map((c) => <Gauge key={c.label} channel={c} />)}
          </Card>
        ))}
      </div>
    </>
  );
}

/* ---------------- PM Schedule tab ---------------- */
function ScheduleTab() {
  const [data, setData] = useState(null);
  useEffect(() => { api.schedule().then(setData); }, []);
  if (!data) return <Skeleton className="h-[400px]" />;
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {[
          ["Scheduled tasks", data.summary.total, "var(--ink-1)"],
          ["Overdue", data.summary.overdue, "var(--critical)"],
          ["Next 30 days", data.summary.next_30_days, "var(--warn)"],
          ["Predictive", data.summary.by_source.predictive, "var(--c1)"],
        ].map(([l, v, c]) => (
          <Card key={l} className="p-4"><div className="tnum text-[26px] font-bold" style={{ color: c }}>{v}</div><div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>{l}</div></Card>
        ))}
      </div>
      <Card className="p-2">
        {data.tasks.map((t, i) => {
          const p = PRIORITY_META[t.priority] || PRIORITY_META.info;
          const src = SOURCE_META[t.source] || { label: t.source, color: "var(--ink-3)" };
          const overdue = t.days_until != null && t.days_until < 0;
          return (
            <div key={i} className="flex items-start gap-4 p-3 rounded-[10px] hover:bg-[var(--surface-inset)] transition-colors" style={i > 0 ? { borderTop: "1px solid var(--line-2)" } : {}}>
              <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: p.color }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono font-bold text-sm" style={{ color: "var(--ink-1)" }}>{t.asset}</span>
                  <span className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>{t.task}</span>
                  <Badge color={src.color} wash="var(--surface-2)">{src.label}</Badge>
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--ink-2)" }}>{t.reason}</div>
                <div className="flex gap-1.5 mt-1.5">{t.docs.map((d) => <DocRefLink key={d} id={d} />)}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="tnum text-sm font-semibold" style={{ color: overdue ? "var(--critical)" : "var(--ink-1)" }}>{t.due || "—"}</div>
                {t.days_until != null && (
                  <div className="tnum text-[11px]" style={{ color: overdue ? "var(--critical)" : "var(--ink-3)" }}>
                    {overdue ? `${-t.days_until}d overdue` : `in ${t.days_until}d`}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </Card>
    </>
  );
}

export default function Assets() {
  const [assets, setAssets] = useState(null);
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("assets");
  const activeTag = params.get("tag");

  useEffect(() => { api.assets().then(setAssets); }, []);

  return (
    <>
      <PageHeader
        eyebrow="Maintenance Intelligence & RCA"
        title="Asset health, live conditions & schedule"
        subtitle="Work orders, inspections, incidents, OEM knowledge and real-time operating conditions fused per asset — with recurring-failure RCA and an optimised, risk-ranked maintenance schedule."
      />

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { key: "assets", label: "Assets & RCA" },
          { key: "live", label: "Live Conditions" },
          { key: "schedule", label: "PM Schedule" },
        ]}
      />

      {!assets ? (
        <Skeleton className="h-[500px]" />
      ) : tab === "assets" ? (
        <AssetsTab assets={assets} activeTag={activeTag} setTag={(t) => setParams({ tag: t })} />
      ) : tab === "live" ? (
        <LiveConditionsTab />
      ) : (
        <ScheduleTab />
      )}
    </>
  );
}
