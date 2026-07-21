import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Card, DocTypeBadge, Badge, Skeleton, DocRefLink } from "../components/ui.jsx";

const ENTITY_META = {
  equipment: { label: "Equipment", color: "var(--c6)" },
  standard: { label: "Standards & regulations", color: "var(--c2)" },
  failure_mode: { label: "Failure modes", color: "var(--c8)" },
  person: { label: "Personnel", color: "var(--c7)" },
  parameter: { label: "Process parameters", color: "var(--c1)" },
  docref: { label: "Referenced documents", color: "var(--brand)" },
};

/* lightweight markdown rendering for the body */
function renderBody(body) {
  const lines = body.split("\n");
  const out = [];
  let table = null;
  lines.forEach((line, i) => {
    const t = line.trim();
    if (t.startsWith("|")) {
      const cells = t.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.every((c) => /^-+$/.test(c.replace(/:/g, "")))) return;
      if (!table) table = [];
      table.push(cells);
      return;
    } else if (table) {
      out.push(<TableBlock key={`t${i}`} rows={table} />);
      table = null;
    }
    if (t.startsWith("# ")) out.push(<h2 key={i} className="text-lg font-bold mt-5 mb-2" style={{ color: "var(--ink-1)" }}>{t.slice(2)}</h2>);
    else if (t.startsWith("## ")) out.push(<h3 key={i} className="text-base font-bold mt-4 mb-1.5" style={{ color: "var(--ink-1)" }}>{t.slice(3)}</h3>);
    else if (t.startsWith("- ") || /^\d+\.\s/.test(t))
      out.push(<li key={i} className="ml-5 text-[15px] leading-relaxed list-disc" style={{ color: "var(--ink-2)" }}>{inline(t.replace(/^-\s|^\d+\.\s/, ""))}</li>);
    else if (t) out.push(<p key={i} className="text-[15px] leading-relaxed my-1.5" style={{ color: "var(--ink-2)" }}>{inline(t)}</p>);
  });
  if (table) out.push(<TableBlock key="tend" rows={table} />);
  return out;
}

function inline(text) {
  const parts = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(<strong key={parts.length} style={{ color: "var(--ink-1)" }}>{m[1]}</strong>);
    last = re.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function TableBlock({ rows }) {
  const [head, ...body] = rows;
  return (
    <div className="my-3 overflow-x-auto rounded-[10px] border" style={{ borderColor: "var(--line-1)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: "var(--surface-inset)" }}>
            {head.map((h, i) => <th key={i} className="text-left px-3 py-2 font-semibold" style={{ color: "var(--ink-2)" }}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {body.map((r, i) => (
            <tr key={i} className="border-t" style={{ borderColor: "var(--line-2)" }}>
              {r.map((c, j) => <td key={j} className="px-3 py-2 tnum" style={{ color: "var(--ink-2)" }}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DocumentView() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    setDoc(null);
    api.document(id).then(setDoc).catch(() => setDoc({ error: true }));
  }, [id]);

  if (doc?.error) return <Card className="p-8 text-center" style={{ color: "var(--ink-3)" }}>Document not found.</Card>;

  return (
    <>
      <button onClick={() => navigate(-1)} className="text-sm font-medium mb-4 inline-flex items-center gap-1.5" style={{ color: "var(--ink-3)" }}>
        ← Back
      </button>

      {!doc ? (
        <Skeleton className="h-[400px]" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
          <Card className="p-7">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded" style={{ background: "var(--surface-2)", color: "var(--ink-2)" }}>{doc.id}</span>
              <DocTypeBadge type={doc.type} />
              <span className="text-xs" style={{ color: "var(--ink-3)" }}>{doc.date}{doc.author && ` · ${doc.author}`}</span>
            </div>
            <h1 className="text-xl font-bold mb-4" style={{ color: "var(--ink-1)" }}>{doc.title}</h1>
            <div className="prose-none">{renderBody(doc.body)}</div>
          </Card>

          <div className="space-y-4">
            {doc.linked_docs?.length > 0 && (
              <Card className="p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>Linked documents</h3>
                <div className="flex flex-wrap gap-1.5">
                  {doc.linked_docs.map((d) => <DocRefLink key={d} id={d} />)}
                </div>
              </Card>
            )}

            <Card className="p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--ink-3)" }}>Extracted entities</h3>
              <div className="space-y-4">
                {Object.entries(ENTITY_META).map(([key, meta]) => {
                  const items = doc.entities?.[key];
                  if (!items || Object.keys(items).length === 0) return null;
                  return (
                    <div key={key}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                        <span className="text-xs font-semibold" style={{ color: "var(--ink-2)" }}>{meta.label}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.keys(items).map((name) => (
                          <span key={name} className="text-xs px-2 py-0.5 rounded-md font-medium" style={{ background: "var(--surface-inset)", color: "var(--ink-2)" }}>{name}</span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
