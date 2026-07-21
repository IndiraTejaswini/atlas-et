// import { Component } from "react";
// import { Link } from "react-router-dom";

// /* Catches render/lifecycle errors in whatever subtree it wraps so one
//    broken page can't take down the whole SPA — React has no hook
//    equivalent, an error boundary must be a class component with
//    getDerivedStateFromError/componentDidCatch. Regression coverage for
//    the Alerts.jsx `load` ReferenceError: that bug rendered the entire app
//    blank because nothing caught it; this is what would have contained it
//    to the one page instead. */
// export class ErrorBoundary extends Component {
//   constructor(props) {
//     super(props);
//     this.state = { error: null };
//   }

//   static getDerivedStateFromError(error) {
//     return { error };
//   }

//   componentDidCatch(error, info) {
//     console.error("ErrorBoundary caught a render error:", error, info?.componentStack);
//   }

//   render() {
//     if (this.state.error) {
//       return (
//         <div className="flex flex-col items-center justify-center py-20 text-center px-6">
//           <div className="text-4xl mb-3 opacity-60">⚠</div>
//           <div className="font-semibold text-lg" style={{ color: "var(--ink-1)" }}>This page hit an error</div>
//           <p className="text-sm mt-1.5 max-w-md" style={{ color: "var(--ink-3)" }}>
//             The rest of ATLAS is unaffected — pick another page from the sidebar, or reload this one.
//           </p>
//           <div className="flex items-center gap-2 mt-5">
//             <button
//               onClick={() => window.location.reload()}
//               className="px-4 py-2 rounded-[10px] text-sm font-semibold text-white transition-all hover:opacity-90"
//               style={{ background: "var(--brand)" }}
//             >
//               Reload page
//             </button>
//           </div>
//           <pre
//             className="text-[11px] text-left mt-6 p-3 rounded-[8px] max-w-lg overflow-auto font-mono"
//             style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}
//           >
//             {String(this.state.error?.message || this.state.error)}
//           </pre>
//         </div>
//       );
//     }
//     return this.props.children;
//   }
// }

// const DOC_TYPE_META = {
//   drawing: { label: "P&ID", color: "var(--c1)", wash: "#eaf2fd" },
//   datasheet: { label: "Datasheet", color: "var(--c7)", wash: "#ecebf7" },
//   oem_manual: { label: "OEM Manual", color: "var(--c5)", wash: "#e6f7f0" },
//   procedure: { label: "SOP", color: "var(--c2)", wash: "#e7f6e7" },
//   work_order: { label: "Work Order", color: "var(--c4)", wash: "#fdf3e0" },
//   inspection: { label: "Inspection", color: "var(--c6)", wash: "#fdeee7" },
//   incident: { label: "Incident", color: "var(--c8)", wash: "#fbe9e9" },
//   memo: { label: "Handover", color: "var(--c3)", wash: "#fdeef4" },
//   regulatory: { label: "Regulatory", color: "#0891b2", wash: "#e2f5f9" },
//   email: { label: "Email", color: "#64748b", wash: "#eef1f5" },
//   uploaded: { label: "Uploaded", color: "var(--brand)", wash: "#eaf2fd" },
// };

// export function docTypeMeta(type) {
//   return DOC_TYPE_META[type] || DOC_TYPE_META.uploaded;
// }

// export function Card({ children, className = "", ...rest }) {
//   return (
//     <div
//       className={`rounded-[14px] bg-white border ${className}`}
//       style={{ borderColor: "var(--line-1)", boxShadow: "var(--shadow-1)" }}
//       {...rest}
//     >
//       {children}
//     </div>
//   );
// }

// export function Badge({ children, color = "var(--ink-2)", wash = "var(--surface-2)", className = "" }) {
//   return (
//     <span
//       className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${className}`}
//       style={{ color, background: wash }}
//     >
//       {children}
//     </span>
//   );
// }

// export function DocTypeBadge({ type }) {
//   const m = docTypeMeta(type);
//   return <Badge color={m.color} wash={m.wash}>{m.label}</Badge>;
// }

// const STATUS_META = {
//   compliant: { label: "Compliant", color: "var(--good)", wash: "var(--good-wash)", dot: "var(--good)" },
//   due_soon: { label: "Due soon", color: "var(--warn)", wash: "var(--warn-wash)", dot: "var(--warn)" },
//   gap: { label: "Gap", color: "var(--critical)", wash: "var(--critical-wash)", dot: "var(--critical)" },
//   no_evidence: { label: "No evidence", color: "var(--ink-2)", wash: "var(--neutral-wash)", dot: "var(--ink-3)" },
// };

