import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ui.jsx";

function Bomb() {
  throw new Error("boom from a broken page");
}

describe("ErrorBoundary", () => {
  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <div>hello world</div>
      </ErrorBoundary>
    );
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("catches a render error and shows the fallback instead of crashing the tree", () => {
    // React logs the caught error to console.error by design; silence it
    // for this test's expected-error case so the test output isn't noisy.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText("This page hit an error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload page/i })).toBeInTheDocument();
    spy.mockRestore();
  });

  it("surfaces the actual error message in the fallback for debugging", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText(/boom from a broken page/)).toBeInTheDocument();
    spy.mockRestore();
  });
});
