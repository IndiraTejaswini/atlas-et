// import { useEffect, useRef, useState, useMemo } from "react";
// import { useNavigate } from "react-router-dom";
// import {
//   forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide,
// } from "d3-force";
// import { api } from "../api.js";
// import { Card, PageHeader, Badge } from "../components/ui.jsx";

// const NODE_STYLE = {
//   document: { color: "var(--c1)", r: 7, label: "Document" },
//   equipment: { color: "var(--c6)", r: 9, label: "Equipment" },
//   standard: { color: "var(--c2)", r: 7, label: "Standard / Reg" },
//   failure_mode: { color: "var(--c8)", r: 8, label: "Failure mode" },
//   person: { color: "var(--c7)", r: 6, label: "Person" },
// };

// export default function Graph() {
//   const [data, setData] = useState(null);
//   const [hover, setHover] = useState(null);
//   const [selected, setSelected] = useState(null);
//   const [filters, setFilters] = useState({ document: true, equipment: true, standard: true, failure_mode: true, person: true });
//   const svgRef = useRef(null);
//   const nodesRef = useRef([]);
//   const navigate = useNavigate();

//   useEffect(() => {
//     api.graph().then(setData);
//   }, []);

//   const filtered = useMemo(() => {
//     if (!data) return null;
//     const nodes = data.nodes.filter((n) => filters[n.type]);
//     const ids = new Set(nodes.map((n) => n.id));
//     const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
//     return { nodes: nodes.map((n) => ({ ...n })), edges: edges.map((e) => ({ ...e })) };
//   }, [data, filters]);

//   useEffect(() => {
//     if (!filtered || !svgRef.current) return;
//     const W = svgRef.current.clientWidth, H = 560;
//     const nodes = filtered.nodes;
//     const links = filtered.edges.map((e) => ({ ...e }));
//     nodesRef.current = nodes;

//     const sim = forceSimulation(nodes)
//       .force("link", forceLink(links).id((d) => d.id).distance((l) => (l.relation === "references" ? 70 : 55)).strength(0.35))
//       .force("charge", forceManyBody().strength(-130))
//       .force("center", forceCenter(W / 2, H / 2))
//       .force("collide", forceCollide().radius((d) => (NODE_STYLE[d.type]?.r || 6) + 6))
//       .alpha(1).alphaDecay(0.028);

//     const svg = svgRef.current;
//     function render() {
//       const lineEls = svg.querySelectorAll(".gedge");
//       links.forEach((l, i) => {
//         const el = lineEls[i];
//         if (!el) return;
//         el.setAttribute("x1", l.source.x); el.setAttribute("y1", l.source.y);
//         el.setAttribute("x2", l.target.x); el.setAttribute("y2", l.target.y);
//       });
//       const nodeEls = svg.querySelectorAll(".gnode");
//       nodes.forEach((n, i) => {
//         const el = nodeEls[i];
//         if (el) el.setAttribute("transform", `translate(${n.x},${n.y})`);
//       });
//     }
//     sim.on("tick", render);
//     return () => sim.stop();
//   }, [filtered]);

//   const selectedEdges = selected
//     ? filtered?.edges.filter((e) => (e.source.id || e.source) === selected.id || (e.target.id || e.target) === selected.id)
//     : [];

//   return (
//     <>
//       <PageHeader
//         eyebrow="Unified Knowledge Graph"
//         title="How everything connects"
//         subtitle="Every document, equipment tag, standard, failure mode and engineer, linked into one graph. This is what lets a query about a pump reach the OEM manual and a retirement handover note at once."
//       />

//       <div className="flex items-center gap-2 mb-4 flex-wrap">
//         {Object.entries(NODE_STYLE).map(([type, s]) => (
//           <button
//             key={type}
//             onClick={() => setFilters((f) => ({ ...f, [type]: !f[type] }))}
//             className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
//             style={{
//               borderColor: filters[type] ? "transparent" : "var(--line-1)",
//               background: filters[type] ? "var(--surface-2)" : "transparent",
//               color: filters[type] ? "var(--ink-1)" : "var(--ink-3)",
//               opacity: filters[type] ? 1 : 0.55,
//             }}
//           >
//             <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
//             {s.label}
//           </button>
//         ))}
//         {data && (
//           <span className="ml-auto text-xs" style={{ color: "var(--ink-3)" }}>
//             {filtered?.nodes.length} nodes · {filtered?.edges.length} edges
//           </span>
//         )}
//       </div>

