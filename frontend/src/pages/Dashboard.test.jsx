import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Dashboard from "./Dashboard.jsx";
import { mockFetch } from "../test/mockFetch.js";

const STATS = {
  documents: 18, chunks: 49, graph_nodes: 57, graph_edges: 186,
  entity_mentions: 120, unique_entities: { equipment: 10, standard: 6, failure_mode: 5, person: 6 },
  compliance_score: 23, open_gaps: 6, assets_at_risk: 2, total_downtime_hours: 90, total_cost_inr: 1500000,
  downtime_by_month: [{ month: "2025-01", hours: 20 }], index_build_ms: 95, avg_query_ms: 1.2, llm_mode: false,
};
const ROI = { avoidable_downtime_hours: 18, avoidable_cost_inr: 420000, avoided_incidents: 1, recurrence_count: 2, headline: "test headline", docs: [] };
const COMPLIANCE = { score: 23, counts: { gap: 6, due_soon: 2, no_evidence: 3, compliant: 2 }, total_checks: 13, as_of: "2026-07-20", findings: [] };
const EVAL = {
  validation: { held_out_questions: 18, held_out_labelled_docs: 11 },
  answer_quality: { hit_at_1: 81, questions: 16 },
  answer_quality_held_out: { hit_at_1: 72, questions: 18 },
  entity_extraction: { f1: 98 }, entity_extraction_held_out: { f1: 100 },
  graph_linkage: { completeness_pct: 100 },
  compliance_detection: { evidence_traceability_pct: 100 },
  hybrid_lift: { indirect: { hit_at_1: 17 } }, hybrid_lift_held_out: { indirect: { hit_at_1: 0 } },
};
const BENCH = { n_docs: 5000, query_p50_ms: 44, build_ms: 1300, graph_nodes: 5300, graph_edges: 18200, query_p95_ms: 66, peak_mem_mb: 65 };

function renderDashboard() {
  mockFetch({
    "/api/stats": STATS, "/api/assets": [], "/api/compliance": COMPLIANCE,
    "/api/roi": ROI, "/api/evaluation": EVAL, "/api/benchmark": BENCH,
  });
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("Dashboard page", () => {
  it("renders KPI cards from real fetched stats", async () => {
    renderDashboard();
    expect(await screen.findByText("Plant Knowledge Overview")).toBeInTheDocument();
    // Unique to the "Documents unified" KPI card's subtitle — unlike the
    // bare number "18", which also appears as the ROI banner's unrelated
    // "18h avoidable downtime" figure in this fixture.
    expect(await screen.findByText("49 indexed passages")).toBeInTheDocument();
  });

  it("EvalCard toggles between tuning and held-out figures", async () => {
    renderDashboard();
    expect(await screen.findByText("81%")).toBeInTheDocument(); // tuning hit@1

    fireEvent.click(screen.getByRole("button", { name: "Held-out" }));
    expect(await screen.findByText("72%")).toBeInTheDocument(); // held-out hit@1
    expect(screen.getByText(/held-out, not independently authored/i)).toBeInTheDocument();
  });
});
