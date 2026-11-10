# API Reference

This is a compact guide to the implemented API, not a complete OpenAPI schema.
See the [root README](../README.md) for setup and environment variables.
Routing starts in [config/urls.py](../backend/config/urls.py); each app's
`urls.py`, views, and serializers define the actual contract.

## Conventions

- Base path: `/api/v1/`. Use trailing slashes and JSON request bodies.
- Browser authentication: `Authorization: Bearer <access_token>`. Django session
  authentication is also enabled; session-authenticated writes require CSRF protection.
- Most business endpoints require authentication. Permissions and queryset filtering
  are enforced on the server, independently of frontend route guards.
- Currency is **IRR (rial)**. Model decimal fields normally serialize as strings;
  computed fields and analytics can return JSON numbers. Do not assume every
  monetary response has the same JSON type.
- Date/time fields use ISO 8601 with timezone support. The application timezone is
  `Asia/Tehran`; selected serializers also expose a display-only `jalali_date`.

### Pagination and errors

List viewsets use `page` and `page_size` (default 20, maximum 100), returning:

```json
{
  "count": 0,
  "total_pages": 1,
  "current_page": 1,
  "next": null,
  "previous": null,
  "results": []
}
```

Analytics views have their own object or array responses, not this envelope.
Search/filter/ordering support is endpoint-specific. For example:
`GET /api/v1/catalog/tires/?brand=1&size=2&search=radial&ordering=sale_price&page=1`.

Exceptions handled by the [custom handler](../backend/utils/exceptions.py) use:

```json
{
  "success": false,
  "status_code": 400,
  "errors": { "field_name": ["Validation message"] }
}
```

`errors` can also contain a list or `detail`. This is not a universal response
wrapper: explicitly returned errors, such as an invalid logout token, can be plain
`{"detail": "..."}`. Expect 400 for validation/business rules, 401 for invalid
credentials/tokens, 403 for insufficient permissions, 404 for unavailable objects,
405 for disallowed methods, and 429 for throttling.

## Authentication and users

Source: [account routes](../backend/apps/accounts/urls.py),
[views](../backend/apps/accounts/views.py), and
[serializers](../backend/apps/accounts/serializers.py).

| Method | Path relative to `/api/v1/` | Contract |
| --- | --- | --- |
| POST | `auth/login/` | `username`, `password`; returns `access`, `refresh`, and `user` |
| POST | `auth/token/refresh/` | `refresh`; returns a new access token and rotated refresh token |
| POST | `auth/logout/` | Authenticated; `refresh` to blacklist |
| GET | `auth/profile/` | Current user profile |
| PATCH / PUT | `auth/profile/` | Updates only `full_name` and `phone_number` |
| POST | `auth/change-password/` | `old_password`, `new_password` |
| CRUD | `auth/users/`, `auth/users/{id}/` | Manager user administration, with self-account and superuser protections |

Login's `user` contains `id`,
`username`, `full_name`, `role`, and `phone_number`. Profile responses additionally
include `role_display`, `is_active`, and `date_joined`.

The only roles are `MANAGER`, `TECHNICIAN`, and `WAREHOUSE`. Default access-token
lifetime is 60 minutes; refresh lifetime is 14 days, configurable in settings.
Refresh rotation blacklists the old refresh token in the database. Password changes
invalidate password-bound access/refresh tokens and blacklist outstanding refresh
tokens. Logout blacklists the submitted refresh token; it does **not** revoke an
already issued access token before expiry.

## Resource routes and permissions

Here, **CRUD** means list/create plus retrieve/update/delete at `{pk}/`, subject
to permissions and protected relationships. **List/create/retrieve** does not
include direct PUT, PATCH, or DELETE.

| Path relative to `/api/v1/` | Operations | Access for ordinary role accounts |
| --- | --- | --- |
| `crm/customers/` | CRUD | All authenticated users; delete manager-only |
| `crm/vehicles/` | CRUD; filter by `customer` | All authenticated users; delete manager-only |
| `catalog/brands/`, `catalog/sizes/`, `catalog/tires/` | CRUD | Read by all; write manager/warehouse |
| `catalog/tires/low-stock/` | GET | All authenticated users |
| `catalog/tires/{pk}/adjust-stock/` | POST | Manager/warehouse |
| `catalog/stock-movements/` | List/retrieve only | Manager/warehouse |
| `workshop/services/` | CRUD | Read by all; write manager-only |
| `procurement/suppliers/` | CRUD | Read by all; write manager/warehouse |
| `invoices/sales/` | List/create/retrieve | Manager/technician create; warehouse can read; technicians see only their own invoices |
| `invoices/sales/{pk}/confirm/` | POST | Manager/technician, within visible invoices |
| `invoices/sales/{pk}/cancel/` | POST | Manager-only |
| `invoices/purchases/` | List/create/retrieve | Manager/warehouse |
| `invoices/purchases/{pk}/cancel/` | POST | Manager-only |
| `invoices/returns/` | List/create/retrieve | Manager-only |
| `treasury/receipts/`, `treasury/payments/`, `treasury/customer-refunds/` | List/create/retrieve; POST `{pk}/cancel/` | Manager-only |
| `analytics/*` | GET reports listed below | Manager-only |

Most manager permission checks also permit superusers. See the
[account permissions](../backend/apps/accounts/permissions.py) and
[invoice views](../backend/apps/invoices/views.py) for action-specific checks.

