# Database Design

This guide summarizes the current Django models and migrations, not a dump of a
verified live database. Use migrations to create/upgrade a database; do not recreate
it from historical SQL scripts. See the [root README](../README.md) for setup and
environment variables and the [deployment guide](DEPLOYMENT_GUIDE.md) for checks.

## Backend selection and storage conventions

[Settings](../backend/config/settings.py) select:

- PostgreSQL for `DB_ENGINE=postgres` or `postgresql`.
- SQL Server for `DB_ENGINE=mssql` / `sqlserver`, or `USE_SQL_SERVER=True`, unless
  the PostgreSQL branch was selected first. SQL Server requires a native ODBC
  driver as well as the Python dependencies.
- SQLite at `backend/db.sqlite3` otherwise. An unrecognized engine value also falls
  through to SQLite, so verify the selected backend before deployment.

The latest full suites passed on SQLite and PostgreSQL, including the
PostgreSQL-specific concurrency tests. SQL Server remains unverified; see the
[release record](RELEASE_READINESS.md) for the exact checks and remaining limits.

Business tables often use explicit legacy names and `AutoField` primary keys,
not Django's default `app_model` names. Exact names and case matter, including
`Tier` for tires. Django auth/session/permission and SimpleJWT blacklist tables
also exist; they are not enumerated below. `reports` adds no business tables.

## Model-to-table map