//       <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
//         <Card className="relative overflow-hidden p-0" style={{ background: "var(--surface-1)" }}>
//           <svg ref={svgRef} width="100%" height="560" style={{ display: "block" }}>
//             {filtered?.edges.map((e, i) => (
//               <line key={i} className="gedge" stroke="var(--line-1)" strokeWidth="1" />
//             ))}
//             {filtered?.nodes.map((n) => {
//               const s = NODE_STYLE[n.type];
//               const isSel = selected?.id === n.id;
//               return (
//                 <g
//                   key={n.id}
//                   className="gnode"
//                   style={{ cursor: "pointer" }}
//                   onMouseEnter={() => setHover(n)}
//                   onMouseLeave={() => setHover(null)}
//                   onClick={() => setSelected(n)}
//                 >
//                   <circle
//                     r={(s?.r || 6) + (isSel ? 4 : 0)}
//                     fill={s?.color || "#888"}
//                     stroke="#fff"
//                     strokeWidth={isSel ? 3 : 1.5}
//                     opacity={selected && !isSel && !isNeighbor(n, selected, filtered.edges) ? 0.25 : 1}
//                   />
//                   {(isSel || (s?.r || 0) >= 8) && (
//                     <text x={(s?.r || 6) + 5} y="4" fontSize="11" fontWeight="600" fill="var(--ink-2)" style={{ pointerEvents: "none" }}>
//                       {n.label}
//                     </text>
//                   )}
//                 </g>
//               );
//             })}
//           </svg>

//           {hover && (
//             <div
//               className="absolute top-3 left-3 px-3 py-2 rounded-[10px] text-xs pointer-events-none"
//               style={{ background: "var(--ink-1)", color: "#fff", boxShadow: "var(--shadow-pop)" }}
//             >
//               <div className="font-bold">{hover.label}</div>
//               <div className="opacity-70 mt-0.5">{NODE_STYLE[hover.type]?.label} · {hover.weight} links</div>
//             </div>
//           )}
//         </Card>

//         <Card className="p-5">
//           {selected ? (
//             <div className="animate-in">
//               <div className="flex items-center gap-2 mb-1">
//                 <span className="w-3 h-3 rounded-full" style={{ background: NODE_STYLE[selected.type]?.color }} />
//                 <Badge>{NODE_STYLE[selected.type]?.label}</Badge>
//               </div>
//               <h3 className="font-bold text-lg mt-2 mb-3 break-words" style={{ color: "var(--ink-1)" }}>{selected.label}</h3>
//               {selected.type === "document" && (
//                 <button
//                   onClick={() => navigate(`/documents/${selected.label}`)}
//                   className="w-full mb-4 py-2 rounded-[10px] text-sm font-semibold text-white"
//                   style={{ background: "var(--brand)" }}
//                 >
//                   Open document →
//                 </button>
//               )}
//               <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>
//                 Connections ({selectedEdges.length})
//               </div>
//               <div className="space-y-1.5 max-h-[360px] overflow-auto pr-1">
//                 {selectedEdges.map((e, i) => {
//                   const other = (e.source.id || e.source) === selected.id ? e.target : e.source;
//                   const otherNode = typeof other === "object" ? other : filtered.nodes.find((n) => n.id === other);
//                   return (
//                     <button
//                       key={i}
//                       onClick={() => setSelected(otherNode)}
//                       className="w-full flex items-center gap-2 text-left py-1.5 px-2 rounded-lg hover:bg-[var(--surface-2)] transition-colors"
//                     >
//                       <span className="w-2 h-2 rounded-full shrink-0" style={{ background: NODE_STYLE[otherNode?.type]?.color }} />
//                       <span className="text-xs font-medium truncate flex-1" style={{ color: "var(--ink-2)" }}>{otherNode?.label}</span>
//                       <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}>{e.relation}</span>
//                     </button>
//                   );
//                 })}
//               </div>
//             </div>
//           ) : (
//             <div className="text-center py-12">
//               <div className="text-3xl mb-3 opacity-50">⬡</div>
//               <div className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>Click any node</div>
//               <div className="text-xs mt-1" style={{ color: "var(--ink-3)" }}>Explore its connections and jump to source documents</div>
//             </div>
//           )}
//         </Card>
//       </div>
//     </>
//   );
// }

