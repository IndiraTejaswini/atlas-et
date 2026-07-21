import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Agent from "./Agent.jsx";
import { mockFetch } from "../test/mockFetch.js";

function renderAgent() {
  return render(
    <MemoryRouter>
      <Agent />
    </MemoryRouter>
  );
}

async function askQuestion(text) {
  fireEvent.change(screen.getByPlaceholderText(/prioritise this week/i), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: /^ask$/i }));
}

describe("Planning Agent page", () => {
  it("renders the empty state with suggested questions", () => {
    renderAgent();
    expect(screen.getByText("Ask the planning agent")).toBeInTheDocument();
    expect(screen.getByText(/what should rotating equipment prioritise/i)).toBeInTheDocument();
  });

  it("shows the honest 'Agent unavailable' state on a 503, not a crash or a silent failure", async () => {
    mockFetch({ "/api/agent/ask": { status: 503, body: { detail: "Agent unavailable" } } });
    renderAgent();
    await askQuestion("What should Rotating Equipment prioritise?");
    expect(await screen.findByText("Agent unavailable")).toBeInTheDocument();
    expect(screen.getByText(/GROQ_API_KEY/)).toBeInTheDocument();
  });

  it("renders the plan trace and answer on a successful multi-tool run", async () => {
    mockFetch({
      "/api/agent/ask": {
        answer: "P-101A needs attention first — worst health score and an open compliance gap.",
        trace: [
          { tool: "get_asset_health", args: {}, result_preview: '[{"tag":"P-101A","health":48}]' },
          { tool: "get_compliance_gaps", args: {}, result_preview: '{"score":23,"findings":[]}' },
        ],
        iterations: 2,
        truncated: false,
      },
    });
    renderAgent();
    await askQuestion("What should Rotating Equipment prioritise?");

    expect(await screen.findByText(/P-101A needs attention first/)).toBeInTheDocument();
    expect(screen.getByText("get_asset_health()")).toBeInTheDocument();
    expect(screen.getByText("get_compliance_gaps()")).toBeInTheDocument();
    expect(screen.getByText(/2 tool calls/)).toBeInTheDocument();
  });

  it("shows a generic error card on an unexpected failure (not 503)", async () => {
    mockFetch({ "/api/agent/ask": { status: 500, body: { detail: "boom" } } });
    renderAgent();
    await askQuestion("Anything");
    await waitFor(() => {
      expect(screen.getByText(/could not reach the agent service/i)).toBeInTheDocument();
    });
  });
});
