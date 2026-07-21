import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, beforeEach } from "vitest";
import Alerts from "./Alerts.jsx";
import { mockFetch } from "../test/mockFetch.js";
import { FakeEventSource } from "../test/setup.js";

const EMPTY_ALERTS = { alerts: [], active: 0, acknowledged: 0, by_team: {}, teams: [] };

function renderAlerts() {
  return render(
    <MemoryRouter>
      <Alerts />
    </MemoryRouter>
  );
}

describe("Alerts page", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    mockFetch({
      "/api/health": { alert_webhook_configured: false },
      "/api/alerts": EMPTY_ALERTS,
    });
  });

  it("renders without throwing — regression test for the shipped `load` ReferenceError", async () => {
    // Alerts.jsx previously referenced an undefined `load` identifier in
    // its header's Refresh button. Because JSX attribute expressions are
    // evaluated during render, that threw on the component's very first
    // render, before any data even loaded — Testing Library's render()
    // re-throws exactly that kind of error, which is what makes this a
    // real regression test rather than a placeholder.
    renderAlerts();
    expect(await screen.findByText("Action queue")).toBeInTheDocument();
  });

  it("the Refresh button calls a real handler and re-fetches alerts without throwing", async () => {
    const fetchMock = mockFetch({
      "/api/health": { alert_webhook_configured: false },
      "/api/alerts": EMPTY_ALERTS,
    });
    renderAlerts();
    await screen.findByText("Action queue");

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      const alertsCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/alerts"));
      expect(alertsCalls.length).toBeGreaterThan(0);
    });
  });

  it("shows an honest empty state when there are no alerts", async () => {
    renderAlerts();
    await screen.findByText("Action queue");
    // Alerts.jsx's data comes from the live SSE subscription
    // (api.streamAlerts), not a one-shot fetch — push a frame the same
    // way the real backend would over /api/stream/alerts.
    act(() => { FakeEventSource.instances[0].emit(EMPTY_ALERTS); });
    expect(await screen.findByText(/no alerts for this team/i)).toBeInTheDocument();
  });

  it("shows 'Webhook not configured' when the backend reports it unconfigured", async () => {
    renderAlerts();
    expect(await screen.findByText(/webhook not configured/i)).toBeInTheDocument();
  });
});