See the [entity relationship diagram](../README.md#entity-relationship-diagram)
for the operational relationships. The tables below include the audit and
numbering models omitted from that overview.

### Users, catalog, customers, and suppliers

| Model | Database table | Primary key | Selected stored fields / relationships |
| --- | --- | --- | --- |
| [User](../backend/apps/accounts/models.py) | `Users` | `id` (BigAutoField) | AbstractUser fields plus `role`, blankable `full_name` (150), optional `phone_number` (20) |
| [Brand](../backend/apps/catalog/models.py) | `Brand` | `brand_id` (AutoField) | Unique `brand_name` (50); no country column |
| Size | `Size` | `size_id` (AutoField) | Unique `size_name` (50) |
| Tire | `Tier` | `tire_id` (AutoField) | `tire_name` (150), brand, size, stock, sale/purchase prices, `min_stock_alert` (default 5) |
| StockMovement | `Stock_movement` | `movement_id` (BigAutoField) | Tire, signed `quantity`, `movement_type`, `balance_after`, optional invoice/return links and `unit_cost`, user, description, `created_at` |
| StockProjectionRepair | `catalog_stockprojectionrepair` | `id` (BigAutoField) | Tire, `stock_before`, `stock_after`, optional `last_movement`, authorizing user, reason, timestamp |
| [Customer](../backend/apps/customers/models.py) | `Customer` | `customer_id` (AutoField) | `full_name` (100), optional phone (20), national code (10), address (255), created/updated timestamps |
| Vehicle | `Vehicle` | `vehicle_id` (AutoField) | Customer, unique `license_plate` (20), model (100), year (10), recommended tire size (50), notes |
| [Supplier](../backend/apps/suppliers/models.py) | `Supplier` | `supplier_id` (AutoField) | Unique `supplier_name` (100), optional phone (20), address (200) |
| [Service](../backend/apps/services_app/models.py) | `Services` | `service_id` (AutoField) | `service_name` (150), price, description |

`User.role` has only `MANAGER`, `TECHNICIAN`, and `WAREHOUSE` (default technician).
Nonempty user phone numbers are conditionally unique. Customer nonempty phone
numbers and national codes each have conditional unique constraints. Relevant
model/serializer paths normalize Persian/Arabic digits and blank optional
identifiers; this is not a guarantee that arbitrary direct SQL writes are normalized.

### Invoices and returns

Source: [invoice models](../backend/apps/invoices/models.py).

| Model | Database table | Primary key | Selected stored fields / relationships |
| --- | --- | --- | --- |
| InvoiceSequence | `Invoice_Sequences` | `id` (BigAutoField) | `doc_type`, Jalali `year`, `last_number`; unique `(doc_type, year)` |
| SalesInvoice | `Sales_invoice` | `sales_invoice_id` (AutoField) | Unique `invoice_number` (32), invoice date, customer, optional vehicle, total, fixed/percentage discounts, status, payment status, notes, creator, updated timestamp |
| SalesInvoiceTireItem | `SalesInvoice_TireItems` | `id` (BigAutoField) | Sales invoice, tire, quantity, `unit_price`, `unit_cost` snapshot |
| SalesInvoiceServiceItem | `SalesInvoice_ServiceItems` | `id` (BigAutoField) | Sales invoice, service, quantity, `unit_price` |
| PurchaseInvoice | `Purchase_invoice` | `purchase_invoice_id` (AutoField) | Unique `invoice_number` (32), invoice date, supplier, total, status, payment status, creator, updated timestamp |
| PurchaseInvoiceTireItem | `PurchaseInvoice_TireItems` | `id` (BigAutoField) | Purchase invoice, tire, quantity, `unit_cost`, nullable `previous_purchase_price` |
| SalesReturn | `Sales_return` | `sales_return_id` (AutoField) | Sales invoice, return date, reason, `total_refund_amount`, creator, created timestamp |
| SalesReturnItem | `SalesReturn_Items` | `id` (BigAutoField) | Return document, original sales tire line, tire, quantity, original price/cost, discounted `refund_amount` |

Invoice states are `DRAFT`, `CONFIRMED`, and `CANCELLED`; model defaults are
`CONFIRMED`. Payment states are `UNPAID`, `PARTIAL`, and `PAID`, defaulting to
`UNPAID`. API workflows expose fewer transitions than the model choices: purchases
are created confirmed, for example. Numbers use `S-1405-00001` / `P-1405-00001`
formats, not Gregorian `INV-YYYY-XXXXXX` numbers.

Sales `returned_amount`, `net_amount`, `paid_amount`, `remaining_amount`, and
`excess_amount` are computed properties/query annotations, not stored balance
columns. Serialized line `total_price` is also computed, not a table column.
For sales, ignoring optional query annotations:

```text
returned_amount = sum(return document totals)
net_amount      = max(total_amount - returned_amount, 0)
paid_amount     = max(active receipts - active refunds, 0)
remaining       = max(net_amount - paid_amount, 0)
excess          = max(active receipts - active refunds - net_amount, 0)
```

`payment_status` is stored and synchronized by financial services. Purchase
payment status is based on non-cancelled supplier-payment vouchers.

### Treasury

Source: [finance models](../backend/apps/finance/models.py).

| Model | Database table | Primary key (AutoField) | Required invoice link / date |
| --- | --- | --- | --- |
| ReceiptVoucher | `Receipt_voucher` | `receipt_id` | Sales invoice / `receipt_date` |
| PaymentVoucher | `Payment_voucher` | `payment_id` | Purchase invoice / `payment_date` |
| CustomerRefundVoucher | `Customer_refund_voucher` | `refund_id` | Sales invoice / `refund_date`; optional sales-return link |

All three store positive `amount`, `payment_method`, optional `reference_number`,
notes, creator, and cancellation metadata (`is_cancelled`, `cancelled_at`,
`cancelled_by`, `cancellation_reason`). These are payment/refund records, not
paired debit/credit entries. There is no chart of accounts or general-ledger schema.

`LegacyInvoiceItem` maps to `Invoice_items` with `managed=False`. Django migrations
do not create/manage that table; current invoice workflows use the line tables above.

## Integrity and lifecycle rules

- **Money:** most business amounts are `DecimalField(14, 2)`, with up to 12 whole
  digits (`999999999999.99` IRR). Percentage discounts are `(5, 2)`; the unmanaged
  legacy line price is `(18, 2)`. The configured canonical currency is IRR, even
  where older field labels mention rial/toman. Report JSON may use floats.
- **Database constraints:** tires have nonnegative stock/sale-price/purchase-price
  checks; service price is nonnegative; voucher amounts are positive. Invoice
  lines have unique invoice/product pairs and selected nonnegative price/cost
  checks. These are not blanket constraints on every amount or business rule.
- **Application validation:** positive line quantities, invoice-total limits,
  mutually exclusive discounts, vehicle ownership, stock availability, return
  ceilings, and payment ceilings also depend on serializers/services. Do not
  assume a model validator runs on every ORM save or that direct SQL is safe.
- **Relationships:** brands/sizes referenced by tires, customers/suppliers
  referenced by invoices, tires/services referenced by lines, and invoices
  referenced by movements/vouchers/returns use `PROTECT`. Invoice-to-line and
  return-to-line links use `CASCADE`. Customer-to-vehicle uses `CASCADE`, while
  a sales invoice's optional vehicle uses `SET_NULL`. Most creator/canceller
  references use `SET_NULL`; projection-repair references use `PROTECT`.
- **API lifecycle:** invoice and voucher APIs prohibit direct editing/deletion;
  explicit actions handle confirmation/cancellation. This is application-level
  protection, not a database trigger preventing all historical changes.
- **Stock:** `stock_quantity` is the current projection. `StockMovement.quantity`
  is a signed delta with `balance_after`, not a paired ledger posting. Movement
  codes are `INITIAL_STOCK`, `PURCHASE`, `PURCHASE_CANCEL`, `SALE`, `SALE_CANCEL`,
  `SALE_RETURN`, and `MANUAL_ADJUSTMENT`.

## Migration and recovery considerations

Sales tire-line cost is snapshotted for reporting; draft confirmation finalizes it
at stock-out time. Purchases store the prior catalog cost so cancellation can
restore an earlier price rather than rewriting sales history. The
[previous-price migration](../backend/apps/invoices/migrations/0015_purchase_item_previous_purchase_price.py)
deliberately leaves unknown legacy baselines null. A cancellation needing such a
missing baseline can fail and requires investigation, not an invented zero cost.

`reconcile_stock` compares stock projections with summed movements; its explicit
repair mode records a [StockProjectionRepair](../backend/apps/catalog/migrations/0009_stock_projection_repair.py)
and changes the projection without creating fictitious physical movements.
Physical stocktaking is a separate operation. `reconcile_payments` reports stored
payment-status discrepancies without changing them. See the
[operational guide](DEPLOYMENT_GUIDE.md) before using either command.
