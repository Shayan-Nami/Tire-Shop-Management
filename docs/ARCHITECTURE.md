# Architecture

The application is a Django REST backend and a browser-rendered React single-page
application for tire catalog, stock, customers, invoices, and payment records.
See the [root README](../README.md) for setup and configuration,
[API reference](API_REFERENCE.md) for routes, and
[database design](DATABASE_DESIGN.md) for persistence.

## Runtime and request flow

```text
Browser SPA (React + TypeScript)
  -> Axios /api/v1 requests with JWT bearer tokens
  -> Django REST Framework views and permissions
  -> Serializers and domain services
  -> Django ORM / configured relational database
```

During development, Vite proxies `/api` to Django. In production, a reverse proxy,
HTTPS termination, static file hosting, process supervision, and shared cache are
configured by the operator.

- [Backend requirements](../backend/requirements.txt) allow Django `>=5.2.17,<6.2`
  with DRF, SimpleJWT, django-filter, drf-spectacular, and the PostgreSQL driver;
  SQL Server drivers live in `requirements-mssql.txt`, test tooling in
  `requirements-dev.txt`, and exact versions in the matching `requirements*.lock` files.
- [Frontend package metadata](../frontend/package.json) specifies React 19,
  TypeScript 6, Vite 8, Tailwind CSS 3, Axios, React Router and Lucide.
  Node.js must be at least 22.18.0.
- [Settings](../backend/config/settings.py) select SQLite by default, PostgreSQL,
  or SQL Server. WSGI and ASGI entrypoints exist; the selected deployment server
  and database still need environment-specific verification.
- Default caching is process-local `LocMemCache`. `REDIS_CACHE_URL` selects
  Django's Redis cache, including shared throttle counters.

## Eight backend apps

All eight are registered in `INSTALLED_APPS` and mounted in
[config/urls.py](../backend/config/urls.py).

| App under `backend/apps/` | API prefix under `/api/v1/` | Responsibility |
| --- | --- | --- |
| `accounts` | `auth/` | Custom users, roles, login/refresh/logout, profiles, passwords |
| `customers` | `crm/` | Customers and their vehicles |
| `catalog` | `catalog/` | Brands, sizes, tires, stock movements and projection recovery |
| `services_app` | `workshop/` | Service catalog and tariffs |
| `suppliers` | `procurement/` | Supplier records |
| `invoices` | `invoices/` | Sales, purchases, sales returns, document numbering |
| `finance` | `treasury/` | Receipts, supplier payments, customer refunds and cancellations |
| `reports` | `analytics/` | Read-only operational aggregations; no separate business tables |

Views handle HTTP methods, permissions, querysets, filtering, and response shapes.
Serializers validate input and control representation. Multi-record operations
live mainly in `services.py` in accounts, catalog, invoices, and finance; ordinary
master-data CRUD also uses serializer/model persistence directly.

## Transaction and stock boundaries

[Catalog services](../backend/apps/catalog/services.py) write signed stock
movements and update `Tire.stock_quantity` together inside atomic transactions.
Each movement records the resulting balance, cost snapshot, actor, and applicable
document references. The public stock-movement API is read-only.

[Invoice services](../backend/apps/invoices/services.py) coordinate:

- **Sales:** confirmed sales reduce stock; drafts do not reserve or consume it.
  Draft confirmation refreshes tire cost snapshots at stock-out time. Positive
  paid sales create receipt vouchers in the same transaction.
- **Purchases:** increase stock and set the latest purchase price. The service
  retains the prior price for cancellation recovery.
- **Cancellations:** reverse the relevant stock effect and preserve document
  records. Existing returns/payments and stock/history constraints can prevent
  cancellation.
- **Returns:** validate remaining sold quantities, allocate original discounts,
  restore stock, and update payment status. The return API also requests an
  automatic refund voucher when there is refundable excess.
- **Numbering:** locks a counter keyed by document type and Jalali year, producing
  `S-1405-00001` / `P-1405-00001`-style identifiers, with unique invoice numbers.

The services use `transaction.atomic()` and `select_for_update()`, and tire locks
are acquired in primary-key order in stock workflows to keep lock ordering
consistent across concurrent requests. Because SQLite does not implement
row-level locks, run the concurrency test suite on PostgreSQL or SQL Server when
validating multi-worker deployments; see the [deployment guide](DEPLOYMENT_GUIDE.md).

## Financial records and treasury

[Finance services](../backend/apps/finance/services.py) lock invoices when issuing
vouchers, enforce positive amounts and debt/refund ceilings, and synchronize
payment status from non-cancelled vouchers. Sales balances subtract refunds from
receipts and returns from invoice value. Cancellation records actor, time, and
reason instead of exposing direct voucher editing/deletion through the API.

Profitability reports use tire cost snapshots together with invoice discounts and
returns. Vouchers record shop receipts, supplier payments, and customer refunds.

## Access and session boundaries

The only roles in [the user model](../backend/apps/accounts/models.py) are
`MANAGER`, `TECHNICIAN`, and `WAREHOUSE`. This is a shop-wide role model, not
multi-tenant isolation. Manager checks generally also accept superusers.

- Technicians can create sales and see only their own sales invoices. They cannot
  access purchase invoices, stock-movement endpoints, treasury, or analytics.
- Warehouse users maintain catalog/purchases and can read sales invoices. They
  can see catalog purchase prices and purchase line costs; sales-line and
  stock-movement cost snapshots are hidden from them.
- Managers administer users, treasury, reports, returns, and invoice cancellation.
  Authenticated users can read/create/update customers and vehicles; only managers
  can delete them. The [API reference](API_REFERENCE.md) details endpoint differences.

SimpleJWT access tokens are password-bound (`CHECK_REVOKE_TOKEN`); the custom
refresh serializer also checks the live user/password binding. Refresh rotation
and password-change revocation use database-backed blacklist records. Logout
blacklists a refresh token, not every outstanding access token. Session
authentication remains available, including Django admin and CSRF requirements.

Default API throttles are 30/minute anonymous and 300/minute authenticated;
login uses 5/minute per IP and username, and refresh 15/minute. These are
configurable cache-backed throttles, not a substitute for edge abuse controls.
Proxy trust and a shared cache require deliberate deployment configuration.

## Frontend boundaries

[App.tsx](../frontend/src/App.tsx) defines lazy-loaded browser routes and role
checks. [AuthContext](../frontend/src/context/AuthContext.tsx) stores the session
and refreshes the profile on startup.
[LanguageContext](../frontend/src/context/LanguageContext.tsx) switches Persian /
English and document direction. Currency preference affects rial/toman display;
backend amounts remain IRR.

The [Axios client](../frontend/src/api/client.ts) adds access tokens, queues
concurrent 401 failures behind one refresh, stores rotated tokens, and retries a
request once. `VITE_API_BASE_URL` defaults to `/api/v1`; it is public build-time
configuration. Access/refresh tokens and user information are in `localStorage`,
so malicious same-origin JavaScript can read them. Frontend guards and cached
roles are not authorization controls; server checks remain authoritative.

See the [frontend guide](../frontend/README.md) for scripts and test boundaries,
and the [deployment guide](DEPLOYMENT_GUIDE.md) for hardening and verification.