// export function statusMeta(status) {
//   return STATUS_META[status] || STATUS_META.no_evidence;
// }

// export function StatusBadge({ status }) {
//   const m = statusMeta(status);
//   return (
//     <Badge color={m.color} wash={m.wash}>
//       <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.dot }} />
//       {m.label}
//     </Badge>
//   );
// }

// export function SeverityDot({ severity }) {
//   const c = { critical: "var(--critical)", high: "var(--serious)", medium: "var(--warn)", low: "var(--ink-3)" }[severity] || "var(--ink-3)";
//   return <span className="w-2 h-2 rounded-full inline-block" style={{ background: c }} title={severity} />;
// }

// export function HealthBar({ value }) {
//   const color = value >= 75 ? "var(--good)" : value >= 55 ? "var(--warn)" : value >= 35 ? "var(--serious)" : "var(--critical)";
//   return (
//     <div className="flex items-center gap-2.5 min-w-[120px]">
//       <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
//         <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, background: color }} />
//       </div>
//       <span className="tnum text-sm font-semibold w-8 text-right" style={{ color }}>{value}</span>
//     </div>
//   );
// }

// export function PageHeader({ eyebrow, title, subtitle, actions }) {
//   return (
//     <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
//       <div>
//         {eyebrow && (
//           <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--brand)" }}>
//             {eyebrow}
//           </div>
//         )}
//         <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--ink-1)" }}>{title}</h1>
//         {subtitle && <p className="text-sm mt-1.5 max-w-2xl" style={{ color: "var(--ink-2)" }}>{subtitle}</p>}
//       </div>
//       {actions && <div className="flex items-center gap-2">{actions}</div>}
//     </div>
//   );
// }

// export function DocRefLink({ id, children }) {
//   return (
//     <Link
//       to={`/documents/${encodeURIComponent(id)}`}
//       className="inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-semibold font-mono transition-colors hover:opacity-80"
//       style={{ color: "var(--brand-strong)", background: "var(--brand-wash)" }}
//     >
//       {children || id}
//     </Link>
//   );
// }

// export function EmptyState({ icon, title, hint }) {
//   return (
//     <div className="flex flex-col items-center justify-center py-16 text-center">
//       <div className="text-4xl mb-3 opacity-60">{icon}</div>
//       <div className="font-semibold" style={{ color: "var(--ink-1)" }}>{title}</div>
//       {hint && <div className="text-sm mt-1 max-w-sm" style={{ color: "var(--ink-3)" }}>{hint}</div>}
//     </div>
//   );
// }

// export function Skeleton({ className = "" }) {
//   return <div className={`skeleton ${className}`} />;
// }

// export function Tabs({ tabs, active, onChange }) {
//   return (
//     <div className="flex items-center gap-1 p-1 rounded-[12px] mb-5 w-fit" style={{ background: "var(--surface-2)" }}>
//       {tabs.map((t) => (
//         <button
//           key={t.key}
//           onClick={() => onChange(t.key)}
//           className="px-4 py-2 rounded-[9px] text-sm font-semibold transition-all flex items-center gap-2"
//           style={
//             active === t.key
//               ? { background: "var(--surface-1)", color: "var(--ink-1)", boxShadow: "var(--shadow-1)" }
//               : { color: "var(--ink-3)" }
//           }
//         >
//           {t.label}
//           {t.badge != null && t.badge > 0 && (
//             <span className="tnum text-[11px] font-bold px-1.5 rounded-full" style={{ background: t.badgeColor || "var(--critical)", color: "#fff" }}>{t.badge}</span>
//           )}
//         </button>
//       ))}
//     </div>
//   );
// }

// const SENSOR_STATUS = {
//   ok: { color: "var(--good)", label: "OK" },
//   warn: { color: "var(--warn)", label: "Warn" },
//   high: { color: "var(--critical)", label: "High" },
//   low: { color: "var(--critical)", label: "Low" },
// };

