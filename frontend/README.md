# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## Frontend validation and Phase 5 regression coverage

Use Node.js 24 LTS (or Node.js 22.18+ with native TypeScript stripping):

```sh
npm run lint
npm run build
npm test
```

- Lint runs **Oxlint**, not ESLint, fails on warnings, and excludes `dist/` and `dist-audit/`.
- Existing intentional network-loading/form-reset effects have documented, line-scoped
  Oxlint exceptions. Rules remain enabled globally; no auth lifecycle redesign is included.
- Tests use Node's built-in test runner and native TypeScript support. The existing
  TypeScript dependency compiles TSX in a small hook-level harness; no new dependencies
  or backend services are required.
- Coverage includes immediate customer/vehicle clearing, out-of-order responses and
  failures, stale submit rejection, quick-create cancellation/retry/single-flight behavior,
  all-page selector loading beyond 100 records, sales-list races, draft wording, and
  plate parsing/rendering without invented values.
- The harness executes component handlers and effects with controlled API promises.
  It is not a browser renderer and does not verify native dialog focus, layout, or
  React's concurrent scheduling. Manually check keyboard focus/return and Escape in
  the quick-create dialog when testing the UI in a browser.

Selector requests use a batch size of 100 but fetch **every page**. Superseded
operations are sequence-invalidated, including errors and finalizers, so their responses
cannot restore stale selections. Quick-create writes already sent to the server may
still persist after closing the dialog; closing prevents further steps and stale UI
updates, not server-side rollback. Check saved customer/vehicle records before retrying
an interrupted or network-ambiguous creation.

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
