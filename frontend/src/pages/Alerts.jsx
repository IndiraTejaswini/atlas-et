import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, PageHeader, Badge, DocRefLink, Skeleton, EmptyState } from "../components/ui.jsx";

const SEV = {
  critical: { color: "var(--critical)", wash: "var(--critical-wash)", label: "Critical" },
  high: { color: "var(--serious)", wash: "var(--serious-wash)", label: "High" },
  medium: { color: "var(--warn)", wash: "var(--warn-wash)", label: "Medium" },
  low: { color: "var(--ink-3)", wash: "var(--neutral-wash)", label: "Low" },
};

const TEAM_COLOR = {
  "Rotating Equipment": "#3b82f6",          // Blue
  "Inspection & Integrity": "#f59e0b",      // Amber
  "Process Safety": "#ef4444",              // Red
  "Compliance & Regulatory": "#0891b2",     // Cyan
  "Operations": "#8b5cf6",                  // Purple
};

const SOURCE_ICON = {
  "Failure Intelligence": "◈",
  "Live Conditions": "◎",
  "Quality Deviation": "◇",
  "Compliance": "❖",
};

function WebhookStatus() {
  const [configured, setConfigured] = useState(null);
  const [testState, setTestState] = useState(null); // null | "sending" | "ok" | "fail"

  useEffect(() => {
    api.health().then((h) => setConfigured(h.alert_webhook_configured)).catch(() => setConfigured(false));
  }, []);

  async function sendTest() {
    setTestState("sending");
    try {
      const r = await api.testAlertWebhook();
      setTestState(r.sent ? "ok" : "fail");
    } catch {
      setTestState("fail");
    }
    setTimeout(() => setTestState(null), 4000);
  }

  if (configured === null) return null;

  return (
    <div className="flex items-center gap-2">
      <Badge
        color={configured ? "var(--good)" : "var(--ink-3)"}
        wash={configured ? "var(--good-wash)" : "var(--surface-2)"}
        title={configured ? "" : "Set ATLAS_ALERT_WEBHOOK_URL on the backend to enable real delivery"}
      >
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: configured ? "var(--good)" : "var(--ink-3)" }} />
        {configured ? "Webhook delivery on" : "Webhook not configured"}
      </Badge>
      {configured && (
        <button
          onClick={sendTest}
          disabled={testState === "sending"}
          className="text-xs font-semibold px-3 py-1.5 rounded-[9px] border transition-all hover:bg-[var(--surface-2)] disabled:opacity-50"
          style={{
            borderColor: "var(--line-1)",
            color: testState === "ok" ? "var(--good)" : testState === "fail" ? "var(--critical)" : "var(--ink-2)",
          }}
        >
          {testState === "sending" ? "Sending…" : testState === "ok" ? "✓ Sent" : testState === "fail" ? "✗ Failed" : "Send test"}
        </button>
      )}
    </div>
  );
}