// /* Linear gauge: value against its low/high limit band */
// export function Gauge({ channel }) {
//   const s = SENSOR_STATUS[channel.status] || SENSOR_STATUS.ok;
//   const { value, low, high, unit } = channel;
//   // Build a display scale around the active limit
//   const limit = high ?? low;
//   const span = high != null ? high * 1.4 : low != null ? low * 1.8 : value * 1.5;
//   const pct = Math.max(2, Math.min(98, (value / span) * 100));
//   const limitPct = limit != null ? Math.max(2, Math.min(98, (limit / span) * 100)) : null;
//   return (
//     <div className="py-2">
//       <div className="flex items-baseline justify-between mb-1.5">
//         <span className="text-xs font-medium" style={{ color: "var(--ink-2)" }}>{channel.label}</span>
//         <span className="tnum text-sm font-bold" style={{ color: s.color }}>
//           {value}<span className="text-xs font-medium ml-0.5" style={{ color: "var(--ink-3)" }}>{unit}</span>
//         </span>
//       </div>
//       <div className="relative h-2 rounded-full overflow-hidden" style={{ background: "var(--surface-2)" }}>
//         <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: s.color }} />
//         {limitPct != null && (
//           <div className="absolute top-0 bottom-0 w-[2px]" style={{ left: `${limitPct}%`, background: "var(--ink-1)", opacity: 0.55 }} title={`limit ${limit}${unit}`} />
//         )}
//       </div>
//       <div className="flex justify-between mt-1 text-[10px]" style={{ color: "var(--ink-3)" }}>
//         <span>{channel.status !== "ok" ? s.label : ""}</span>
//         {limit != null && <span className="tnum">limit {limit}{unit}</span>}
//       </div>
//     </div>
//   );
// }

// export function LiveDot({ status }) {
//   const color = status === "breach" ? "var(--critical)" : status === "warn" ? "var(--warn)" : "var(--good)";
//   return <span className={`inline-block w-2 h-2 rounded-full ${status !== "ok" ? "pulse" : ""}`} style={{ background: color }} />;
// }

import { Component } from "react";
import { Link } from "react-router-dom";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught a render error:", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center px-6 animate-in">
          <div className="text-5xl mb-4 text-[var(--critical)] opacity-80" style={{ textShadow: "0 0 20px var(--critical)" }}>⚠</div>
          <div className="font-semibold text-xl text-white">System Interruption</div>
          <p className="text-sm mt-2 max-w-md text-[var(--ink-2)]">
            The telemetry for this view was interrupted. The core network remains unaffected.
          </p>
          <div className="mt-6">
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all bg-[var(--surface-2)] border border-[var(--brand)] hover:shadow-[0_0_15px_var(--brand-glow)]"
            >
              Reload View
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const DOC_TYPE_META = {
  drawing: { label: "P&ID", color: "#60A5FA", wash: "rgba(96, 165, 250, 0.1)" },
  datasheet: { label: "Datasheet", color: "#A78BFA", wash: "rgba(167, 139, 250, 0.1)" },
  oem_manual: { label: "OEM Manual", color: "#2DD4BF", wash: "rgba(45, 212, 191, 0.1)" },
  procedure: { label: "SOP", color: "#34D399", wash: "rgba(52, 211, 153, 0.1)" },
  work_order: { label: "Work Order", color: "#FBBF24", wash: "rgba(251, 191, 36, 0.1)" },
  inspection: { label: "Inspection", color: "#F97316", wash: "rgba(249, 115, 22, 0.1)" },
  incident: { label: "Incident", color: "#F87171", wash: "rgba(248, 113, 113, 0.1)" },
  uploaded: { label: "Uploaded", color: "var(--brand)", wash: "var(--brand-glow)" },
};

export function docTypeMeta(type) {
  return DOC_TYPE_META[type] || DOC_TYPE_META.uploaded;
}

export function Gauge({ value, max = 100, label }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  return (
    <div className="flex flex-col items-center gap-1">
      <div 
        className="relative w-12 h-12 flex items-center justify-center rounded-full"
        style={{ background: "var(--surface-2)" }}
      >
        <svg className="w-full h-full transform -rotate-90 absolute" viewBox="0 0 36 36">
          {/* Background Track */}
          <path
            strokeWidth="3"
            stroke="var(--line-1)"
            fill="none"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          {/* Progress Arc */}
          <path
            strokeDasharray={`${percentage}, 100`}
            strokeWidth="3"
            stroke="var(--brand, #3b82f6)"
            fill="none"
            strokeLinecap="round"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <span className="text-xs font-bold" style={{ color: "var(--ink-1)" }}>
          {Math.round(percentage)}%
        </span>
      </div>
      {label && (
        <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
          {label}
        </span>
      )}
    </div>
  );
}

// Add this to /src/components/ui.jsx

export function LiveDot({ color = "var(--brand, #10b981)" }) {
  return (
    <span className="relative flex h-3 w-3">
      <span 
        className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" 
        style={{ backgroundColor: color }}
      ></span>
      <span 
        className="relative inline-flex rounded-full h-3 w-3" 
        style={{ backgroundColor: color }}
      ></span>
    </span>
  );
}

export function SeverityDot({ severity }) {
  const c = { critical: "var(--critical)", high: "var(--serious)", medium: "var(--warn)", low: "var(--ink-3)" }[severity] || "var(--ink-3)";
  return <span className="w-2 h-2 rounded-full inline-block" style={{ background: c }} title={severity} />;
}

