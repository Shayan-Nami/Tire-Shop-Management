# Release verification — November 3, 2026

## Publication status

Source and documentation have been validated locally. GitHub-hosted CI and deployment results are not yet available.

Publishing source code and deploying the existing shop database are separate decisions. The current local database has four stock-versus-ledger discrepancies. Treat that as a blocker for trusting inventory history or using that database operationally until investigated. The verification did not rewrite stock, ledger entries, invoices or payment records.

## Completed checks

- Runtime: Python 3.14.6, Django 6.1.1, Node 24.19.0; PostgreSQL server reports 18.6.
- Full configured PostgreSQL suite: **519 passed, 1 skipped** out of 520 collected tests. The skip is the SQLite-specific writer-contention regression.
- Full isolated SQLite suite: **511 passed, 9 skipped** out of 520 collected tests. The skipped checks require row-lock/database behavior SQLite does not provide.
- Both full suites include `test_frontend_contracts.py`, checking 14 real API responses against frontend contracts; it passed on both engines.
- Frontend: **125 passed, 0 skipped**, with lint and production build successful. The build includes TypeScript checks.
- npm audit reported **0 known vulnerabilities** across the installed dependency tree. A fresh `npm ci` succeeded in the November 2 preparation; installation was not repeated in this rerun.
- Python `pip check`, Ruff and the project's scoped strict mypy check passed. Mypy currently covers `utils/domain.py`, not the entire backend.
- OpenAPI validation with `--validate --fail-on-warn` passed under isolated SQLite and configured PostgreSQL settings. The tracked `backend/schema.yml` matches the generated PostgreSQL schema structurally. SQLite reports different integer bounds, so its generated schema is not a portable byte-for-byte comparison target.
- Django system checks passed; no model/migration drift, no pending PostgreSQL migrations, and fresh migrations applied successfully to a disposable in-memory SQLite database.
- Read-only payment reconciliation found no differences between invoice payment statuses and valid vouchers.
- Read-only stock reconciliation still reports **4 discrepancies** in the existing local database. No repair or business-data mutation was performed.
- Local Markdown link targets, environment-template defaults, Git exclusion rules and `git diff --check` passed. No publishable file exceeds GitHub's 100 MiB file-size limit; all are below 50 MiB.

### Earlier checks retained for context

The November 2 preparation also checked PostgreSQL constraint validation and read-only dashboard/catalog API probes. Twelve authenticated routes were inspected in the browser at desktop and mobile sizes in the preceding UI pass; no page-level mobile overflow was found. Those live API and browser inspections were not repeated on November 3. Their earlier results do not establish a browser end-to-end suite or production readiness.

## Frontend/backend contract integration

The backend regression creates synthetic catalog/customer/vehicle/service/supplier records in the disposable test database and posts a paid invoice through the API. Fourteen real JSON responses are checked against the SPA's actual TypeScript interfaces, including nullable fields, decimal representations, nested structures and pagination.

The checker lives at `frontend/tests/checkBackendContracts.mjs`; its negative regression proves that a response missing required dashboard fields is rejected. It does not replace browser end-to-end testing or validate every possible subtype and workflow. Without Node or frontend TypeScript dependencies, the backend test skips explicitly; CI installs both.

