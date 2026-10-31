# Codebase Health and Publication Audit

**Date:** October 31, 2026  
**Scope:** Django backend, React/Vite frontend, API contracts, dependency advisories, repository hygiene, and public documentation.  
**Result:** Verified blockers were fixed and the checked local suites pass. This is not a penetration-test report, security certification, or production-readiness guarantee.

## Executive summary

- Prevented invoice-total overflow from committing invalid financial/stock records and breaking subsequent API reads.
- Fixed SQLite decimal-division truncation affecting discount-aware reporting on Django 5.2.
- Added the missing Redis client and made SQL Server authentication/TLS controls explicit with secure defaults.
- Fixed incomplete paginated selectors, duplicate financial submissions, and refresh/logout handling in the frontend.
- Aligned TypeScript contracts and UI error parsing with backend serializers and exception envelopes.
- Patched frontend dependencies and raised vulnerable Python dependency minimums; the audited resolved sets have no known advisories.
- Removed generated/local artifacts, strengthened ignore rules, archived historical material, and replaced inaccurate/template documentation.

## Phase 1 — Health, quality, and contract audit

### Verified defects and remediation

| Finding | Evidence / impact | Remediation | Main files |
| --- | --- | --- | --- |
| Invoice total exceeds storage capacity | Valid individual prices multiplied by quantities could exceed `DecimalField(14,2)`. A reproduced purchase returned 500 after committing invoice/stock, and later list serialization also failed. | Validate computed totals within the existing atomic transaction. Invalid totals return 400 and roll back documents, stock, movement history, and numbering. Regression tests cover sales, purchases, boundaries, discounts, and rollback. | `backend/apps/invoices/services.py`, `backend/apps/invoices/tests/test_invoice_total_bounds.py` |
| Incorrect discount reporting on Django 5.2 / SQLite | NUMERIC casts could still perform integer division; percentage discounts were ignored and full returns could leave phantom revenue. | Added SQLite-specific real-number division while preserving decimal SQL arithmetic on other backends. Added fractional-allocation, revenue/profit, and full-return regressions. | `backend/utils/expressions.py`, `backend/apps/reports/views.py`, `backend/apps/reports/tests/test_brand_discount_audit.py` |
| Redis cache dependency missing | Configuring `REDIS_CACHE_URL` reproduced `ModuleNotFoundError: redis`. | Declare Redis client dependency and test backend initialization/reads with the connection mocked. | `backend/requirements.txt`, `backend/config/test_dependencies.py` |
| SQL Server authentication/TLS ambiguity | Configuration combined SQL credentials with unconditional trusted authentication and certificate-validation bypass. | Select integrated/SQL authentication deliberately. Default to encryption and certificate verification; validate new Boolean controls. Tests inspect configuration and connection strings without native connections. | `backend/config/settings.py`, `backend/config/test_database_settings.py` |
| Paginated data silently truncated | Users, brands, sizes, and low-stock helpers discarded records after the first backend page. | Reuse complete-pagination helper, retaining array-response compatibility. | `frontend/src/api/pagination.ts`, `frontend/src/api/auth.ts`, `frontend/src/api/catalog.ts` |
| Repeated financial/stock mutations | Purchase, receipt, and return handlers could submit again while a request was pending. | Synchronous in-flight guards with regression coverage. These are browser guards, not backend idempotency guarantees. | `frontend/src/pages/PurchaseInvoices.tsx`, receipt/return modal components |
| JWT retry/rotation mismatch | Queued 401 requests could retry more than once; logout retries could submit the already blacklisted pre-rotation refresh token. | Mark all retries once and use the current refresh token for logout. Test real Axios interceptors with mocked transport. | `frontend/src/api/client.ts`, `frontend/tests/apiClient.test.ts` |
| API type/error-envelope drift | Several nullable fields and purchase/report shapes differed from serializers; creation types allowed unsupported states or omitted required reasons. Forms sometimes expected unwrapped errors. | Correct request/read contracts, add compile-time contract tests, and reuse `parseApiError` in affected forms. | `frontend/src/types/index.ts`, API modules, form handlers, contract/error tests |
| Hardcoded API configuration | API base and development proxy destination were not configurable. | Add `VITE_API_BASE_URL` and `VITE_API_PROXY_TARGET`, retain same-origin/local defaults, and document public build-time behavior. | `frontend/src/api/client.ts`, `frontend/vite.config.ts`, `frontend/src/vite-env.d.ts` |

No new schema/data migration was needed for these fixes. No API route was renamed.

### Dependency review

