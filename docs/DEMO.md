# ATLAS — Demo Script & Video Shot List

A tight **4-minute** demo that lands the "connect the dots no one team can" story. Rehearse once; every beat below maps to a screen you already have.

---

## Before you start
- Backend running on `:8100`, frontend on the Vite URL.
- (Optional) `ANTHROPIC_API_KEY` set so the Copilot shows "Claude synthesis on" — but the demo works identically without it.
- Have a small `.md` file ready to drag-drop for the live-ingest beat (see the appendix for one).

---

## The narrative spine
A single real failure chain is hidden across six document types. The demo *discovers* it live:

> In January 2024 the plant switched to a waxy crude. An engineer flagged the risk in an email; the change never went through Management of Change. Over 2024 the P-101A pump seal failed **twice**, causing a near-miss vapor release. The same wax pattern was later found forming on the standby pump. A retiring engineer's handover note explains the whole thing — but it lives in a file nobody reads. **ATLAS connects all of it in one query.**

---

## Beat-by-beat (4 min)

### 0:00 — Overview (15s)
Land on the **Overview** page. One sentence:
> "Every drawing, work order, procedure, inspection and incident in this unit — 18 documents, 57 knowledge-graph nodes, one brain. Notice the compliance score is 23% and two assets are at risk. Let's find out why."

### 0:15 — The hero query (60s)
Go to **Knowledge Copilot**. Type: **"Why does P-101A keep failing?"**
- Point at the **citations** — "every claim links to a real document."
- Point at the **confidence score**.
- Expand the **retrieval trace**: *"Look — it matched the equipment tag `P-101A`, then surfaced `OEM-SLZ-OHH` and `MEMO-HND-01` **through the graph, via the shared failure mode.** Those documents don't contain the word 'failing.' A keyword search would never find them. That's the retiring engineer's handover note and the OEM manual — exactly the knowledge that walks out the door when someone retires."

### 1:15 — Follow the chain (45s)
Click the citation to **WO-2415** (repeat seal failure). From there click the linked **INC-451** near-miss, then **EML-0124** (the crude-slate email).
> "Six document types, one causal chain — a feedstock change that skipped Management of Change and caused two seal failures and a near-miss. No single team saw this whole picture."

### 2:00 — The graph (30s)
Open **Knowledge Graph**. Click the `P-101A` node.
> "This is the connective tissue. One click shows every document, standard, person and failure mode touching this pump. Filter to just failure modes and documents to see the failure cluster."

### 2:30 — Maintenance intelligence (45s)
Open **Maintenance Intelligence**. `P-101A` is at the top, health 48.
> "It fused the work-order history, inspections and incidents into a failure timeline and MTBF. And here's the AI recommendation — it detected the **recurring** seal failure, root-caused it to the crude-slate change, and cites the exact documents. It even flags that the same wax pattern is forming on the standby pump — a warning *before* the next failure."

### 3:00 — Lessons Learned & Failure Intelligence (30s)
Open **Lessons Learned**.
> "This is the systemic view — it analyses every incident at once. It found that wax blockage isn't a P-101A problem, it's a **fleet-wide pattern** across three assets over five years, and it matched that to a known industry failure signature. And here are the **proactive warnings** — it's telling us the standby pump shows the early pattern *before* it fails, and that feedstock changes keep bypassing Management of Change. That's the knowledge no single review would assemble."

### 3:30 — Compliance + evidence pack (20s)
Open **Compliance**.
> "It maps OISD, Factories Act and PESO against the actual documents — PSV-1104 is 399 days overdue, computed from the register, not hardcoded." Click **Generate evidence pack**.
> "One click produces a printable, auditor-ready evidence package — every requirement, its status, and the verbatim source excerpts."

### 3:50 — Live multi-format ingest (10s)
Go to **Documents**, drag-drop a **PDF** (or CSV).
> "A real PDF inspection report arrives. Text extracted, entities parsed, graph re-linked, every engine updated in under 50 milliseconds — no re-training. The knowledge base is alive."

