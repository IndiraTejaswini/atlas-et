import { vi } from "vitest";

/**
 * Installs a global fetch mock that resolves based on the first matching
 * URL substring in `routes` (checked in insertion order), and 404s
 * anything unlisted — loudly, in the test output, rather than hanging.
 * Each page test supplies only the endpoints it actually needs; this
 * keeps each test's fixture data next to the test it belongs to instead
 * of one giant shared mock every test secretly depends on.
 */
export function mockFetch(routes) {
  const entries = Object.entries(routes);
  const fn = vi.fn((url, init) => {
    const entry = entries.find(([path]) => String(url).includes(path));
    if (!entry) {
      return Promise.resolve({
        ok: false, status: 404, statusText: "Not Found",
        json: () => Promise.resolve({ detail: `no mock route for ${url}` }),
      });
    }
    const value = typeof entry[1] === "function" ? entry[1](url, init) : entry[1];
    if (value?.status) {
      return Promise.resolve({
        ok: value.status >= 200 && value.status < 300,
        status: value.status,
        json: () => Promise.resolve(value.body ?? {}),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(value) });
  });
  globalThis.fetch = fn;
  return fn;
}
