import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Copilot from "./Copilot.jsx";
import { mockFetch } from "../test/mockFetch.js";

function renderCopilot() {
  mockFetch({ "/api/stats": { llm_mode: false } });
  return render(
    <MemoryRouter>
      <Copilot />
    </MemoryRouter>
  );
}

describe("Copilot page", () => {
  it("renders the question input and suggestions", async () => {
    renderCopilot();
    expect(screen.getByPlaceholderText(/why does p-101a keep failing/i)).toBeInTheDocument();
    expect(await screen.findByText("Extractive mode")).toBeInTheDocument();
    expect(screen.getByText(/which relief valves are overdue/i)).toBeInTheDocument();
  });

  it("the Filters toggle opens the metadata filter bar", async () => {
    renderCopilot();
    await screen.findByText("Extractive mode");
    expect(screen.queryByText("Document type")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /filters/i }));
    expect(screen.getByText("Document type")).toBeInTheDocument();
    expect(screen.getByText("Work Order")).toBeInTheDocument();
  });

  it("selecting a doc-type filter shows an active-filter count on the toggle", async () => {
    renderCopilot();
    await screen.findByText("Extractive mode");
    fireEvent.click(screen.getByRole("button", { name: /filters/i }));
    fireEvent.click(screen.getByRole("button", { name: "Work Order" }));
    expect(screen.getByRole("button", { name: /filters \(1\)/i })).toBeInTheDocument();
  });
});
