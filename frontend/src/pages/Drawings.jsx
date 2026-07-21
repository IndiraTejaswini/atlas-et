import { useEffect, useState, useRef } from "react";
import { api } from "../api.js";
import { Card, PageHeader, Badge, Skeleton, Tabs } from "../components/ui.jsx";

/* ---------------- P&ID computer-vision view ---------------- */
function PidVision() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(true);
  const [drag, setDrag] = useState(false);
  const [source, setSource] = useState("sample");
  const inputRef = useRef(null);

  useEffect(() => {
    api.parseSamplePid().then((r) => { setResult(r); setBusy(false); }).catch(() => setBusy(false));
  }, []);

  async function handleFile(file) {
    if (!file) return;
    setBusy(true); setResult(null); setSource(file.name);
    try { setResult(await api.parsePid(file)); } catch { /* ignore */ }
    setBusy(false);
  }

  const c = result?.counts;
  return (
    <>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <p className="text-sm max-w-2xl" style={{ color: "var(--ink-2)" }}>
          Classical computer vision digitises the drawing itself — not just its text. Instrument
          balloons are found by Hough circle detection, equipment by contour/shape analysis, piping
          by probabilistic Hough lines; a single OCR pass binds each tag to the symbol it labels, and
          line endpoints landing on two symbols become real <b>connectivity</b> in the knowledge graph.
        </p>
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
          onClick={() => inputRef.current?.click()}
          className="flex items-center gap-3 px-5 py-3 rounded-[12px] border-2 border-dashed cursor-pointer transition-all shrink-0"
          style={{ borderColor: drag ? "var(--brand)" : "var(--line-1)", background: drag ? "var(--brand-wash)" : "var(--surface-inset)" }}
        >
          <span className="text-xl">{busy ? "⏳" : "⬆"}</span>
          <span className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
            {busy ? "Analysing drawing…" : "Drop your own P&ID"}
          </span>
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleFile(e.target.files[0])} />
        </div>
      </div>

      {busy && <Skeleton className="h-[420px]" />}

      {result && !busy && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
            {[
              ["Equipment symbols", c.equipment, "var(--c2)"],
              ["Instrument balloons", c.instruments, "var(--c1)"],
              ["Process lines", c.lines, "var(--c6)"],
              ["Connections", c.connections, "var(--c7)"],
              ["Tags read", c.tagged_symbols, "var(--c5)"],
            ].map(([label, val, color]) => (
              <Card key={label} className="p-4">
                <div className="tnum text-[26px] font-bold" style={{ color }}>{val}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>{label}</div>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm" style={{ color: "var(--ink-1)" }}>Detection overlay</h3>
                <span className="text-xs" style={{ color: "var(--ink-3)" }}>{result.source || source}</span>
              </div>
              {result.overlay_png_b64 ? (
                <img
                  src={`data:image/png;base64,${result.overlay_png_b64}`}
                  alt="P&ID detection overlay"
                  className="w-full rounded-[10px] border"
                  style={{ borderColor: "var(--line-1)" }}
                />
              ) : (
                <p className="text-sm" style={{ color: "var(--ink-3)" }}>No overlay produced.</p>
              )}
              <div className="flex items-center gap-4 mt-3 text-xs" style={{ color: "var(--ink-2)" }}>
                <LegendDot color="rgb(12,163,42)" label="Equipment" />
                <LegendDot color="rgb(235,104,52)" label="Instrument" />
                <LegendDot color="rgb(42,120,219)" label="Process line" />
              </div>
            </Card>

            <div className="space-y-4">
              <Card className="p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>
                  Tags digitised from the drawing
                </h3>
                {result.tags_found?.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {result.tags_found.map((t) => (
                      <span key={t} className="font-mono text-xs font-bold px-2 py-1 rounded-md"
                        style={{ background: "var(--brand-wash)", color: "var(--brand-strong)" }}>{t}</span>
                    ))}
                  </div>
                ) : <p className="text-sm" style={{ color: "var(--ink-3)" }}>No tags recognised.</p>}
              </Card>

              <Card className="p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>
                  Extracted connectivity
                </h3>
                {result.connections?.length ? (
                  <div className="space-y-1.5">
                    {result.connections.map((cn, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="font-mono font-semibold truncate" style={{ color: "var(--ink-1)" }}>{cn.from}</span>
                        <span style={{ color: "var(--ink-3)" }}>→</span>
                        <span className="font-mono font-semibold truncate" style={{ color: "var(--ink-1)" }}>{cn.to}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-sm" style={{ color: "var(--ink-3)" }}>No connectivity inferred.</p>}
                <p className="text-[11px] mt-3 pt-3 border-t leading-relaxed" style={{ borderColor: "var(--line-1)", color: "var(--ink-3)" }}>
                  {result.graph_updated ? (
                    <>
                      Tagged pairs became <span className="font-mono">connected_to</span> edges in the
                      knowledge graph just now (+{result.new_graph_nodes} nodes, +{result.new_graph_edges} edges,
                      as <span className="font-mono">{result.graph_doc_id}</span>). <a href="/graph" className="font-semibold" style={{ color: "var(--brand)" }}>View in graph →</a>
                    </>
                  ) : result.tags_found?.length ? (
                    <>This drawing's connectivity is already in the knowledge graph as <span className="font-mono">{result.graph_doc_id}</span>.</>
                  ) : (
                    "No tagged symbols were found, so nothing was added to the knowledge graph — untagged connections aren't linked."
                  )}
                </p>
              </Card>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function LegendDot({ color, label }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: color }} />
      {label}
    </span>
  );
}

/* ---------------- Industrial ontology view ---------------- */
function OntologyView() {
  const [ont, setOnt] = useState(null);
  useEffect(() => { api.ontology().then(setOnt); }, []);
  if (!ont) return <Skeleton className="h-[400px]" />;

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {ont.standards.map((s) => (
          <Card key={s.id} className="p-5">
            <div className="flex items-center gap-2 mb-1">
              <Badge color="var(--c7)" wash="#ecebf7">{s.id}</Badge>
              <span className="text-sm font-semibold" style={{ color: "var(--ink-1)" }}>{s.role}</span>
            </div>
            <p className="text-xs mt-1.5" style={{ color: "var(--ink-2)" }}>{s.note}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5 mb-4">
        <h3 className="font-semibold mb-1" style={{ color: "var(--ink-1)" }}>ISA-95 physical hierarchy</h3>
        <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Every asset is addressable by its standard location path</p>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          {[["Enterprise", ont.isa95.enterprise], ["Site", ont.isa95.site], ["Area", ont.isa95.area], ["Unit", ont.isa95.unit]].map(([lvl, val], i, arr) => (
            <span key={lvl} className="flex items-center gap-2">
              <span className="px-3 py-1.5 rounded-[10px]" style={{ background: "var(--surface-inset)" }}>
                <span className="text-[10px] uppercase tracking-wider block" style={{ color: "var(--ink-3)" }}>{lvl}</span>
                <span className="font-medium" style={{ color: "var(--ink-1)" }}>{val}</span>
              </span>
              {i < arr.length - 1 && <span style={{ color: "var(--ink-3)" }}>›</span>}
            </span>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="flex items-baseline justify-between mb-1">
            <h3 className="font-semibold" style={{ color: "var(--ink-1)" }}>ISO 14224 equipment taxonomy</h3>
            <span className="tnum text-xs font-semibold" style={{ color: "var(--good)" }}>{ont.coverage.pct_tags}% classified</span>
          </div>
          <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>{ont.coverage.tags_classified} of {ont.coverage.tags_total} tags mapped to a standard class</p>
          <div className="space-y-2">
            {Object.entries(ont.equipment_by_class).map(([cls, tags]) => (
              <div key={cls} className="flex items-start justify-between gap-3 p-2.5 rounded-[10px]" style={{ background: "var(--surface-inset)" }}>
                <span className="text-sm font-medium" style={{ color: "var(--ink-1)" }}>{cls}</span>
                <div className="flex gap-1 flex-wrap justify-end">
                  {tags.map((t) => (
                    <span key={t} className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "#fff", color: "var(--ink-2)" }}>{t}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-baseline justify-between mb-1">
            <h3 className="font-semibold" style={{ color: "var(--ink-1)" }}>ISO 14224 failure-mode codes</h3>
            <span className="tnum text-xs font-semibold" style={{ color: "var(--good)" }}>{ont.coverage.pct_modes}% coded</span>
          </div>
          <p className="text-xs mb-4" style={{ color: "var(--ink-3)" }}>Standard codes make failures comparable across sites and vendors</p>
          <div className="space-y-1.5">
            {ont.failure_modes.map((f) => (
              <div key={f.mode} className="flex items-center justify-between gap-2 text-sm">
                <span style={{ color: "var(--ink-2)" }}>{f.mode}</span>
                <span className="flex items-center gap-2 shrink-0">
                  <span className="text-[11px]" style={{ color: "var(--ink-3)" }}>{f.iso14224_label}</span>
                  <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: "#ecebf7", color: "var(--c7)" }}>{f.iso14224_code}</span>
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

/* ---------------- QMS integration surface ---------------- */
function QmsView() {
  const [ncr, setNcr] = useState(null);
  useEffect(() => { api.qmsNcr().then(setNcr); }, []);
  if (!ncr) return <Skeleton className="h-[400px]" />;

  const SEV = { critical: "var(--critical)", high: "var(--serious)", medium: "var(--warn)", low: "var(--ink-3)" };
  return (
    <>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <p className="text-sm max-w-2xl" style={{ color: "var(--ink-2)" }}>
          ATLAS emits non-conformance records in a documented, stable contract that a QMS
          (SAP QM, ETQ, MasterControl, Intelex…) can import by file drop or webhook. Quality
          deviations and compliance gaps are normalised into one schema with severity, evidence
          and ISO 14224 classification. <b>This is an integration surface with a published
          contract — not a vendor-specific connector.</b>
        </p>
        <a href={api.qmsCsvUrl()} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold text-white shrink-0"
          style={{ background: "var(--brand)" }}>⬇ Export NCRs (CSV)</a>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <Card className="p-4"><div className="tnum text-2xl font-bold">{ncr.record_count}</div><div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Records</div></Card>
        <Card className="p-4"><div className="tnum text-2xl font-bold" style={{ color: "var(--critical)" }}>{ncr.records.filter((r) => r.criticality === 1).length}</div><div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Criticality 1</div></Card>
        <Card className="p-4"><div className="text-2xl font-bold">v{ncr.contract_version}</div><div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Contract version</div></Card>
        <Card className="p-4"><div className="text-2xl font-bold">{Object.keys(ncr.schema).length}</div><div className="text-xs mt-0.5" style={{ color: "var(--ink-2)" }}>Schema fields</div></Card>
      </div>

      <Card className="overflow-hidden mb-4">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px]">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)", background: "var(--surface-inset)" }}>
                <th className="px-4 py-3">NCR ID</th><th className="px-2 py-3">Title</th>
                <th className="px-2 py-3">Source</th><th className="px-2 py-3">Equipment</th>
                <th className="px-2 py-3">ISO class</th><th className="px-2 py-3">Crit.</th>
              </tr>
            </thead>
            <tbody>
              {ncr.records.map((r) => (
                <tr key={r.ncr_id} className="border-t" style={{ borderColor: "var(--line-1)" }}>
                  <td className="px-4 py-3 font-mono text-[11px] font-bold" style={{ color: "var(--brand-strong)" }}>{r.ncr_id}</td>
                  <td className="px-2 py-3 text-sm" style={{ color: "var(--ink-1)" }}>{r.title}</td>
                  <td className="px-2 py-3 text-xs" style={{ color: "var(--ink-2)" }}>{r.source.replace("_", " ")}</td>
                  <td className="px-2 py-3 font-mono text-xs" style={{ color: "var(--ink-2)" }}>{r.equipment_tag || "—"}</td>
                  <td className="px-2 py-3 text-xs" style={{ color: "var(--ink-2)" }}>{r.iso14224_class || "—"}</td>
                  <td className="px-2 py-3">
                    <span className="tnum text-xs font-bold px-2 py-0.5 rounded-full text-white" style={{ background: SEV[r.severity] }}>{r.criticality}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold mb-3" style={{ color: "var(--ink-1)" }}>Published contract</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>NCR schema</div>
            <div className="space-y-1">
              {Object.entries(ncr.schema).map(([k, v]) => (
                <div key={k} className="text-[11px] flex gap-2">
                  <span className="font-mono font-semibold shrink-0" style={{ color: "var(--brand-strong)" }}>{k}</span>
                  <span style={{ color: "var(--ink-3)" }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--ink-3)" }}>Webhook contract</div>
            <pre className="text-[11px] p-3 rounded-[10px] overflow-x-auto" style={{ background: "var(--surface-inset)", color: "var(--ink-2)" }}>
{JSON.stringify(ncr.webhook_contract, null, 2)}
            </pre>
          </div>
        </div>
      </Card>
    </>
  );
}

export default function Drawings() {
  const [tab, setTab] = useState("pid");
  return (
    <>
      <PageHeader
        eyebrow="Drawing Digitisation & Standards"
        title="P&ID vision, industrial ontology & QMS"
        subtitle="Computer vision that reads engineering drawings into the knowledge graph, an ISO 14224 / ISA-95 ontology so the graph speaks the industry's language, and a documented QMS integration contract."
      />
      <Tabs
        tabs={[
          { key: "pid", label: "P&ID Computer Vision" },
          { key: "ontology", label: "Industrial Ontology" },
          { key: "qms", label: "QMS Integration" },
        ]}
        active={tab}
        onChange={setTab}
      />
      <div className="mt-4">
        {tab === "pid" && <PidVision />}
        {tab === "ontology" && <OntologyView />}
        {tab === "qms" && <QmsView />}
      </div>
    </>
  );
}