- The initial frontend audit reported **4 affected packages: 3 high and 1 moderate**; one high-severity affected dependency was present in the production dependency tree.
- `npm audit fix --ignore-scripts` updated dependencies within existing manifest ranges. Final `npm audit`, production-only audit, and the final `npm ci` audit reported **0 vulnerabilities**.
- Backend clean Windows and Linux resolutions were audited with **pip-audit 2.10.1** against public package/version metadata. No repository source was uploaded. The audited sets contained **49 packages each, 0 known vulnerabilities, and 0 skipped packages**.
- Minimum-version probes found vulnerable releases still permitted by broad Python requirements. Lower bounds were raised to Django **5.2.17**, DRF **3.18.2**, SimpleJWT **5.5.1**, pytest **9.0.3**, and python-dotenv **1.2.2**. The Django upper bound remains `<6.2`.
- Compatibility checks passed for the resolved environments. Linux packages were resolved/audited, not executed on Linux.
- The frontend lockfile is committed; Python requirements are not a full hash-pinned lockfile. A clean resolution today does not guarantee future versions or artifact integrity. Native libraries, OS packages, Python itself, and ODBC driver security were not comprehensively assessed.

### Configuration and API review

- Eight Django domain apps are installed; Django system checks found no configuration/model-reference errors.
- SQLite, PostgreSQL, and SQL Server selection branches exist on one `default` connection; there is no multi-database router. Unknown `DB_ENGINE` values fall back to SQLite.
- JWT and session authentication are enabled; authenticated API access is the default. Roles are exactly `MANAGER`, `TECHNICIAN`, and `WAREHOUSE`, with action-level permissions and technician sales-queryset restrictions.
- CORS uses explicit origins, not wildcard access. Production hosts/origins, proxy trust, HTTPS/cookies/HSTS, and a shared throttle cache require operator configuration.
- Frontend domain prefixes match backend routing: `auth`, `crm`, `catalog`, `workshop`, `procurement`, `invoices`, `treasury`, and `analytics`.
- No URL/method mismatch was found in the inspected API clients. Payload/response and pagination problems were corrected as described above.
- API documentation is public in debug mode and manager/superuser-protected outside debug unless `ENABLE_DOCS_IN_PROD` explicitly makes it public.
- The known debug-only Django secret is rejected outside debug mode. Demo seed credentials are predictable, guarded by two opt-ins, and must never be promoted unchanged to an exposed database.

### Validation record

Backend validation used **Python 3.14.6**, clean virtual environments, isolated SQLite databases, and disposable copies for migration checks. The original local database was not migrated or modified; its hash remained unchanged during backend validation.

| Check | Result |
| --- | --- |
| Python syntax compilation | 173 backend Python files passed after fixes |
| Dependency installation and compatibility | Clean requirements/dev installations and pip/uv compatibility checks passed |
| Baseline backend suite | 314 passed; 9 skipped |
| Final suite, Django 5.2.17 | **342 passed; 9 skipped** |
| Final suite, Django 6.1.2 | **342 passed; 9 skipped** |
| Targeted final reporting/config suite | 43 passed on each Django version |
| Django `check` | Passed on both tested versions |
| `makemigrations --check --dry-run` | No model/migration drift on either version |
| Fresh `migrate`, migration-state/constraint checks | Passed on both versions |
| Upgrade of a disposable local-database copy | Six pending migrations applied successfully; schema/constraint/integrity checks passed |
| `spectacular --validate --fail-on-warn` | Passed on both tested versions |
| Frontend baseline suite | 55 passed |
| Final frontend suite | **106 passed; 0 failed/skipped** |
| `npm ci` | Passed; final lockfile reinstall audited 173 packages |
| `npm run typecheck` and forced `tsc -b` | Passed |
| `npm run lint` | 0 warnings/errors; 64 files checked |
| `npm run build` | Passed with Vite 8.3.5; 2,562 modules transformed |
| `npm audit` and production-only audit | 0 known vulnerabilities |
| `npm ls --depth=0` | No missing/invalid direct dependencies reported |
| Documentation links and anchors | 104 local links/anchors across 8 public Markdown files passed |
| Ignore rules and publication candidates | 22 cases passed; no unwanted artifacts or files over 100 MiB found |
| `git diff --check` | Passed; Git emitted only line-ending conversion notices |

The final frontend reinstall/test/typecheck/lint/build/audit sequence was rerun from the lockfile after documentation reconciliation and starter-asset removal. Backend suites were run through isolated wrappers to avoid connecting to the original SQLite database. Standard contributor commands and environment setup are documented in the [root README](../README.md).

### Deployment checks and limits