export function Tabs({ tabs, activeTab, onChange }) {
  return (
    <div className="flex space-x-2 border-b mb-4" style={{ borderColor: "var(--line-1)" }}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className="py-2 px-4 text-sm font-medium border-b-2 transition-colors"
          style={{
            borderColor: activeTab === tab.id ? "var(--brand, #3b82f6)" : "transparent",
            color: activeTab === tab.id ? "var(--ink-1)" : "var(--ink-3)",
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* Premium Bento Glow Card */
export function Card({ children, className = "", ...rest }) {
  return (
    <div
      className={`relative bg-[var(--surface-1)] rounded-[16px] border border-[var(--line-1)] overflow-hidden group transition-all duration-500 hover:-translate-y-1 hover:border-[var(--brand)] hover:shadow-[0_8px_30px_rgba(27,42,74,0.4)] ${className}`}
      {...rest}
    >
      {/* Top Edge Glow */}
      <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[var(--brand)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {/* Internal ambient corner glow */}
      <div className="absolute -top-20 -left-20 w-48 h-48 bg-[var(--brand)] rounded-full blur-[80px] opacity-0 group-hover:opacity-15 transition-opacity duration-700 pointer-events-none" />
      
      <div className="relative z-10">{children}</div>
    </div>
  );
}

export function Badge({ children, color = "var(--ink-2)", wash = "var(--surface-2)", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] uppercase tracking-[0.1em] font-semibold border ${className}`}
      style={{ color, background: wash, borderColor: wash.replace('0.1', '0.2') }}
    >
      {children}
    </span>
  );
}

export function DocTypeBadge({ type }) {
  const m = docTypeMeta(type);
  return <Badge color={m.color} wash={m.wash}>{m.label}</Badge>;
}

const STATUS_META = {
  compliant: { label: "Compliant", color: "var(--good)", wash: "rgba(16, 185, 129, 0.1)" },
  due_soon: { label: "Due soon", color: "var(--warn)", wash: "rgba(245, 158, 11, 0.1)" },
  gap: { label: "Gap", color: "var(--critical)", wash: "rgba(239, 68, 68, 0.1)" },
  no_evidence: { label: "No evidence", color: "var(--ink-3)", wash: "rgba(255, 255, 255, 0.05)" },
};

export function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.no_evidence;
}

export function StatusBadge({ status }) {
  const m = statusMeta(status);
  return (
    <Badge color={m.color} wash={m.wash}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.color, boxShadow: `0 0 8px ${m.color}` }} />
      {m.label}
    </Badge>
  );
}

export function HealthBar({ value }) {
  const color = value >= 75 ? "var(--good)" : value >= 55 ? "var(--warn)" : value >= 35 ? "var(--serious)" : "var(--critical)";
  return (
    <div className="flex items-center gap-3 min-w-[120px]">
      <div className="flex-1 h-1 rounded-full overflow-hidden bg-[var(--surface-inset)]">
        <div className="h-full rounded-full transition-all duration-700 ease-out relative" style={{ width: `${value}%`, background: color }}>
          <div className="absolute right-0 top-0 bottom-0 w-4 bg-white opacity-50 blur-[2px]" />
        </div>
      </div>
      <span className="tnum text-xs font-semibold w-8 text-right drop-shadow-md" style={{ color }}>{value}%</span>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8 animate-in">
      <div>
        {eyebrow && (
          <div className="text-[11px] font-bold uppercase tracking-[0.2em] mb-2 text-[var(--brand)] drop-shadow-[0_0_8px_var(--brand-glow)]">
            {eyebrow}
          </div>
        )}
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">{title}</h1>
        {subtitle && <p className="text-sm max-w-3xl text-[var(--ink-2)] leading-relaxed">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

export function DocRefLink({ id, children }) {
  return (
    <Link
      to={`/documents/${encodeURIComponent(id)}`}
      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono transition-all hover:bg-[var(--brand-glow)] border"
      style={{ color: "var(--brand)", background: "rgba(79,143,232,0.1)", borderColor: "rgba(79,143,232,0.2)" }}
    >
      {children || id}
    </Link>
  );
}

export function EmptyState({ icon, title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-in">
      <div className="text-5xl mb-4 text-[var(--brand)] opacity-70 filter drop-shadow-[0_0_15px_var(--brand-glow)]">{icon}</div>
      <div className="font-semibold text-lg text-white">{title}</div>
      {hint && <div className="text-sm mt-2 max-w-sm text-[var(--ink-2)] leading-relaxed">{hint}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} />;
}