Reproduce from the repository root after installing both projects' dependencies:

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
cd ../backend
python -m pip check
python -m ruff check .
python -m mypy
python manage.py check --settings=config.verification_settings
python manage.py makemigrations --check --dry-run --settings=config.verification_settings
python manage.py spectacular --settings=config.verification_settings --validate --fail-on-warn
python -m pytest --ds=config.verification_settings
```

For PostgreSQL, configure an isolated development/test database and a disposable cache, then run `python -m pytest --ds=config.settings`. Django uses a separate test database. Its account must be allowed to create that database. Tests clear the configured cache, so never point them at a production cache.

## Existing local inventory discrepancy

The read-only command `python manage.py reconcile_stock` exited with an error because four existing tires have more projected stock than their recorded ledger explains. The inspected records have no sufficient opening/inbound history. That explains the mismatch but does not establish the authoritative physical quantities or historical cost.

Do not run a blanket repair: replacing stock with the current ledger would discard unexplained quantities, and one inspected ledger total was negative. Do not invent opening movements to force reconciliation to pass.

Before using this database operationally:

1. Back it up and verify restoration to a separate database.
2. Review opening balances, source invoices, stocktaking records and any manual imports against physical stock.
3. Establish whether the ledger or the current projection is authoritative for each affected tire.
4. Use the existing audited repair service only when the ledger is verified and the manager provides a reason. Missing historical evidence needs an explicit accounting/operational resolution first.
5. Re-run `reconcile_stock` and `reconcile_payments`; retain the investigation evidence outside the public repository.

The public verification record intentionally omits customer details, credentials, affected record identifiers and business amounts.

## GitHub preparation

The [CI workflow](../.github/workflows/ci.yml) runs frontend tests/lint/build/audit, backend lint/scoped typing, OpenAPI validation, migration checks and PostgreSQL/SQLite tests. Action pins were checked against the official repositories' `v7` tags, repository permissions are read-only and checkout credentials are not persisted. The PostgreSQL service uses disposable test-only credentials. No deployment step is included.

Local `.env` files, databases, node_modules, builds, caches, logs, browser sessions, and `.impeccable/` design references are excluded via `.gitignore`. `.gitattributes` normalizes text to LF while preserving CRLF for Windows batch launchers. The backend environment template leaves the signing key empty, disables demo seeding and uses the application's default 60-minute access-token lifetime; supply a random private key before running it.

A focused scan of publishable files and reachable Git blobs found no private-key blocks or common hosted-service access-token patterns. Environment-file history contains only `.env.example` templates. All published files are well within platform size limits.

## Remaining deployment checks

SQL Server, a live shared Redis service, production reverse-proxy/TLS settings, backup restoration, thermal-printer hardware, screen readers, every dialog's keyboard behavior and manual end-to-end flows for all roles still need deployment-specific validation. Existing overlay-based forms are not all native dialogs. Python requirements have version ranges rather than a full hash-pinned lockfile; resolve and audit the production environment separately.

No claim of zero defects or production readiness is made while these gates and the existing stock discrepancy remain open.

## English interface follow-up

The English UI expansion covers all page and dialog copy, client validation, invoice A4/thermal view labels, document statuses, currency labels/digits and Gregorian date display. Persian retains Jalali dates. Layout uses logical spacing and bidi isolation for shop-entered text. The login page now exposes its language switch as well.

The follow-up frontend suite passed **125 tests**, including static translation-key coverage, locale formatting, preserved form input on language changes, English dashboard output and both invoice print views. Lint, TypeScript/build and the cross-stack response contract test also passed. All twelve authenticated routes were inspected in English on desktop and mobile; the mobile checks found no page-level horizontal overflow.

Shop data and unknown custom backend validation details remain in their original language. English UI completion is not automatic translation of customer records or a backend localization change. Physical printing and a manual submission through every dialog were not repeated for this localization pass.

## Repository cleanup — November 4, 2026

Removed superseded coursework and standalone SQL scripts under `docs/archive/`, unused frontend artwork/template icons, the unreferenced `utils/constants.py` module, and unused Recharts/clsx/tailwind-merge dependencies. The dependency lockfile and Vite chunk configuration were updated together. Historical committed files remain recoverable from Git history.

The root README now includes an ERD checked against Django model metadata, showing operational foreign keys and their optionality. The database guide retains physical table mappings and documents supporting audit/numbering models. Database files, environment secrets, migrations and regression tests remain intact.

Post-cleanup checks: all 125 frontend tests, lint and production build passed; backend Ruff, Django system checks and migration-drift checks passed. All 18 diagram entities, selected columns and 24 operational foreign keys were checked against model metadata, including nullable relationships. The final Mermaid diagram was rendered and visually inspected in a local browser. Markdown links, dependency/lockfile alignment and `git diff --check` passed. The complete backend suites were not repeated for this file/dependency cleanup; their preceding results are recorded above.

## Local verification update — November 4, 2026

A focused local re-verification was conducted on the candidate release tree:

- **Frontend:** 125 passed, 0 skipped; Oxlint and Vite production build with TypeScript passed cleanly.
- **Backend isolated SQLite:** 511 passed, 9 database-specific skips (520 total collected); includes cross-stack validation of 14 live API responses against frontend TypeScript contracts.
- **Code hygiene:** Python `pip check`, Ruff, and scoped strict mypy (covering `utils/domain.py`) passed.
- **Django checks:** System checks, migration drift dry-run, and OpenAPI schema generation with `--validate --fail-on-warn` passed.
- **Audit & secrets:** `npm audit` reported 0 known vulnerabilities. Scan of 284 candidate files confirmed no active `.env` files, databases, or local logs; secret pattern scanning of candidate files and 489 reachable blobs detected no credentials.
- **Scope note:** This run did not repeat live PostgreSQL, SQL Server, Redis, physical thermal printing, or browser UI inspection. PostgreSQL results (519 passed, 1 skip) remain documented from the November 3 run and will be verified by CI. The existing local database discrepancies remain unchanged and unedited.
