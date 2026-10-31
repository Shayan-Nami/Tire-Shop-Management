# Tire Shop Frontend

A client-rendered React/TypeScript SPA for the Django REST backend. See the
[root README](../README.md) for installation, backend setup, environment tables,
and guarded demo-data instructions. See the
[API reference](../docs/API_REFERENCE.md) for server contracts and the
[deployment guide](../docs/DEPLOYMENT_GUIDE.md) before exposing the application.

## Toolchain and scripts

[package.json](package.json) requires **Node.js >=22.18.0**; Node 24 LTS is a
suitable choice. The stack is React 19, TypeScript 6, Vite 8, React Router 7,
Tailwind CSS 3, Axios, Lucide, and Recharts. Install with `npm ci` to use the lockfile.

Run these commands from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite development server (configured port 5173, host `0.0.0.0`) |
| `npm run typecheck` | TypeScript project build checks without the Vite bundle |
| `npm run lint` | Oxlint with warnings treated as failures, not ESLint |
| `npm test` | Node's built-in test runner over `tests/*.test.ts` |
| `npm run build` | TypeScript checks followed by Vite output in `dist/` |
| `npm run preview` | Local inspection of a build; not a production server |

The dev server listens on all interfaces; restrict network access when using demo
credentials or sensitive data.

## API configuration

The [environment example](.env.example) and root README describe configuration.
The source of truth is [api/client.ts](src/api/client.ts) and
[vite.config.ts](vite.config.ts):

- `VITE_API_BASE_URL` defaults to `/api/v1` after trimming whitespace and removing
  trailing slashes. It is embedded in the browser bundle at build time; changing
  deployment environment variables after the build does not rewrite it.
- `VITE_API_PROXY_TARGET` defaults to `http://127.0.0.1:8000`. It sets the development
  server's `/api` proxy target; it does not configure production routing.
- Treat all `VITE_*` configuration as public. Never put database passwords, Django
  secrets, or private API credentials there. Restart development tooling or rebuild
  as appropriate after configuration changes.
- With the default relative API URL, production hosting must route `/api/` to
  Django. A separate API origin needs matching backend CORS/CSRF configuration.
- Browser-history routes need an `index.html` fallback on the static host, without
  swallowing API/admin requests. There is no server-side rendering implementation.

## Source map and session behavior

| Path | Responsibility |
| --- | --- |
| [src/App.tsx](src/App.tsx) | Lazy page routes, role guards, role-specific root redirects |
| [src/context/AuthContext.tsx](src/context/AuthContext.tsx) | Session/profile state and rial/toman display preference |
| [src/context/LanguageContext.tsx](src/context/LanguageContext.tsx) | Persian/English state and RTL/LTR document direction |
| `src/api/` | Domain HTTP clients; pagination and token-refresh handling |
| `src/pages/`, `src/components/` | Screens, forms, dialogs, layout, and domain controls |
| `src/types/` | API-facing TypeScript contracts |
| `src/utils/` | Error parsing, request sequencing, session helpers, formatting/i18n |
| `tests/` | Unit, contract, transport, and hook-level regression tests |

Roles are only `MANAGER`, `TECHNICIAN`, and `WAREHOUSE`. The server enforces actual
permissions; frontend guards merely shape navigation. For example, technicians
create sales and see their own invoices, while treasury and reports are manager
routes. Frontend navigation is not an exhaustive specification of API access.

Login uses `/auth/login/`, relative to the API base. The app stores `access_token`,
`refresh_token`, and `user_info` in `localStorage` and fetches a fresh profile on
session initialization. The Axios interceptor adds bearer tokens, queues concurrent
401 failures behind one refresh, persists the rotated refresh token, and replays
each failed request at most once. Failed refresh clears local session storage and
redirects to login. Logout attempts server-side refresh-token blacklisting and
clears the local session even if that request fails.

**Token threat:** same-origin malicious JavaScript can read `localStorage`,
including both tokens. They are not HttpOnly-cookie sessions. Server logout does
not immediately revoke an issued access token; password changes invalidate
password-bound tokens. Do not expose the known-password demo accounts without
rotation/removal; disabling demo seeding does not disable existing accounts.

Backend monetary values are IRR. The rial/toman preference changes display, not
the API's canonical currency. Preserve contract types and field-specific errors;
analytics numbers and model decimal strings are not interchangeable assumptions.

## Validation and known boundaries

Run `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build` before a
release. The current audit reported **106 passing frontend tests**, successful
typecheck/lint/build, and a clean npm audit for the resolved dependencies tested.
See the [audit snapshot](../docs/DEPLOYMENT_GUIDE.md) for backend results and limits;
these are not promises about future dependency resolution or deployment readiness.

Tests cover API contracts/pagination, refresh queues and logout retries, financial
submission guards, error parsing, password changes, language/plate formatting,
selector races, and invoice/catalog behavior. Tests use native Node TypeScript
support and the installed TypeScript compiler for TSX in a small
[component harness](tests/componentHarness.ts), without requiring a backend.

The harness runs handlers/effects with controlled promises. It is **not** a browser
renderer or SSR test and does not verify layout, native focus/dialog behavior, or
React concurrent scheduling. No browser end-to-end or live external-database
verification was established by the audit. Manually test keyboard focus/return,
Escape, responsive layouts, deep links, and real authenticated workflows.

Array-returning selectors exhaust paginated results (requests use batches of 100,
not a 100-record total limit). Superseded operations are sequence-invalidated to
avoid stale UI updates. Closing a quick-create dialog cannot roll back a write
already sent to the server: customer/vehicle records may persist even if later
steps are cancelled or the response is lost. Check saved records before retrying
an interrupted or network-ambiguous creation.
