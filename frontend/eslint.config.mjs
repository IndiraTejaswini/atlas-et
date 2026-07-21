// Deliberately minimal: `no-undef` is the specific, targeted fix for a real
// bug this project shipped — Alerts.jsx referenced an undefined `load`
// identifier (copy-pasted from Documents.jsx without its `load` function
// coming along) and nothing caught it, because `vite build` only
// transpiles/bundles, it doesn't do the scope analysis a linter does. No
// framework plugin (eslint-plugin-react etc.) is added here on purpose —
// broader linting (unused-vars, hooks rules) is a reasonable follow-up, but
// this file's job is closing the one gap that's already bitten this repo.
export default [
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: "readonly", document: "readonly", console: "readonly",
        fetch: "readonly", EventSource: "readonly", URLSearchParams: "readonly",
        FormData: "readonly", setTimeout: "readonly", clearTimeout: "readonly",
        localStorage: "readonly", navigator: "readonly", getComputedStyle: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
    },
  },
];
