# Tire Shop Frontend

React and TypeScript workspace for the Tire Shop Management System: a Persian-first, RTL interface for sales, tire inventory, customers, workshop services, purchasing and treasury records.

This is a client-rendered SPA backed by the [Django REST API](../README.md). It has no independent database, server rendering, bank integration or offline write queue. See the [API reference](../docs/API_REFERENCE.md), [deployment guide](../docs/DEPLOYMENT_GUIDE.md), [design system](../DESIGN.md) and [release verification](../docs/RELEASE_READINESS.md).

## Requirements

- Node.js **22.18.0 or later**; Node 24 is used in CI.
- npm and the committed `package-lock.json`.
- Python 3.13/3.14 and the running Django backend for interactive use.
- SQLite works for local development. PostgreSQL is tested separately for transactions, constraints and concurrent inventory operations. SQL Server is configurable in the backend but was not exercised in the current verification.

The installed stack is React 19, React Router 7, TypeScript 6, Vite 8, Tailwind CSS 3, Axios and Lucide. Exact resolved versions live in [package-lock.json](package-lock.json). The dashboard brand comparison uses accessible HTML with shared-scale bars and visible amounts.

## Quick start

### 1. Prepare the backend

From the repository root, follow the full [backend setup](../README.md#backend-installation). For a fresh local setup:

```bash
cd backend
python -m venv venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source venv/bin/activate
```

Install and configure:

```bash
python -m pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env`, then configure it for your own local database. Minimal local-only values:

```dotenv
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=replace-with-a-random-local-development-key
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=sqlite
USE_SQL_SERVER=False
```

For PostgreSQL, use `DB_ENGINE=postgres` and your private `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` and `DB_PORT` values **only in the backend environment**. Do not commit that file.

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Use Django admin to set the new account's application role to `MANAGER`. Django superuser status alone does not change frontend navigation. There is no built-in login account on a fresh database. The optional demo seeder and its guards are documented in the root README; do not seed an existing shop database to obtain login credentials.

### 2. Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm ci
```

Copy `.env.example` to `.env` if you need explicit configuration. Defaults work with the backend above:

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

```bash
npm run dev -- --host 127.0.0.1 --strictPort
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Sign in using your own account. The command above restricts the development server to loopback and fails if port 5173 is occupied. Plain `npm run dev` uses the configured `0.0.0.0` bind address and may choose another port if 5173 is busy.

## Commands

Run from `frontend/`:

- `npm ci`: install exactly the lockfile; stop the Vite server first on Windows if a native module is locked.
- `npm run dev`: start Vite, normally on port 5173.
- `npm run typecheck`: check the application and Vite TypeScript projects without producing a bundle.
- `npm run lint`: run Oxlint and fail on warnings.
- `npm test`: run the Node test suite, including contract-checker validation.
- `npm run build`: run TypeScript checks and produce `dist/`.
- `npm run preview -- --host 127.0.0.1`: inspect a production build locally; this is not a production web server.
- `npm audit --audit-level=high`: check the resolved dependency tree against npm's current advisory database.

Use `npm install` only when intentionally changing dependencies; commit both `package.json` and `package-lock.json` together.

## Environment and API routing

`VITE_API_BASE_URL` defaults to `/api/v1`. The HTTP client trims whitespace and removes trailing slashes. All domain paths, such as `/auth/login/`, are relative to that base.

`VITE_API_PROXY_TARGET` defaults to `http://127.0.0.1:8000`. It selects the Vite development proxy destination for `/api`; it does not configure a production reverse proxy. This also allows `/api/health/` to reach Django during development.

All `VITE_*` values are public browser configuration. They are embedded at build time. Never put database passwords, Django secrets, tokens or private service credentials in them. Restart the dev server after editing `.env`; rebuild before deploying changed configuration.

The preferred deployment is one origin: static frontend at `/`, Django at `/api/` and `/admin/`. For a separate API origin, configure its absolute base URL at build time, plus the matching backend allowed hosts, CORS and any session/CSRF settings. JWT API requests use the Authorization header; Django admin uses its own session flow.

## Pages and application roles

The exact route guards are in [App.tsx](src/App.tsx):

- `/login`: public sign-in.
- `/dashboard`, `/reports`, `/treasury`, `/users`: manager.
- `/invoices/create`: manager and technician.
- `/invoices/purchases`, `/suppliers`, `/catalog/movements`: manager and warehouse.
- `/services`: manager and technician.
- `/invoices/sales`, `/catalog/tires`, `/customers`: authenticated users; individual actions and server responses remain role-dependent.

The root route sends managers to the dashboard, technicians to invoice creation and warehouse users to the tire catalog. Unknown routes redirect through the root route. Frontend guards shape navigation; backend permissions are authoritative and may constrain individual records as well as actions.

## Architecture and conventions

```text
src/
  App.tsx                   Lazy routes, providers and role guards
  api/                      Domain HTTP clients and pagination
  components/layout/        Navbar, sidebar and scrolling workspace
  components/ui/            Shared UI primitives, including native dialog wrapper
  components/auth/          Profile and password forms
  components/catalog/       Inventory adjustment form
  components/finance/       Receipt and voucher forms
  components/invoices/      Invoice details and returns
  context/                  Authentication, currency and language state
  pages/                    Operational screens
  types/index.ts            Frontend API contracts
  utils/                    Errors, currency/date/plate formatting, request sequencing
  index.css                 Shared tokens, responsive styles and print rules
tests/                      Unit, transport, component and contract checks
```

Reuse the domain API modules instead of making requests inside new UI components. Preserve the backend's error envelope using `parseApiError`. Selectors that return arrays load all backend pages in batches of 100; 100 is not a total-record limit. Ordinary operational tables remain paginated.

Add interface copy to `src/utils/englishMessages.ts` (Persian source key → English value) and use `useLanguage().t` in components. Keep interpolation values separate from translated strings and pass the active language explicitly to currency/date/error formatters. Do not translate saved customer data or API enum values sent to the server.

Use the existing request-sequence helper when overlapping requests can complete out of order. The catalog already protects newer searches from older responses. Do not treat a network failure as a valid zero balance or empty report: dashboard and report screens show a retryable error state.

Visual changes should follow [DESIGN.md](../DESIGN.md): charcoal/amber tokens, Persian-capable typography, readable amounts, contained table scrolling and matching light/dark behavior. Responsive tables scroll horizontally inside their own containers on mobile. Native dialogs are available, but some older forms still use overlays; keyboard and assistive-technology checks remain necessary when editing those forms.

## Authentication and local preferences

Login uses `/auth/login/`. The app stores `access_token`, `refresh_token` and `user_info` in localStorage and validates the saved identity through `/auth/profile/` during initialization.

The Axios client attaches the bearer token, queues simultaneous 401 responses behind one refresh, saves rotated tokens and retries each failed request at most once. An unsuccessful refresh clears the local session. Logout attempts server-side refresh-token blacklisting and clears local state even if the request fails. A successful password change ends the local session and requires sign-in again.

Same-origin JavaScript can read localStorage tokens; they are not HttpOnly cookies. Protect the site from injected scripts and serve production traffic over HTTPS. Logging out blacklists the refresh token but does not immediately revoke every issued access token. Password-bound token invalidation is enforced by the backend.

Preferences are local: `theme`, `language` and `preferred_currency`. Persian/RTL and English/LTR interface copy covers pages, dialogs, invoice print layouts, status labels and common client errors. English amounts use Latin digits and English dates use the Gregorian calendar; Persian dates remain Jalali. Shop-entered names/notes and unknown custom server validation messages retain their original language.

## Money, dates and document integrity

- Canonical amounts sent to and stored by the backend are **IRR (rial)**. Selecting toman changes display; it does not change the API currency. A form explicitly labeled rial still expects rial.
- Model decimal amounts may be JSON strings; analytics amounts can be numbers. Keep the field-specific TypeScript contracts and server-side monetary validation.
- Use shared currency formatting rather than raw numbers in the UI. The server owns document totals, discounts, payment status and stock updates.
- Jalali dates are used for display. Follow the API's documented accepted date formats for filters; do not assume every date input accepts arbitrary Persian text.
- Confirmed sales affect stock; drafts do not reserve it. Receipt/payment/refund vouchers record transactions and do not execute banking operations.
- A lost response does not prove a write failed. Submission guards do not provide server-side idempotency. Check whether an invoice/customer/voucher was saved before retrying an ambiguous request.

## Tests and frontend/backend compatibility

Standard frontend checks:

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

Tests cover refresh queues, session handling, API pagination and contracts, invoice submission guards, plates, error parsing, request races, chart amounts and recovery from failed reports. [componentHarness.ts](tests/componentHarness.ts) executes handlers and effects with controlled promises. It is not a browser renderer and does not simulate layout, native dialog focus or React concurrent scheduling.

A separate cross-stack check creates synthetic records in Django's disposable test database, creates a paid sales invoice, obtains **14 real API responses**, and checks them against the actual frontend TypeScript interfaces using [checkBackendContracts.mjs](tests/checkBackendContracts.mjs). It covers profile, inventory, customers/vehicles, services/suppliers, invoices/receipts and all report responses.

Install frontend dependencies and backend development requirements first, then run from `backend/`:

```bash
python -m pytest apps/accounts/tests/test_frontend_contracts.py --ds=config.verification_settings
```

For PostgreSQL, configure a dedicated development/test database and run:

```bash
python -m pytest --ds=config.settings
```

Django creates a separate test database; the database user needs permission to create it. Test fixtures clear the configured cache, so use a disposable cache, never a production cache. If Node or the frontend TypeScript dependency is missing, the cross-stack test skips explicitly. CI installs both runtimes and executes it on PostgreSQL and SQLite.

For all isolated SQLite checks:

```bash
python -m pytest --ds=config.verification_settings
```

See the [verification record](../docs/RELEASE_READINESS.md) for current test and contract verification results, browser testing limitations, and remaining deployment checks. Passing contract tests does not prove every browser workflow or every possible response shape.

## Production build and hosting

1. Configure the public API base for the intended deployment.
2. Run `npm ci`, tests, lint and `npm run build`.
3. Serve `dist/` through your static host or reverse proxy with HTTPS.
4. Route `/api/` to Django and `/admin/` to Django admin.
5. Apply an `index.html` fallback only to frontend history routes, such as `/catalog/tires`. Do not return HTML for a failed API or asset request.
6. Test direct deep links, sign-in, refresh, permissions, printing and real API errors against the deployed backend.

No deploy step is included in CI. The repository's [workflow](../.github/workflows/ci.yml) checks frontend builds and tests plus backend migrations, lint, scoped typing and database tests. Its PostgreSQL service and credentials are disposable CI resources and must not be copied into production.

## Troubleshooting

- **Port 5173 is busy:** stop the earlier server, or choose another port deliberately. The `--strictPort` quick-start command avoids silently using a different address.
- **Windows EPERM during npm ci:** stop Vite and other processes using this project's native build modules, then rerun `npm ci`. Do not delete the lockfile to solve a file lock.
- **Proxy ECONNREFUSED / 502:** ensure Django is listening on port 8000 and the proxy target matches it. Check `/api/health/` through the frontend origin.
- **API returns HTML / JSON parse error:** the static host is probably sending `index.html` for `/api/`, or the API base is wrong.
- **Sign-in works but a route is forbidden:** check the account's application role and backend permissions. Superuser status alone is not a frontend role.
- **401 after password change:** sign in again; invalidating the session is expected.
- **429:** wait for the backend throttle interval. Do not disable rate limits to hide a client request loop.
- **Empty or failed reports:** use the displayed retry action and inspect the API response. Do not infer zero revenue from a failed request.
- **Deep-link 404:** configure the frontend history fallback on the host.
- **Unexpected rial/toman value:** check the saved display preference and the form's explicit unit; API amounts remain rial.
- **Stock count and movement ledger differ:** run the backend's read-only `reconcile_stock` command and investigate source records. Do not overwrite stock or invent missing movements just to make an alert disappear.

## Contributing and publishing

Keep changes scoped, add a regression test for behavior changes and update contracts on both sides when an endpoint changes. Commit source, migrations, tests, documentation and lockfiles. Do not commit `.env`, database files, local browser sessions, generated build output, logs or real customer data. Use [RELEASE_READINESS.md](../docs/RELEASE_READINESS.md) before release.

This workspace is private for npm publishing (`private: true`). The repository uses the [MIT license](../LICENSE).
