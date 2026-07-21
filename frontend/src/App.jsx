// import { useState, useEffect } from "react";
// import { Routes, Route, NavLink, useLocation } from "react-router-dom";
// import Dashboard from "./pages/Dashboard.jsx";
// import Copilot from "./pages/Copilot.jsx";
// import Agent from "./pages/Agent.jsx";
// import Graph from "./pages/Graph.jsx";
// import Documents from "./pages/Documents.jsx";
// import DocumentView from "./pages/DocumentView.jsx";
// import Assets from "./pages/Assets.jsx";
// import Compliance from "./pages/Compliance.jsx";
// import Lessons from "./pages/Lessons.jsx";
// import Alerts from "./pages/Alerts.jsx";
// import Drawings from "./pages/Drawings.jsx";
// import { api } from "./api.js";
// import { ErrorBoundary } from "./components/ui.jsx";

// const NAV = [
//   { to: "/", label: "Overview", icon: "◔", end: true },
//   { to: "/copilot", label: "Knowledge Copilot", icon: "✦" },
//   { to: "/agent", label: "Planning Agent", icon: "✳" },
//   { to: "/graph", label: "Knowledge Graph", icon: "⬡" },
//   { to: "/assets", label: "Maintenance Intelligence", icon: "⚙" },
//   { to: "/lessons", label: "Lessons Learned", icon: "◈" },
//   { to: "/alerts", label: "Alerts", icon: "◉", badgeKey: "alerts" },
//   { to: "/compliance", label: "Compliance", icon: "❖" },
//   { to: "/drawings", label: "Drawings & Standards", icon: "⬔" },
//   { to: "/documents", label: "Documents", icon: "▤" },
// ];

// function Brand() {
//   return (
//     <div className="flex items-center gap-2.5">
//       <div
//         className="w-9 h-9 rounded-[10px] flex items-center justify-center text-white font-bold text-lg shrink-0"
//         style={{ background: "linear-gradient(135deg, #2a78d6, #1c5cab)" }}
//       >
//         A
//       </div>
//       <div>
//         <div className="font-bold tracking-tight leading-none">ATLAS</div>
//         <div className="text-[11px] mt-0.5" style={{ color: "var(--ink-3)" }}>Knowledge Intelligence</div>
//       </div>
//     </div>
//   );
// }

// function NavLinks({ onNavigate, badges }) {
//   return (
//     <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
//       {NAV.map((item) => (
//         <NavLink
//           key={item.to}
//           to={item.to}
//           end={item.end}
//           onClick={onNavigate}
//           className={({ isActive }) =>
//             `flex items-center gap-3 px-3 py-2.5 rounded-[10px] text-sm font-medium transition-all ${
//               isActive ? "" : "hover:bg-[var(--surface-2)]"
//             }`
//           }
//           style={({ isActive }) =>
//             isActive
//               ? { background: "var(--brand-wash)", color: "var(--brand-strong)" }
//               : { color: "var(--ink-2)" }
//           }
//         >
//           <span className="w-5 text-center text-base opacity-80">{item.icon}</span>
//           <span className="flex-1">{item.label}</span>
//           {item.badgeKey && badges?.[item.badgeKey] > 0 && (
//             <span className="tnum text-[11px] font-bold px-1.5 rounded-full text-white" style={{ background: "var(--critical)" }}>
//               {badges[item.badgeKey]}
//             </span>
//           )}
//         </NavLink>
//       ))}
//     </nav>
//   );
// }

// export default function App() {
//   const location = useLocation();
//   const [drawerOpen, setDrawerOpen] = useState(false);
//   const [badges, setBadges] = useState({});

//   // Close the mobile drawer whenever the route changes
//   useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

//   // Live alert count for the nav badge; refresh on navigation
//   useEffect(() => {
//     api.alerts().then((d) => setBadges({ alerts: d.active })).catch(() => {});
//   }, [location.pathname]);

//   return (
//     <div className="flex min-h-screen">
//       {/* Desktop sidebar */}
//       <aside
//         className="hidden lg:flex w-[248px] shrink-0 flex-col border-r sticky top-0 h-screen"
//         style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
//       >
//         <div className="px-5 h-16 flex items-center border-b" style={{ borderColor: "var(--line-1)" }}>
//           <Brand />
//         </div>
//         <NavLinks badges={badges} />
//         <div className="px-5 py-4 border-t text-[11px] leading-relaxed" style={{ borderColor: "var(--line-1)", color: "var(--ink-3)" }}>
//           <div className="font-semibold mb-1" style={{ color: "var(--ink-2)" }}>Refinery · Unit 300</div>
//           Crude Distillation demo corpus
//         </div>
//       </aside>