// function isNeighbor(node, selected, edges) {
//   return edges.some(
//     (e) =>
//       ((e.source.id || e.source) === selected.id && (e.target.id || e.target) === node.id) ||
//       ((e.target.id || e.target) === selected.id && (e.source.id || e.source) === node.id)
//   );
// }

import { useEffect, useRef, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide,
} from "d3-force";
import { api } from "../api.js";
import { Card, PageHeader, Badge } from "../components/ui.jsx";

// FIX: Replaced undefined var(--c...) with distinct, professional hex colors
const NODE_STYLE = {
  document: { color: "#3b82f6", r: 7, label: "Document" },       // Blue
  equipment: { color: "#f59e0b", r: 9, label: "Equipment" },      // Amber
  standard: { color: "#10b981", r: 7, label: "Standard / Reg" },  // Emerald
  failure_mode: { color: "#ef4444", r: 8, label: "Failure mode" }, // Red
  person: { color: "#8b5cf6", r: 6, label: "Person" },            // Purple
};

export default function Graph() {
  const [data, setData] = useState(null);
  const [hover, setHover] = useState(null);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ document: true, equipment: true, standard: true, failure_mode: true, person: true });
  const svgRef = useRef(null);
  const nodesRef = useRef([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.graph().then(setData);
  }, []);

  const filtered = useMemo(() => {
    if (!data) return null;
    const nodes = data.nodes.filter((n) => filters[n.type]);
    const ids = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes: nodes.map((n) => ({ ...n })), edges: edges.map((e) => ({ ...e })) };
  }, [data, filters]);

  useEffect(() => {
    if (!filtered || !svgRef.current) return;
    const W = svgRef.current.clientWidth, H = 560;
    const nodes = filtered.nodes;
    const links = filtered.edges.map((e) => ({ ...e }));
    nodesRef.current = nodes;

    const sim = forceSimulation(nodes)
      .force("link", forceLink(links).id((d) => d.id).distance((l) => (l.relation === "references" ? 70 : 55)).strength(0.35))
      .force("charge", forceManyBody().strength(-130))
      .force("center", forceCenter(W / 2, H / 2))
      .force("collide", forceCollide().radius((d) => (NODE_STYLE[d.type]?.r || 6) + 6))
      .alpha(1).alphaDecay(0.028);

    const svg = svgRef.current;
    function render() {
      const lineEls = svg.querySelectorAll(".gedge");
      links.forEach((l, i) => {
        const el = lineEls[i];
        if (!el) return;
        el.setAttribute("x1", l.source.x); el.setAttribute("y1", l.source.y);
        el.setAttribute("x2", l.target.x); el.setAttribute("y2", l.target.y);
      });
      const nodeEls = svg.querySelectorAll(".gnode");
      nodes.forEach((n, i) => {
        const el = nodeEls[i];
        if (el) el.setAttribute("transform", `translate(${n.x},${n.y})`);
      });
    }
    sim.on("tick", render);
    return () => sim.stop();
  }, [filtered]);

  const selectedEdges = selected
    ? filtered?.edges.filter((e) => (e.source.id || e.source) === selected.id || (e.target.id || e.target) === selected.id)
    : [];

  return (
    <>
      <PageHeader
        eyebrow="Unified Knowledge Graph"
        title="How everything connects"
        subtitle="Every document, equipment tag, standard, failure mode and engineer, linked into one graph. This is what lets a query about a pump reach the OEM manual and a retirement handover note at once."
      />

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {Object.entries(NODE_STYLE).map(([type, s]) => (
          <button
            key={type}
            onClick={() => setFilters((f) => ({ ...f, [type]: !f[type] }))}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
            style={{
              borderColor: filters[type] ? "transparent" : "var(--line-1)",
              background: filters[type] ? "var(--surface-2)" : "transparent",
              color: filters[type] ? "var(--ink-1)" : "var(--ink-3)",
              opacity: filters[type] ? 1 : 0.55,
            }}
          >
            {/* FIX: The background color here will now render correctly, filling the empty gap */}
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
            {s.label}
          </button>
        ))}
        {data && (
          <span className="ml-auto text-xs" style={{ color: "var(--ink-3)" }}>
            {filtered?.nodes.length} nodes · {filtered?.edges.length} edges
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        <Card className="relative overflow-hidden p-0" style={{ background: "var(--surface-1)" }}>
          <svg ref={svgRef} width="100%" height="560" style={{ display: "block" }}>
            {filtered?.edges.map((e, i) => (
              <line key={i} className="gedge" stroke="var(--line-1)" strokeWidth="1" />
            ))}
            {filtered?.nodes.map((n) => {
              const s = NODE_STYLE[n.type];
              const isSel = selected?.id === n.id;
              return (
                <g
                  key={n.id}
                  className="gnode"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHover(n)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => setSelected(n)}
                >
                  {/* FIX: Node fill colors will now display properly */}
                  <circle
                    r={(s?.r || 6) + (isSel ? 4 : 0)}
                    fill={s?.color || "#888"}
                    stroke="#fff"
                    strokeWidth={isSel ? 3 : 1.5}
                    opacity={selected && !isSel && !isNeighbor(n, selected, filtered.edges) ? 0.25 : 1}
                  />
                  {(isSel || (s?.r || 0) >= 8) && (
                    <text x={(s?.r || 6) + 5} y="4" fontSize="11" fontWeight="600" fill="var(--ink-2)" style={{ pointerEvents: "none" }}>
                      {n.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {hover && (
            <div
              className="absolute top-3 left-3 px-3 py-2 rounded-[10px] text-xs pointer-events-none z-10"
              style={{ 
                backgroundColor: "#1e293b", // Explicit dark slate background
                color: "#ffffff",           // Explicit white text
                border: "1px solid #334155",// Subtle dark border
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)" 
              }}
            >
              <div className="font-bold">{hover.label}</div>
              <div className="mt-0.5 font-medium" style={{ color: "#94a3b8" }}>
                {NODE_STYLE[hover.type]?.label} · {hover.weight || 0} links
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          {selected ? (
            <div className="animate-in">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: NODE_STYLE[selected.type]?.color }} />
                <Badge>{NODE_STYLE[selected.type]?.label}</Badge>
              </div>
              <h3 className="font-bold text-lg mt-2 mb-3 break-words" style={{ color: "var(--ink-1)" }}>{selected.label}</h3>
              {selected.type === "document" && (
                <button
                  onClick={() => navigate(`/documents/${selected.label}`)}
                  className="w-full mb-4 py-2 rounded-[10px] text-sm font-semibold text-white"
                  style={{ background: "var(--brand)" }}
                >
                  Open document →
                </button>
              )}
              <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>
                Connections ({selectedEdges.length})
              </div>
              <div className="space-y-1.5 max-h-[360px] overflow-auto pr-1">
                {selectedEdges.map((e, i) => {
                  const other = (e.source.id || e.source) === selected.id ? e.target : e.source;
                  const otherNode = typeof other === "object" ? other : filtered.nodes.find((n) => n.id === other);
                  return (
                    <button
                      key={i}
                      onClick={() => setSelected(otherNode)}
                      className="w-full flex items-center gap-2 text-left py-1.5 px-2 rounded-lg hover:bg-[var(--surface-2)] transition-colors"
                    >
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: NODE_STYLE[otherNode?.type]?.color }} />
                      <span className="text-xs font-medium truncate flex-1" style={{ color: "var(--ink-2)" }}>{otherNode?.label}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}>{e.relation}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="text-3xl mb-3 opacity-50">⬡</div>
              <div className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>Click any node</div>
              <div className="text-xs mt-1" style={{ color: "var(--ink-3)" }}>Explore its connections and jump to source documents</div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function isNeighbor(node, selected, edges) {
  return edges.some(
    (e) =>
      ((e.source.id || e.source) === selected.id && (e.target.id || e.target) === node.id) ||
      ((e.target.id || e.target) === selected.id && (e.source.id || e.source) === node.id)
  );
}