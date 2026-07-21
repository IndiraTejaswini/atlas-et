import { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Card, PageHeader, DocTypeBadge, Badge, Skeleton, docTypeMeta } from "../components/ui.jsx";

const FORMAT_LABEL = {
  pdf: "PDF", csv: "CSV / spreadsheet", xlsx: "Excel workbook",
  email: "Email (.eml)", image: "Scanned image (OCR)", markdown: "Markdown", text: "Text",
};

function IngestPanel({ onDone }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [formats, setFormats] = useState([]);
  const [ocr, setOcr] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { api.supportedFormats().then((f) => { setFormats(f.extensions); setOcr(f.ocr_available); }); }, []);

  async function handle(file) {
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await api.ingest(file);
      setResult(r);
      onDone();
    } catch {
      setResult({ error: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5 mb-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="max-w-md">
          <h3 className="font-semibold" style={{ color: "var(--ink-1)" }}>Ingest a new document</h3>
          <p className="text-xs mt-1" style={{ color: "var(--ink-3)" }}>
            Drop a <b>PDF, spreadsheet (CSV/XLSX), email, or scanned image</b>. Text is extracted
            {ocr && <> (<b>scanned forms are OCR'd</b>)</>}, entities parsed, the graph re-links, and every engine
            updates live — no re-training.
          </p>
          {formats.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-2">
              {formats.map((f) => (
                <span key={f} className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}>{f}</span>
              ))}
            </div>
          )}
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
          onClick={() => inputRef.current?.click()}
          className="flex items-center gap-3 px-5 py-3 rounded-[12px] border-2 border-dashed cursor-pointer transition-all shrink-0"
          style={{ borderColor: drag ? "var(--brand)" : "var(--line-1)", background: drag ? "var(--brand-wash)" : "var(--surface-inset)" }}
        >
          <span className="text-xl">{busy ? "⏳" : "⬆"}</span>
          <span className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>
            {busy ? "Processing…" : "Drop file or click to upload"}
          </span>
          <input ref={inputRef} type="file" accept=".md,.txt,.pdf,.csv,.xlsx,.xls,.eml,.png,.jpg,.jpeg,.tif,.tiff" className="hidden" onChange={(e) => handle(e.target.files[0])} />
        </div>
      </div>
      {result && !result.error && (
        <div className="mt-4 p-4 rounded-[12px] animate-in" style={{ background: "var(--good-wash)" }}>
          <div className="flex items-center gap-2 text-sm font-semibold mb-2 flex-wrap" style={{ color: "var(--good)" }}>
            ✓ Parsed {FORMAT_LABEL[result.format] || result.format} → extracted {result.chars_extracted} chars · ingested {result.doc.id} in {result.reindex_ms}ms · graph now {result.new_graph_nodes} nodes
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(result.entities).flatMap(([type, items]) =>
              Object.keys(items).slice(0, 8).map((name) => (
                <span key={type + name} className="px-2 py-0.5 rounded-md text-xs font-medium" style={{ background: "#fff", color: "var(--ink-2)" }}>
                  {name}
                </span>
              ))
            )}
          </div>
        </div>
      )}
      {result?.error && <div className="mt-3 text-sm" style={{ color: "var(--critical)" }}>Upload failed.</div>}
    </Card>
  );
}

export default function Documents() {
  const [docs, setDocs] = useState(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const navigate = useNavigate();

  const load = () => api.documents().then(setDocs);
  useEffect(() => { load(); }, []);

  const types = useMemo(() => {
    if (!docs) return [];
    return [...new Set(docs.map((d) => d.type))];
  }, [docs]);

  const filtered = useMemo(() => {
    if (!docs) return [];
    return docs.filter((d) => {
      if (typeFilter !== "all" && d.type !== typeFilter) return false;
      if (query && !`${d.id} ${d.title}`.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [docs, query, typeFilter]);

  return (
    <>
      <PageHeader
        eyebrow="Document Corpus"
        title="Every record, unified"
        subtitle="Heterogeneous formats — P&IDs, work orders, OEM manuals, inspections, incidents, emails — ingested into one searchable, cross-linked knowledge base."
      />

      <IngestPanel onDone={load} />

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2 px-3 py-2 rounded-[10px] border flex-1 min-w-[240px]" style={{ borderColor: "var(--line-1)", background: "var(--surface-1)" }}>
          <span style={{ color: "var(--ink-3)" }}>⌕</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title or ID…"
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: "var(--ink-1)" }}
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <FilterChip active={typeFilter === "all"} onClick={() => setTypeFilter("all")}>All</FilterChip>
          {types.map((t) => (
            <FilterChip key={t} active={typeFilter === t} onClick={() => setTypeFilter(t)} color={docTypeMeta(t).color}>
              {docTypeMeta(t).label}
            </FilterChip>
          ))}
        </div>
      </div>

      {!docs ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[92px]" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((d) => (
            <button
              key={d.id}
              onClick={() => navigate(`/documents/${encodeURIComponent(d.id)}`)}
              className="text-left"
            >
              <Card className="p-4 h-full transition-all hover:shadow-[var(--shadow-2)] hover:-translate-y-0.5">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-2)" }}>{d.id}</span>
                  <DocTypeBadge type={d.type} />
                </div>
                <div className="font-semibold text-sm leading-snug mb-2" style={{ color: "var(--ink-1)" }}>{d.title}</div>
                <div className="flex items-center gap-2 flex-wrap text-[11px]" style={{ color: "var(--ink-3)" }}>
                  <span>{d.date}</span>
                  {d.author && <><span>·</span><span>{d.author}</span></>}
                  {d.unit && <><span>·</span><span>{d.unit}</span></>}
                </div>
                <div className="flex gap-1.5 mt-3 flex-wrap">
                  {Object.entries(d.entity_counts).filter(([k]) => ["equipment", "standard", "failure_mode"].includes(k)).map(([k, v]) => (
                    <span key={k} className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ background: "var(--surface-inset)", color: "var(--ink-3)" }}>
                      {v} {k.replace("_", " ")}
                    </span>
                  ))}
                </div>
              </Card>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function FilterChip({ active, onClick, children, color }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all"
      style={{
        borderColor: active ? "transparent" : "var(--line-1)",
        // FIX: Replaced var(--ink-1) with #3b82f6
        background: active ? (color || "#3b82f6") : "var(--surface-1)",
        color: active ? "#fff" : "var(--ink-2)",
      }}
    >
      {children}
    </button>
  );
}