//       {/* Mobile top bar */}
//       <header
//         className="lg:hidden fixed top-0 inset-x-0 h-14 z-40 flex items-center justify-between px-4 border-b backdrop-blur"
//         style={{ background: "rgba(255,255,255,0.9)", borderColor: "var(--line-1)" }}
//       >
//         <Brand />
//         <button
//           onClick={() => setDrawerOpen(true)}
//           aria-label="Open menu"
//           className="w-10 h-10 rounded-[10px] flex items-center justify-center border"
//           style={{ borderColor: "var(--line-1)", background: "var(--surface-1)" }}
//         >
//           <div className="space-y-[3px]">
//             <span className="block w-4 h-[2px] rounded" style={{ background: "var(--ink-1)" }} />
//             <span className="block w-4 h-[2px] rounded" style={{ background: "var(--ink-1)" }} />
//             <span className="block w-4 h-[2px] rounded" style={{ background: "var(--ink-1)" }} />
//           </div>
//         </button>
//       </header>

//       {/* Mobile drawer */}
//       {drawerOpen && (
//         <div className="lg:hidden fixed inset-0 z-50">
//           <div className="absolute inset-0 bg-black/40 animate-in" onClick={() => setDrawerOpen(false)} />
//           <aside
//             className="absolute left-0 top-0 h-full w-[280px] flex flex-col shadow-2xl"
//             style={{ background: "var(--surface-1)", animation: "fadeUp 0.2s ease" }}
//           >
//             <div className="px-5 h-14 flex items-center justify-between border-b" style={{ borderColor: "var(--line-1)" }}>
//               <Brand />
//               <button onClick={() => setDrawerOpen(false)} aria-label="Close menu" className="text-xl px-2" style={{ color: "var(--ink-3)" }}>✕</button>
//             </div>
//             <NavLinks badges={badges} onNavigate={() => setDrawerOpen(false)} />
//           </aside>
//         </div>
//       )}

//       <main className="flex-1 min-w-0">
//         <div key={location.pathname} className="animate-in max-w-[1240px] mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8 pt-[76px] lg:pt-8">
//           {/* Keyed on pathname above, so navigating away from a page that
//               errored remounts a fresh ErrorBoundary — the caught error
//               doesn't linger and block the next page. */}
//           <ErrorBoundary>
//             <Routes>
//               <Route path="/" element={<Dashboard />} />
//               <Route path="/copilot" element={<Copilot />} />
//               <Route path="/agent" element={<Agent />} />
//               <Route path="/graph" element={<Graph />} />
//               <Route path="/assets" element={<Assets />} />
//               <Route path="/lessons" element={<Lessons />} />
//               <Route path="/alerts" element={<Alerts />} />
//               <Route path="/compliance" element={<Compliance />} />
//               <Route path="/drawings" element={<Drawings />} />
//               <Route path="/documents" element={<Documents />} />
//               <Route path="/documents/:id" element={<DocumentView />} />
//             </Routes>
//           </ErrorBoundary>
//         </div>
//       </main>
//     </div>
//   );
// }
import { useState, useEffect } from "react";
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Copilot from "./pages/Copilot.jsx";
import Agent from "./pages/Agent.jsx";
import Graph from "./pages/Graph.jsx";
import Documents from "./pages/Documents.jsx";
import DocumentView from "./pages/DocumentView.jsx";
import Assets from "./pages/Assets.jsx";
import Compliance from "./pages/Compliance.jsx";
import Lessons from "./pages/Lessons.jsx";
import Alerts from "./pages/Alerts.jsx";
import Drawings from "./pages/Drawings.jsx";
import { api } from "./api.js";
import { ErrorBoundary } from "./components/ui.jsx";

const NAV = [
  { to: "/", label: "Overview", icon: "◔", end: true },
  { to: "/copilot", label: "Knowledge Copilot", icon: "✦" },
  { to: "/agent", label: "Planning Agent", icon: "✳" },
  { to: "/graph", label: "Knowledge Graph", icon: "⬡" },
  { to: "/assets", label: "Maintenance Intelligence", icon: "⚙" },
  { to: "/lessons", label: "Lessons Learned", icon: "◈" },
  { to: "/alerts", label: "Alerts", icon: "◉", badgeKey: "alerts" },
  { to: "/compliance", label: "Compliance", icon: "❖" },
  { to: "/drawings", label: "Drawings & Standards", icon: "⬔" },
  { to: "/documents", label: "Documents", icon: "▤" },
];