function AlertRow({ a, onAck, onUnack }) {
  const sev = SEV[a.severity] || SEV.low;
  const acked = !!a.acknowledged;
  return (
    <Card className="p-4 transition-all" style={{ opacity: acked ? 0.6 : 1, borderLeft: `3px solid ${sev.color}` }}>
      <div className="flex items-start gap-3">
        <span className="text-lg mt-0.5" style={{ color: sev.color }}>{SOURCE_ICON[a.source] || "●"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-semibold text-[15px]" style={{ color: "var(--ink-1)" }}>{a.title}</span>
            <Badge color={sev.color} wash={sev.wash}>{sev.label}</Badge>
          </div>
          <p className="text-sm leading-relaxed mb-2" style={{ color: "var(--ink-2)" }}>{a.detail}</p>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge color="#fff" wash={TEAM_COLOR[a.team] || "var(--ink-2)"}>→ {a.team}</Badge>
            <span className="text-[11px]" style={{ color: "var(--ink-3)" }}>via {a.source}</span>
            {a.docs.map((d) => <DocRefLink key={d} id={d} />)}
          </div>
        </div>
        <div className="shrink-0">
          {acked ? (
            <button onClick={() => onUnack(a.id)} className="text-xs font-semibold px-3 py-1.5 rounded-[9px]" style={{ color: "var(--good)", background: "var(--good-wash)" }}>
              ✓ Ack {a.acknowledged.at}
            </button>
          ) : (
            <button onClick={() => onAck(a.id)} className="text-xs font-semibold px-3 py-1.5 rounded-[9px] text-white transition-all hover:opacity-90" style={{ background: "var(--brand)" }}>
              Acknowledge
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function Alerts() {
  const [data, setData] = useState(null);
  const [teamFilter, setTeamFilter] = useState("all");

  // Live subscription — picks up new alerts (or ones raised by another
  // client) without polling. Actions below still do one immediate refetch
  // each so the click feels instant rather than waiting for the stream's
  // next push.
  useEffect(() => {
    return api.streamAlerts(setData);
  }, []);

  async function ack(id) { await api.ackAlert(id); api.alerts().then(setData); }
  async function unack(id) { await api.unackAlert(id); api.alerts().then(setData); }
  function load() { api.alerts().then(setData); }

  const alerts = data?.alerts.filter((a) => teamFilter === "all" || a.team === teamFilter) || [];
  const active = alerts.filter((a) => !a.acknowledged);
  const acked = alerts.filter((a) => a.acknowledged);

  return (
    <>
      <PageHeader
        eyebrow="Proactive Alerts · Push to Teams"
        title="Action queue"
        subtitle="Every forward-looking signal — failure-intelligence warnings, live sensor breaches, quality deviations and compliance gaps — routed to the responsible team before it escalates. Acknowledge to clear."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <WebhookStatus />
            <button onClick={load} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold border transition-all hover:bg-[var(--surface-2)]" style={{ borderColor: "var(--line-1)", color: "var(--ink-2)" }}>
              ↻ Refresh
            </button>
          </div>
        }
      />

      {!data ? (
        <Skeleton className="h-[400px]" />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <Card className="p-4">
              <div className="tnum text-[28px] font-bold" style={{ color: "var(--critical)" }}>{data.active}</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Active alerts</div>
            </Card>
            <Card className="p-4">
              <div className="tnum text-[28px] font-bold" style={{ color: "var(--good)" }}>{data.acknowledged}</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Acknowledged</div>
            </Card>
            <Card className="p-4 col-span-2">
              <div className="text-xs font-semibold mb-2" style={{ color: "var(--ink-3)" }}>ROUTED TO</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.by_team).map(([team, n]) => (
                  <span key={team} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: TEAM_COLOR[team], color: "#fff" }}>
                    {team} <span className="tnum">{n}</span>
                  </span>
                ))}
              </div>
            </Card>
          </div>

          <div className="flex items-center gap-1.5 mb-4 flex-wrap">
            <FilterChip active={teamFilter === "all"} onClick={() => setTeamFilter("all")}>All teams</FilterChip>
            {data.teams.map((t) => (
              <FilterChip key={t} active={teamFilter === t} onClick={() => setTeamFilter(t)} color={TEAM_COLOR[t]}>{t}</FilterChip>
            ))}
          </div>

          {active.length === 0 && acked.length === 0 ? (
            <EmptyState icon="✓" title="No alerts for this team" hint="Everything is within limits." />
          ) : (
            <div className="space-y-2.5">
              {active.map((a) => <AlertRow key={a.id} a={a} onAck={ack} onUnack={unack} />)}
              {acked.length > 0 && (
                <div className="pt-4 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Acknowledged</div>
              )}
              {acked.map((a) => <AlertRow key={a.id} a={a} onAck={ack} onUnack={unack} />)}
            </div>
          )}
        </>
      )}
    </>
  );
}

// function FilterChip({ active, onClick, children, color }) {
//   return (
//     <button
//       onClick={onClick}
//       className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
//       style={{
//         borderColor: active ? "transparent" : "var(--line-1)",
//         // FIX: Replaced var(--ink-1) with #3b82f6
//         background: active ? (color || "#3b82f6") : "var(--surface-1)",
//         color: active ? "#fff" : "var(--ink-2)",
//       }}
//     >
//       {children}
//     </button>
//   );
// }

function FilterChip({ active, onClick, children, color }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
      style={{
        borderColor: active ? "transparent" : "var(--line-1)",
        background: active ? (color || "#3b82f6") : "var(--surface-1)", // FIX: Replaced var(--ink-1) with #3b82f6
        color: active ? "#fff" : "var(--ink-2)",
      }}
    >
      {children}
    </button>
  );
}