# Deployment and Operations

Use the [root README](../README.md) for local setup, dependency installation, and
environment-variable tables. This guide covers release checks and operational
risks; it is not evidence of a deployed or production-ready installation.
The [GitHub Actions workflow](../.github/workflows/ci.yml) validates source changes;
it does not deploy them. WSGI/ASGI entrypoints and the Vite build still need an
operator-provided runtime, reverse proxy and hosting.

## Runtime and topology

- Backend dependencies allow Django `>=5.2.17,<6.2`. The latest full verification used
  Python **3.14.6** with Django **6.1.1**; earlier audits also tested Django 5.2.17
  and 6.1.2. These are tested snapshots,
  not a claim about every Python/Django combination.
- [frontend/package.json](../frontend/package.json) requires **Node.js >=22.18.0**
  (Node 24 LTS is a suitable choice). Node 20 is not the documented baseline.
- SQLite is the default; the test suite also runs against PostgreSQL. SQL Server
  has settings/driver support but has not been exercised in this verification. It also
  requires a compatible native ODBC driver and trusted server certificate.
- Redis is optional caching for shared throttle state, enabled by `REDIS_CACHE_URL`.
  Without it, cache/throttle state is process-local. There is no task broker.

A possible deployment is HTTPS static hosting for `frontend/dist/`, with `/api/`
and `/admin/` forwarded to a supervised Django application server and Django
`/static/` assets served from `backend/staticfiles/`. This is an operator-provided
topology, not a bundled deployment. Gunicorn is included only on non-Windows
platforms; choose and verify a platform-appropriate server for
`config.wsgi:application` or `config.asgi:application`. Do not use Django's dev
server or Vite's dev/preview server as the production service.

React uses browser-history routing. Static hosting must return `index.html` for
frontend routes, while preserving real `/api/`, `/admin/`, and static-file responses.

## Configuration checks before exposure

Configuration is read in [settings.py](../backend/config/settings.py), including
`backend/.env` if present. Keep environment files/secrets out of version control
and restrict their filesystem access. Use the root README's configuration tables
rather than copying an unverified production template.

1. Set `DJANGO_DEBUG=False`, a unique random `DJANGO_SECRET_KEY`, and explicit
   production `ALLOWED_HOSTS`. Settings reject a missing secret or the known
   fallback secret outside debug mode; that guard does not validate overall readiness.
2. Replace development CORS/CSRF origin defaults with the actual trusted origins.
   Review admin/session access, cookie security, HTTPS redirect, and HSTS settings.
   Enable HSTS only after confirming HTTPS and the intended subdomain policy.
3. Trust `X-Forwarded-Proto` only when a trusted proxy controls it. Set
   `SECURE_PROXY_SSL_HEADER` and `NUM_PROXIES` to match the real proxy chain;
   prevent clients from reaching the backend with forged forwarded headers.
4. Verify the intended database was selected, credentials have least privilege,
   TLS works, migrations apply, and backups can be restored. An unrecognized
   `DB_ENGINE` falls back to SQLite; do not mistake that for a working external DB.
5. For SQL Server, `DB_TRUSTED_CONNECTION` defaults to true **only when trimmed
   `DB_USER` is empty**; otherwise it defaults to false. An explicit true value
   uses integrated authentication and omits SQL username/password. Defaults are
   `DB_ENCRYPT=yes` and `DB_TRUST_SERVER_CERTIFICATE=no`. These three controls
   accept trimmed, case-insensitive `true/false`, `yes/no`, or `1/0`; invalid values
   fail configuration in the SQL Server branch. Do not disable encryption or
   certificate validation merely to hide connection failures. The default driver
   name is `ODBC Driver 17 for SQL Server`; install/configure the actual driver.
6. With multiple workers/instances, provision and test a shared cache if throttle
   counters must be shared. The dependency test mocks Redis reads; it does not
   prove live Redis availability. Add edge-level abuse controls as needed.
7. Keep `ALLOW_DEMO_SEED=False` and the public `ENABLE_DOCS_IN_PROD` override off.
   Schema/Swagger/Redoc are public in debug mode or with that override, otherwise
   manager/superuser-only. Restrict administration and monitor authentication failures.

