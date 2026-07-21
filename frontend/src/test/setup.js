import "@testing-library/jest-dom/vitest";

// jsdom has no EventSource implementation — every page that subscribes to
// a live stream (Alerts, Assets' Live Conditions tab, Copilot's askStream)
// calls `new EventSource(...)` on mount, which would otherwise throw
// immediately and fail every test that renders those pages, regardless of
// whether the component itself has a real bug.
export class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.onmessage = null;
    this.onerror = null;
    FakeEventSource.instances.push(this);
  }
  emit(data) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  close() {}
}
FakeEventSource.instances = [];

globalThis.EventSource = FakeEventSource;