**Close:**
> "Fragmented documents became connected, explainable, actionable intelligence — and it runs CPU-only, offline, inside the plant's security boundary."

---

## Extended-capability beats (add ~60s if time allows, or keep as backup)

These deepen three of the five areas — pull them in if the audience is technical or asks "what else":

- **Live operating conditions** (Maintenance Intelligence → *Live Conditions* tab): real-time sensor gauges streaming every 3 s. P-101A vibration sits just past its 7.1 mm/s alarm and seal-flush flow below limit — the failure story, live. *"This is the real-time feed the maintenance engine fuses with the document history."*
- **Optimised PM schedule** (*PM Schedule* tab): a risk-ranked maintenance calendar — statutory-overdue first, then predictive intervals derived from each asset's own MTBF. *"Not a flat time-based PM list — it works the highest-risk, soonest-due task first."*
- **Alerts / push-to-teams** (*Alerts* page): every warning, live breach, quality deviation and compliance gap routed to the responsible team — Rotating Equipment, Inspection & Integrity, Process Safety — with one-click acknowledge. *"This is how intelligence becomes action: the right team is notified before it escalates."* Click **Acknowledge** on one to show it clear. If a webhook is configured, point at the **"Webhook delivery on"** badge and hit **Send test** — *"this isn't just an in-app queue, it actually leaves the building."*
- **Quality deviations** (Compliance → *Quality Deviations* tab): E-104 preheat outlet below design, min-flow excursions — flagged with expected-vs-observed before they escalate.
- **OCR ingest**: drop a **scanned image / photo of a form** on Documents — the text is OCR'd, entities extracted, graph updated. *"Even paper the plant scanned becomes queryable knowledge."*
- **Planning Agent** (*Planning Agent* page, needs `ANTHROPIC_API_KEY`): ask *"What should Rotating Equipment prioritise this week?"* and open the **plan trace** — *"watch it decide for itself to check asset health, then compliance gaps, before it answers. That's not the Copilot's fixed retrieve-then-generate pipeline — Claude is choosing which tools to call."*

---

## Video shot list (for the recorded submission)

| # | Shot | Duration | On-screen focus |
|---|---|---|---|
| 1 | Overview KPIs | 8s | the four stat cards + downtime chart |
| 2 | Copilot typing the hero query | 10s | answer streaming in with citation chips |
| 3 | Zoom on retrieval trace | 8s | "surfaced via graph" line highlighted |
| 4 | Click-through WO-2415 → INC-451 → EML-0124 | 12s | linked-document chips |
| 5 | Graph, click P-101A, filter | 12s | node highlight + connection panel |
| 6 | Maintenance P-101A detail | 12s | recommendation card + timeline |
| 7 | Compliance table | 8s | overdue PSV row + evidence links |
| 8 | Drag-drop ingest | 8s | green success toast with entity chips |
| 9 | Architecture diagram (from ARCHITECTURE.md) | 6s | the flow diagram |

Record at 1080p; keep the cursor movements slow and deliberate; let each citation/trace sit on screen for a full second.

---

## Appendix — a file to drag-drop live

Save as `insp-110.md`:
```markdown
---
id: INSP-110
title: INSP-110 P-101B Flush Line Wax Inspection
type: inspection
date: 2026-02-15
author: S. Iyer
unit: Unit 300
equipment: P-101B
failure_mode: wax blockage
status: open
---

# Inspection INSP-110 — P-101B Plan 32 Flush Line

Follow-up to WO-2688. Borescope of the standby pump P-101B flush line
found early wax film formation identical to the P-101A history (WO-2415).
Cleaned as precaution. Recommend monthly strainer cleaning per OISD practice.
Refer OEM manual OEM-SLZ-OHH for flush requirements.
```
After ingesting, re-run **"Why does P-101A keep failing?"** — the new report now participates in the answer.