- Default `check --deploy` reported **W004, W008, W012, W016** for HSTS, HTTPS redirect, and secure cookies. Turning on those controls still leaves explicit subdomain/preload policy choices. Local-development defaults were not blindly hardened in ways that would break local HTTP.
- Nine skipped tests require PostgreSQL row-lock/concurrency behavior. **Live PostgreSQL, SQL Server, Redis, and browser end-to-end workflows were not verified.**
- SQL Server settings/connection strings were tested without connecting. Native ODBC Driver 17/18 was not installed in the audit environment.
- No paid/cloud penetration scan or source upload occurred. This was code inspection, dependency advisory review, and automated local tests—not exhaustive exploit testing.
- **Editor diagnostics are not clean.** The language servers report Django ORM/decorator/descriptor typing errors and Python lint warnings across existing and changed files, plus unresolved Vite/Node imports in the editor. The clean installed CLI TypeScript build and automated suites pass. The editor import/type-analysis configuration was not repaired, and these diagnostics were not suppressed; CLI success should not be presented as a passing Python static typecheck.

## Phase 2 — Repository cleanup and publication hygiene

### Completed

- Expanded root/backend/frontend `.gitignore` coverage for Python caches, environments, databases/sidecars, logs, media/static output, Node dependencies, build outputs, environment files, coverage, OS files, and editor settings including `.zed/`.
- Preserved negation rules allowing dummy `.env.example` templates to be tracked.
- Added `frontend/.env.example` with public API/proxy defaults and an explicit no-secrets warning.
- Removed local `.zed/`, scratch, pytest/Python cache directories, backend logs, frontend build/audit-build output, and unused React/Vite starter SVGs. Test/build commands recreate generated files; final cleanup removes them again.
- Moved tracked coursework/design documents to `docs/archive/phase-1-and-2/` and standalone SQL experiments to `docs/archive/phase-3/`. Content was preserved, not deleted.
- Moved locally excluded agent-coordination notes into `docs/archive/`; these remain locally excluded and are not current public documentation.
- Preserved the local SQLite database and installed Node dependencies; both are ignored rather than destructively removed.
- Verified the current index contains no local database, active environment file, logs, cache bytecode, dependency directory, or build output in the checked patterns.
- Checked available history for the specific `.env` and SQLite paths examined; none appeared. This was not an exhaustive all-history secret scan.

### Explicit limitations

1. **Backend template privacy:** `backend/.env.example` exists and is tracked, but Zed's `private_files` setting blocked reading it. It was neither bypassed nor overwritten. Its contents/dummy-only status could not be verified. Review it manually against the root README before publishing.
2. **Historical binaries:** archived PDF/DOCX/image material was preserved but not exhaustively inspected for embedded metadata or personal information. Review before public release.
3. **History:** no history rewrite was performed. Current ignore rules cannot remove a secret already present in historical commits; rotate/rewrite if a broader secret scan finds one.

## Phase 3 — Documentation

Replaced the root [README](../README.md) with an English guide covering badges, mission/features, architecture diagram, stack, app/data model, JWT/session/RBAC, endpoint table, SPA routing/state, setup for both operating-system families, configuration tables, tests, production considerations, repository structure, contribution guidance, and MIT licensing.

Reconciled these related documents with current source:

- [API reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)
- [Database design](DATABASE_DESIGN.md)
- [Deployment and operations](DEPLOYMENT_GUIDE.md)
- [Frontend guide](../frontend/README.md)
- [Historical archive](archive/README.md)

Removed unsupported claims about an accountant role, double-entry accounting, Redis as a task broker, non-existent authentication routes, and bundled production infrastructure. Audit results are presented as dated observations rather than badges claiming live CI coverage.

## Remaining release actions

1. **Apply existing migrations to the local database before using it with current code.** Six are pending in the preserved local database: catalog 0008–0009, finance 0006, and invoices 0013–0015. Back up first; the upgrade passed only on a disposable copy during the audit.
2. **Configure and validate deployment security.** Replace secrets/origins, rotate or delete demo accounts, verify SQL Server certificate/authentication settings if used, and resolve deployment-check warnings for the actual topology.
3. **Run PostgreSQL concurrency tests and real-browser workflows.** SQLite tests do not establish row-lock safety, native dialog/focus behavior, responsive rendering, or deployed token/proxy behavior.
4. **Review publication-sensitive material.** Manually review the privacy-blocked backend template and historical binary documents; consider a dedicated all-history secret scan before the first public push.
5. **Track nonblocking design/maintenance gaps.** Frontend guards do not fully model backend superuser overrides and sometimes restrict navigation more than API read permissions. Strict TypeScript mode is not enabled. `PAGINATION_PAGE_SIZE` is shadowed by the pagination class's fixed default of 20; request-level `page_size` works. Browser submission guards do not provide cross-client/server idempotency.

No commits or branches were created. The working tree contains the changes for review.