### Demo accounts and browser tokens

The [demo seed command](../backend/apps/catalog/management/commands/seed_tire_shop.py)
requires both debug mode (`DJANGO_DEBUG=True`) and `ALLOW_DEMO_SEED=True`. It creates known-password
accounts only when absent: `admin` / `admin123`, `technician` / `tech123`, and
`warehouse` / `warehouse123`. Existing passwords are left unchanged. Use this
only with disposable local data. Rotate all seeded passwords or remove the demo
accounts before any exposure; disabling the seed flag does not remove accounts.

The browser stores JWT access/refresh tokens in `localStorage`, not HttpOnly
cookies. Same-origin malicious JavaScript can steal them. Treat XSS prevention,
third-party script review, and appropriate host security headers as deployment
concerns; HTTPS alone does not address that threat. Logout blacklists the refresh
token but does not revoke an existing access token. Password changes revoke
password-bound tokens; verify that workflow and force credential rotation when needed.

## Release checklist

After configuring the target environment and taking a recoverable backup, run
from `backend/` using its virtual environment:

```sh
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
```

Investigate deployment-check warnings rather than assuming defaults are hardened.
Create a non-demo administrator with `python manage.py createsuperuser` when
needed, and verify its application role as well as Django admin access.

From `frontend/`, use `npm ci`, run the validation scripts in the
[frontend guide](../frontend/README.md), then `npm run build` and deploy `dist/`.
`VITE_API_BASE_URL` defaults to `/api/v1` and is public **build-time** configuration;
rebuild after changing it. All `VITE_*` values must be treated as public, never
secrets. `VITE_API_PROXY_TARGET` defaults to `http://127.0.0.1:8000` and configures
the Vite development `/api` proxy, not a production reverse proxy. For a separate
API origin, configure CORS/CSRF deliberately and test the deployed URL.

Before serving users, smoke-test login, refresh rotation, password change,
role restrictions, sales/drafts/confirmation, purchases, returns, voucher
cancellation, and reconciliation on the intended database. Exercise concurrent
stock/payment updates there; passing SQLite tests does not establish row-lock safety.
Verify frontend deep links, API failures, and admin/static routing in a real browser.

## Monitoring and recovery

- `/api/health/` is public and returns 200/503 based on opening a database
  connection. It does not check migrations, Redis, frontend assets, or business integrity.
- Logging writes to the console and `backend/logs/backend_errors.log` and
  `backend/logs/security.log`. Provision write permissions, rotation, retention,
  access restrictions, and alerts; a file handler is not an installed monitoring service.
- Back up the configured database and protect secrets. Schedule backups and test
  restoration using database-specific tooling; no automated backup service is implied.
- From `backend/`, `python manage.py reconcile_stock` and
  `python manage.py reconcile_payments` report discrepancies and fail when found.
  Payment reconciliation is read-only. Investigate before changing financial data.
- Stock repair is explicitly opt-in: `reconcile_stock --repair` requires `--user`
  naming an active manager and `--reason`; optional repeatable `--tire-id` limits
  the repair. It rebuilds the stock projection from verified movement history and
  writes a repair audit record. It does not repair corrupted movement history.
  Physical `adjust-stock` creates a real movement and is not projection recovery.
- Rehearse rollback with migration compatibility and data recovery in mind;
  reverting frontend/backend files alone cannot undo database changes.

## Verification and limits

The latest [release verification](RELEASE_READINESS.md), dated **2026-11-03**,
records 519 passing PostgreSQL tests (1 SQLite-only skip), 511 passing SQLite tests
(9 database-specific skips), and 125 passing frontend tests. Lint, build, OpenAPI,
system checks and migration-drift checks passed. Older results remain in the
[historical audit](AUDIT_REPORT.md).

These results are a point-in-time record, not a security certification or a
guarantee for future dependency resolution. Earlier browser inspections are
recorded separately from this automated rerun; there is no automated browser
end-to-end suite. Native ODBC connectivity, production database load behavior,
live Redis, infrastructure, backup restoration and deployed behavior still need
environment-specific validation. Investigate the existing stock/ledger discrepancy
described in the release record before trusting the local shop database.