Resource identifiers are not uniformly named `id`: examples include `customer_id`,
`vehicle_id`, `brand_id`, `size_id`, `tire_id`, `service_id`, `supplier_id`,
`sales_invoice_id`, `purchase_invoice_id`, `sales_return_id`, `movement_id`,
`receipt_id`, `payment_id`, and `refund_id`. Tire catalog records use
`tire_name` for the tire model/tread name. Technicians do not receive catalog `purchase_price`;
sales tire-line `unit_cost` is omitted for both technicians and warehouse users.
Warehouse users can still read catalog purchase prices and purchase invoices.

## Inventory and invoice workflows

Source: [catalog serializers](../backend/apps/catalog/serializers.py),
[invoice serializers](../backend/apps/invoices/serializers.py), and
[invoice services](../backend/apps/invoices/services.py).
The following IDs are illustrative; substitute existing records and sufficient stock.

### Stock adjustment

POST `catalog/tires/{pk}/adjust-stock/` with an absolute physical count:

```json
{ "counted_quantity": 12, "reason": "Physical stock count" }
```

A nonnegative count and nonblank reason are required; an unchanged count is rejected.
The response contains `message`, `movement_id`, `difference`, and `current_stock`.
`stock_quantity` is read-only in tire CRUD. Catalog updates do not change
`purchase_price`; purchase services own later cost changes.

### Sales

POST `invoices/sales/`:

```json
{
  "customer": 5,
  "vehicle": 3,
  "status": "CONFIRMED",
  "payment_status": "UNPAID",
  "discount_amount": "0.00",
  "tire_items": [{ "tire": 12, "quantity": 2, "unit_price": "28500000.00" }],
  "service_items": [{ "service": 1, "quantity": 2 }]
}
```

- At least one tire or service line is required; duplicate products/services must
  be combined. Quantities must be positive. Omitted line prices use catalog prices.
- A supplied vehicle must belong to the customer. Use either a fixed discount or
  a percentage discount, not both positive values.
- Default status is `CONFIRMED`; `DRAFT` does not consume stock. POST the draft's
  `confirm/` action without a body to deduct stock and finalize tire cost snapshots.
- Direct creation as `CANCELLED` or with payment status `PARTIAL` is rejected.
  `PAID` creation generates a receipt for a positive total; optional
  `payment_method` and `reference_number` describe that receipt.
- Create returns the full read representation, including computed `paid_amount`,
  `remaining_amount`, `returned_amount`, `net_amount`, and `excess_amount`.
- POST `cancel/` without a body. Unlike voucher cancellation, this action does not
  accept a cancellation reason contract. Returns or active receipts block cancellation.

Numbers are generated server-side in Jalali-year formats such as `S-1405-00001`
(sale) and `P-1405-00001` (purchase).

### Purchases and returns

POST `invoices/purchases/` with `supplier` and nonempty `tire_items`, for example:

```json
{ "supplier": 2, "tire_items": [{ "tire": 12, "quantity": 4, "unit_cost": "22000000.00" }] }
```

Purchases are created confirmed, increase stock, and update the latest purchase
price. The create serializer does not expose draft/payment-status controls and
there is no purchase-confirm action. Cancellation can fail for active payments,
insufficient stock, or missing historical cost information.

POST `invoices/returns/` with `sales_invoice`, nonblank `reason`, and `items`:

```json
{
  "sales_invoice": 104,
  "reason": "Customer returned an unused tire",
  "items": [{ "sales_invoice_tire_item_id": 21, "quantity": 1 }]
}
```

Only confirmed invoices and their unreturned tire quantities are eligible. An
optional `return_date` must not be in the future. The service applies the original
discount share, restocks tires, and the API enables automatic creation of a refund
voucher when net receipts exceed the revised invoice value. A return amount is
not itself evidence of cash refunded.

## Treasury and analytics

[Voucher serializers](../backend/apps/finance/serializers.py) accept positive
`amount`, the related invoice, and optional date, `payment_method`,
`reference_number`, and `notes`. Receipts use `sales_invoice`; payments use
`purchase_invoice`; customer refunds use `sales_invoice` and optionally a matching
`sales_return`. Amounts are bounded by remaining debt or refundable excess.
POST a voucher's `cancel/` action with `{"reason": "Duplicate entry"}`.
These are payment records, not a bank/payment-gateway integration or a double-entry ledger.

[Analytics routes](../backend/apps/reports/urls.py):

| GET path under `analytics/` | Response / query |
| --- | --- |
| `dashboard-stats/` | `today_revenue`, `today_invoices_count`, `total_receivables`, `unpaid_invoices_count`, `total_inventory_value`, `total_tires_stock`, `low_stock_count` |
| `sales-by-brand/` | Array of brand quantities/revenue, after discounts and returns; optional `brand_id` |
| `profitability/` | Array of tire sales, revenue, snapshot cost, and profit after discounts/returns; not company net income |
| `inventory-value/` | `total_inventory_value` and `items`, using current purchase prices |
| `sales-by-date/` | `start_date`, `end_date` accept Gregorian or Jalali dates; returns counts, gross sales, return amounts, and net sales |

Date-range sales use invoice dates for sales and return dates for returns,
independently of cash-refund dates; net sales can be negative in a return-heavy period.

Outside `/api/v1/`, `/api/health/` publicly reports database connection availability
(200 or 503). `/api/schema/`, `/api/docs/`, and `/api/redoc/` provide generated
documentation: public with debug enabled or `ENABLE_DOCS_IN_PROD`, otherwise
manager/superuser-only. Keep that public override off in production.
