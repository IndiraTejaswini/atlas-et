# ATLAS — Presentation Deck Outline

12 slides, ~8 minutes. Each slide has a one-line **assertion** (the headline) and the **evidence** to show. Build the deck so the headlines alone tell the story.

---

### Slide 1 — Title
**ATLAS — Industrial Knowledge Intelligence**
"One queryable brain over every document in the plant."
Team name, tagline, the ⚙️ logo. Screenshot: the Overview page as backdrop.

### Slide 2 — The problem (make it hurt)
**35% of working hours lost to finding information. 7–12 disconnected systems per plant. 25% of expert engineers retiring within a decade.**
- 18–22% of unplanned downtime traces to fragmented knowledge (BIS Research).
- Frame it as three compounding problems: *safety, quality, efficiency.*
- Land the knowledge-cliff line: "When they retire, it's gone. It cannot be recovered."

### Slide 3 — The insight
**This is not a file-management problem. It's a relationship problem.**
The answer to "why did this pump fail" lives across an email, two work orders, a near-miss, and a handover note that share no keywords. You can't search your way there — you have to *connect* your way there.

### Slide 4 — What we built
**ATLAS ingests any document, extracts its entities, and links everything into one knowledge graph you can query in plain English — with citations.**
Show the architecture diagram (from ARCHITECTURE.md). Name the six capabilities: Ingestion+Graph, Copilot, Maintenance RCA, Compliance, Failure Intelligence, and a Planning Agent that decides for itself which of these to call.

### Slide 5 — Live demo hook: the hero query
**"Why does P-101A keep failing?" → the answer reaches documents that share no words with the question.**
Screenshot the Copilot answer with the retrieval trace open, "surfaced via graph" highlighted. This is the money slide — the GraphRAG moment.

### Slide 6 — Connect the dots
**Six document types, one causal chain — surfaced automatically.**
A visual of the chain: `EML-0124 (slate change)` → `skipped MOC` → `WO-2301 + WO-2415 (repeat seal failures)` → `INC-451 (near-miss)` → `MEMO-HND-01 (the retiring engineer's explanation)`. "No single team ever saw this whole picture. ATLAS did, in one query."

### Slide 7 — Maintenance intelligence & RCA
**Recurring-failure detection + root cause + a warning before the next failure.**
Screenshot the P-101A asset detail: health score, failure timeline, the recommendation card. Call out the standby-pump early warning.

### Slide 8 — Compliance intelligence
**Every regulatory gap computed from the documents, with evidence attached for the audit pack.**
Screenshot the compliance table: PSV-1104 overdue by 399 days, evidence links. "Nothing hardcoded — change a date in a source file and the gap updates."

### Slide 9 — Continuously updated
**Drop a new document; every engine updates in under 50 ms. No re-training.**
Screenshot the live-ingest success toast. Emphasize: the knowledge base is *alive*, not a one-time index.

### Slide 10 — How it's engineered (for the technical judges)
**Three-signal explainable retrieval + in-memory knowledge graph — CPU-only, offline-capable.**
- **Three retrieval signals, all explainable:** inverted-index BM25 (lexical) + **LSA semantic vectors** (meaning — catches paraphrases with zero keyword overlap) + graph expansion (relational). The retrieval trace shows which signal surfaced each source.
- Rule-based extraction: 100% precise on industrial tag conventions, 0 ms, 0 GPU.
- Runs inside the plant's OT security boundary — where cloud-only tools can't go.
- **Proven at scale (measured, live on the Overview page):** 5,000 docs → ~44 ms median query, 1.3 s build, ~65 MB; linear to 10k on one CPU core; documented ANN/sharding path beyond.
- Point to ARCHITECTURE.md §6.1 for the full complexity/latency/scale table.

### Slide 10b — We measured it (this is your credibility slide)
**81% hit@1 · 88% hit@3 · 98% entity F1 · 100% graph linkage — on a hand-labelled expert gold set.**
Then show the ablation table and say the honest line out loud:
> *"When the engineer already knows the tag, plain BM25 is at ceiling — the graph adds nothing, and we'll say so. Where the graph earns its place is the query described in plain English: **+17 points hit@1**. We know that because we measured it, not because we assumed it."*

Then the harder version of the same slide, if the audience is technical enough to earn it:
> *"Those numbers were measured against the set we used to tune the code — so we built a second set, 18 questions and 11 more document labels, written after the extraction and retrieval code was frozen, and changed nothing to make it score better. Held-out hit@1 comes in at 72%, not 81% — and on that set the semantic and graph signals show no net lift over plain keyword search. We're showing you the number that went down, not just the ones that went up."*
This is the strongest credibility beat in the deck precisely because it's the one number that makes the pitch look worse — say it plainly rather than skip the slide.

### Slide 10c — Agentic AI, demonstrated not claimed
**Claude plans its own path through six live tools — compliance, asset health, ROI, PM schedule, fleet patterns, document search — and shows its work.**
Ask the Planning Agent *"What should Rotating Equipment prioritise this week?"* live and open the plan trace. *"This is different from the Copilot: that page always retrieves then generates, in that order, every time. Here Claude decided for itself to check asset health, then compliance gaps, before answering — and every tool call it made is right there, inspectable, same as the retrieval trace."*

Add the kicker — the evaluation **found two real bugs**: graph expansion was only firing on exact tag matches (fixed → that's where the +17 came from), and most of our apparent entity errors turned out to be *our own gold labels being wrong*. That's engineering maturity, and judges reward it far more than a suspicious 100%.

### Slide 10a — Quantified impact (optional, strengthens Business Impact)
**₹4.2 L + 18 hours of downtime were avoidable — computed from the record, not estimated.**
The 2nd P-101A seal failure replayed a root cause already in the first work order 5 months earlier. ATLAS surfaces the pattern after the first event. Show the ROI banner on the Overview page — every rupee traces to a work order.

### Slide 11 — Why it wins (map to judging criteria)
| Criterion | Weight | ATLAS |
|---|---|---|
| **Innovation** | 25% | GraphRAG that reaches non-keyword documents; explainable retrieval trace |
| **Business Impact** | 25% | Attacks downtime, audit prep, and the knowledge cliff simultaneously |
| **Technical Excellence** | 25% | Hybrid retrieval, knowledge graph, live re-index, offline CPU deployment |
| **Scalability** | 20% | Clean module boundaries; documented path from unit → refinery → multi-site |
| **User Experience** | 15% | Answers in seconds vs. hours; citations + confidence build trust |

### Slide 12 — Close & vision
**The organizations that connect their knowledge first will have a structural advantage in how they operate, maintain, and improve their assets.**
Vision: ATLAS as the plant's institutional memory — capturing what retires, connecting what fragments, warning before what recurs.
Call to action / QR to the demo video.

---

## Speaker notes — the three things to never skip
1. **The retrieval trace.** It's the proof that this isn't a generic chatbot — show that a document was surfaced *through the graph*, not by keyword.
2. **"Every number is computed from the documents."** This kills the "it's all staged" objection instantly.
3. **CPU-only / offline.** Industrial buyers cannot send P&IDs and incident reports to a cloud API. This is a real, disqualifying requirement for competitors — and a checkbox we hit.
