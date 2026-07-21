"""Auto-generated compliance evidence package.

Produces a self-contained, printable HTML audit document: the compliance
posture, every requirement evaluated, its status computed from the source
records, and — for each finding — the actual evidence documents with their
relevant excerpts. An auditor can open it, read it, and print it to PDF.
"""
from __future__ import annotations

import html
from datetime import datetime

SEV = {"critical": "#d03b3b", "high": "#eb6834", "medium": "#c98500", "low": "#94a3b8"}
STATUS = {
    "gap": ("GAP", "#d03b3b", "#fbe9e9"),
    "no_evidence": ("NO EVIDENCE", "#475569", "#eef1f5"),
    "due_soon": ("DUE SOON", "#c98500", "#fdf3e0"),
    "compliant": ("COMPLIANT", "#0ca30c", "#e7f6e7"),
}


def _excerpt(doc, max_chars=320):
    body = " ".join(doc.body.split())
    return html.escape(body[:max_chars]) + ("…" if len(body) > max_chars else "")


def build_evidence_pack(compliance: dict, docs: list) -> str:
    by_id = {d.id: d for d in docs}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = compliance["counts"]

    rows = []
    for i, f in enumerate(compliance["findings"], 1):
        label, color, wash = STATUS.get(f["status"], STATUS["no_evidence"])
        ev_blocks = []
        for did in f["evidence"]:
            doc = by_id.get(did)
            if not doc:
                continue
            ev_blocks.append(f"""
              <div class="ev">
                <div class="ev-h"><span class="mono">{html.escape(doc.id)}</span>
                  <span class="ev-t">{html.escape(doc.title)}</span>
                  <span class="ev-d">{html.escape(doc.date)}</span></div>
                <div class="ev-x">{_excerpt(doc)}</div>
              </div>""")
        equip = "".join(f'<span class="chip">{html.escape(e)}</span>' for e in f.get("equipment", []))
        rows.append(f"""
          <section class="finding">
            <div class="f-top">
              <div class="f-num">{i:02d}</div>
              <div class="f-main">
                <div class="f-title">{html.escape(f['title'])}
                  <span class="sev" style="background:{SEV.get(f['severity'],'#94a3b8')}"></span>
                  <span class="sev-l">{f['severity']}</span></div>
                <div class="f-std">{html.escape(f['standard'])}</div>
                <div class="f-detail">{html.escape(f['detail'])}</div>
                {f'<div class="chips">{equip}</div>' if equip else ''}
              </div>
              <div class="f-status" style="color:{color};background:{wash}">{label}</div>
            </div>
            {'<div class="ev-wrap"><div class="ev-cap">Evidence records</div>' + ''.join(ev_blocks) + '</div>' if ev_blocks else ''}
          </section>""")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>ATLAS Compliance Evidence Pack — {now}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #0f172a;
         max-width: 900px; margin: 0 auto; padding: 40px 32px; background: #fff; }}
  .brand {{ display:flex; align-items:center; gap:12px; margin-bottom:4px; }}
  .logo {{ width:38px;height:38px;border-radius:9px;background:linear-gradient(135deg,#2a78d6,#1c5cab);
          color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px;}}
  h1 {{ font-size: 22px; margin: 0; }}
  .sub {{ color:#64748b; font-size:13px; }}
  .meta {{ display:flex; gap:24px; margin:20px 0 8px; font-size:13px; color:#475569;
           border-top:1px solid #e6e9ee; border-bottom:1px solid #e6e9ee; padding:14px 0; }}
  .meta b {{ color:#0f172a; }}
  .summary {{ display:flex; gap:10px; margin:18px 0 28px; }}
  .card {{ flex:1; text-align:center; padding:14px; border-radius:12px; }}
  .card .n {{ font-size:26px; font-weight:700; }}
  .card .l {{ font-size:12px; color:#475569; margin-top:2px; }}
  .finding {{ border:1px solid #e6e9ee; border-radius:14px; padding:18px; margin-bottom:14px;
              break-inside: avoid; }}
  .f-top {{ display:flex; gap:14px; align-items:flex-start; }}
  .f-num {{ font-variant-numeric:tabular-nums; font-weight:700; color:#94a3b8; font-size:14px; padding-top:2px; }}
  .f-main {{ flex:1; }}
  .f-title {{ font-weight:700; font-size:15px; display:flex; align-items:center; gap:8px; }}
  .sev {{ width:9px;height:9px;border-radius:50%;display:inline-block; }}
  .sev-l {{ font-size:11px;color:#94a3b8;text-transform:uppercase;font-weight:600;letter-spacing:.04em; }}
  .f-std {{ font-size:12px; color:#2a78d6; font-weight:600; margin-top:3px; }}
  .f-detail {{ font-size:13.5px; color:#475569; margin-top:6px; line-height:1.5; }}
  .f-status {{ font-size:11px; font-weight:700; padding:5px 10px; border-radius:20px; white-space:nowrap;
               letter-spacing:.03em; }}
  .chips {{ margin-top:8px; display:flex; gap:5px; flex-wrap:wrap; }}
  .chip {{ font-family:ui-monospace,monospace; font-size:11px; background:#f2f4f7; color:#475569;
           padding:2px 7px; border-radius:5px; }}
  .ev-wrap {{ margin-top:14px; padding-top:14px; border-top:1px dashed #e6e9ee; }}
  .ev-cap {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
             color:#94a3b8; margin-bottom:8px; }}
  .ev {{ background:#f8fafc; border-radius:9px; padding:11px 13px; margin-bottom:8px; }}
  .ev-h {{ display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }}
  .mono {{ font-family:ui-monospace,monospace; font-weight:700; font-size:12px; background:#eef2f7;
           padding:1px 6px; border-radius:4px; }}
  .ev-t {{ font-weight:600; font-size:13px; }}
  .ev-d {{ color:#94a3b8; font-size:12px; margin-left:auto; font-variant-numeric:tabular-nums; }}
  .ev-x {{ font-size:12.5px; color:#475569; margin-top:6px; line-height:1.55; }}
  .foot {{ margin-top:28px; padding-top:16px; border-top:1px solid #e6e9ee; font-size:11px; color:#94a3b8; }}
  @media print {{ body {{ padding:0; }} .finding {{ break-inside: avoid; }} }}
</style></head><body>
  <div class="brand"><div class="logo">A</div>
    <div><h1>Compliance Evidence Package</h1>
    <div class="sub">ATLAS — Industrial Knowledge Intelligence · Refinery Unit 300 (Crude Distillation)</div></div>
  </div>
  <div class="meta">
    <div>Generated <b>{now}</b></div>
    <div>Compliance score <b>{compliance['score']}%</b></div>
    <div>Requirements evaluated <b>{compliance['total_checks']}</b></div>
    <div>As of <b>{compliance['as_of']}</b></div>
  </div>
  <div class="summary">
    <div class="card" style="background:#fbe9e9"><div class="n" style="color:#d03b3b">{c['gap']}</div><div class="l">Gaps</div></div>
    <div class="card" style="background:#eef1f5"><div class="n" style="color:#475569">{c['no_evidence']}</div><div class="l">No evidence</div></div>
    <div class="card" style="background:#fdf3e0"><div class="n" style="color:#c98500">{c['due_soon']}</div><div class="l">Due soon</div></div>
    <div class="card" style="background:#e7f6e7"><div class="n" style="color:#0ca30c">{c['compliant']}</div><div class="l">Compliant</div></div>
  </div>
  {''.join(rows)}
  <div class="foot">This package was auto-generated by ATLAS from the plant document corpus. Every status is
  computed from dates and records found in the cited source documents. Excerpts are drawn verbatim from those
  documents. Print to PDF for audit submission.</div>
</body></html>"""