function Brand() {
  return (
    <div className="flex items-center gap-3 relative group">
      <div className="absolute -inset-1 bg-gradient-to-r from-[var(--brand)] to-blue-600 rounded-xl blur-md opacity-10 group-hover:opacity-30 transition duration-700 pointer-events-none" />
      <div
        className="relative w-9 h-9 rounded-[10px] flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-md"
        style={{ background: "linear-gradient(135deg, #3b82f6, #1d4ed8)" }}
      >
        A
      </div>
      <div className="relative z-10">
        <div className="font-extrabold tracking-wider text-white leading-none">ATLAS</div>
        <div className="text-[10px] mt-1 uppercase tracking-widest text-[var(--ink-3)] font-semibold">Knowledge Intelligence</div>
      </div>
    </div>
  );
}

function NavLinks({ onNavigate, badges }) {
  return (
    <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all duration-300 group relative overflow-hidden ${
              isActive 
                ? "bg-gradient-to-r from-[#1A263B] to-[#121C2D] text-white shadow-[0_0_15px_rgba(79,143,232,0.15)] border border-[var(--brand)]/30" 
                : "text-[var(--ink-2)] hover:text-white hover:bg-white/[0.03] hover:translate-x-1"
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-[var(--brand)] shadow-[0_0_10px_var(--brand)]" />
              )}
              <span className={`w-5 text-center text-base transition-colors duration-300 ${isActive ? 'text-[var(--brand)] drop-shadow-[0_0_8px_var(--brand)]' : 'opacity-70 group-hover:opacity-100'}`}>
                {item.icon}
              </span>
              <span className="flex-1 tracking-wide">{item.label}</span>
              {item.badgeKey && badges?.[item.badgeKey] > 0 && (
                <span className="tnum text-[10px] font-extrabold px-2 py-0.5 rounded-full text-white bg-[var(--critical)] shadow-[0_0_10px_var(--critical)] animate-pulse">
                  {badges[item.badgeKey]}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [badges, setBadges] = useState({});

  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

  useEffect(() => {
    api.alerts().then((d) => setBadges({ alerts: d.active })).catch(() => {});
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen bg-[#04070D] text-white">
      {/* Desktop sidebar */}
      <aside
        className="hidden lg:flex w-[260px] shrink-0 flex-col border-r sticky top-0 h-screen bg-gradient-to-b from-[#070B14] to-[#04070D] border-white/5 shadow-2xl z-20"
      >
        <div className="px-6 h-20 flex items-center border-b border-white/5">
          <Brand />
        </div>
        <NavLinks badges={badges} />
        <div className="px-6 py-5 border-t border-white/5 text-[11px] leading-relaxed bg-[#050810]/50">
          <div className="font-bold text-white tracking-wide mb-0.5">Refinery · Unit 300</div>
          <div className="text-[var(--ink-3)] font-medium">Crude Distillation demo corpus</div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header
        className="lg:hidden fixed top-0 inset-x-0 h-16 z-40 flex items-center justify-between px-5 border-b backdrop-blur-md bg-[#070B14]/90 border-white/10"
      >
        <Brand />
        <button
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="w-10 h-10 rounded-xl flex items-center justify-center border border-white/10 bg-[#121C2D] text-white hover:border-[var(--brand)] transition-colors"
        >
          <div className="space-y-[3px]">
            <span className="block w-4 h-[2px] rounded bg-white" />
            <span className="block w-4 h-[2px] rounded bg-white" />
            <span className="block w-4 h-[2px] rounded bg-white" />
          </div>
        </button>
      </header>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in" onClick={() => setDrawerOpen(false)} />
          <aside
            className="absolute left-0 top-0 h-full w-[280px] flex flex-col shadow-2xl bg-[#070B14] border-r border-white/10"
            style={{ animation: "fadeUp 0.2s ease" }}
          >
            <div className="px-6 h-20 flex items-center justify-between border-b border-white/5">
              <Brand />
              <button onClick={() => setDrawerOpen(false)} aria-label="Close menu" className="text-xl px-2 text-[var(--ink-3)] hover:text-white">✕</button>
            </div>
            <NavLinks badges={badges} onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 bg-[#04070D]">
        <div key={location.pathname} className="animate-in max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-10 py-6 lg:py-10 pt-[88px] lg:pt-10">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/copilot" element={<Copilot />} />
              <Route path="/agent" element={<Agent />} />
              <Route path="/graph" element={<Graph />} />
              <Route path="/assets" element={<Assets />} />
              <Route path="/lessons" element={<Lessons />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/compliance" element={<Compliance />} />
              <Route path="/drawings" element={<Drawings />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/documents/:id" element={<DocumentView />} />
            </Routes>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}