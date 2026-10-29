# Database Design & Schema Specification

## 1. Schema Overview

The Tire Shop Management database is designed with strict relational principles, third normal form (3NF) adherence, financial immutability, and transactional data integrity.

The system supports:
- **PostgreSQL 16+**: Recommended for production environments (MVCC, pessimistic row-level locking, rich indexing).
- **SQLite 3**: Supported for local development and rapid test execution.
- **Microsoft SQL Server**: Supported via Django MSSQL backend.

---

## 2. Entity Relationship Overview

```
                      ┌───────────────┐
                      │  Custom User  │
                      │(accounts_user)│
                      └───────┬───────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│     Customer     │ │     Supplier     │ │   Tire Catalog   │
│  (crm_customer)  │ │(suppliers_suppl.)│ │  (catalog_tire)  │
└─────────┬────────┘ └────────┬─────────┘ └───────┬──────────┘
          │                   │                   │
          ▼                   │                   │
┌──────────────────┐          │                   │
│     Vehicle      │          │                   │
│  (crm_vehicle)   │          │                   │
└─────────┬────────┘          │                   │
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Sales Invoice   │ │ Purchase Invoice │ │  Stock Movement  │
│ (invoices_sales) │ │(invoices_purch.) │ │ (catalog_stock)  │
└─────────┬────────┘ └────────┬─────────┘ └──────────────────┘
          │                   │
          ├───────────────────┤
          ▼                   ▼
┌──────────────────┐ ┌──────────────────┐
│  Receipt Voucher │ │  Payment Voucher │
│ (finance_receipt)│ │ (finance_payment)│
└──────────────────┘ └──────────────────┘
```

---

## 3. Core Entities & Tables

### 3.1 Authentication & Authorization (`apps.accounts`)

#### Table: `accounts_user`
Stores user credentials, organizational roles, and security audit timestamps.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Internal user ID |
| `username` | CharField(150) | Unique, Indexed | Login handle |
| `full_name` | CharField(150) | Not Null | Display name (Persian/English) |
| `role` | CharField(20) | Choices (`MANAGER`, `ACCOUNTANT`, `WAREHOUSE`, `TECHNICIAN`) | RBAC role |
| `phone_number` | CharField(20) | Nullable, Indexed | Contact mobile number |
| `is_active` | Boolean | Default True | Account active status |
| `is_staff` | Boolean | Default False | Admin access flag |
| `date_joined` | DateTime | Auto now add | Account creation timestamp |

---

### 3.2 Inventory & Catalog (`apps.catalog`)

#### Table: `catalog_brand`
Stores manufacturer brands (e.g., Michelin, Bridgestone, Barez, Yazd Tire).

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Brand identifier |
| `name` | CharField(100) | Unique, Indexed | Brand name |
| `country` | CharField(100) | Nullable | Country of origin |

#### Table: `catalog_size`
Stores standardized tire dimension classifications (e.g., `185/65R14`, `205/55R16`).

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Size identifier |
| `size_name` | CharField(50) | Unique, Indexed | Standard dimension code |

#### Table: `catalog_tire`
Core tire SKU catalog with pricing, physical stock projection, and alerts.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | SKU identifier |
| `brand_id` | ForeignKey -> `catalog_brand` | `on_delete=PROTECT` | Manufacturer brand |
| `size_id` | ForeignKey -> `catalog_size` | `on_delete=PROTECT` | Dimensional size |
| `pattern` | CharField(100) | Blankable | Tread pattern model name |
| `purchase_price` | DecimalField(14, 2) | Check >= 0 | Current baseline purchase cost (IRR) |
| `sale_price` | DecimalField(14, 2) | Check >= 0 | Retail sale price (IRR) |
| `stock_quantity` | IntegerField | Check >= 0 | Projected on-hand units |
| `min_stock_alert`| IntegerField | Default 4 | Low stock threshold alert |

#### Table: `catalog_stockmovement`
The immutable double-entry stock ledger. Every physical unit entering or exiting inventory is written here.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Ledger entry ID |
| `tire_id` | ForeignKey -> `catalog_tire` | `on_delete=PROTECT` | Affected tire item |
| `movement_type` | CharField(30) | Indexed | Enum (`INITIAL`, `PURCHASE`, `SALE`, `SALE_RETURN`, `SALE_CANCEL`, `PURCHASE_CANCEL`, `MANUAL_ADJUSTMENT`) |
| `quantity` | IntegerField | Non-zero | Units changed (signed) |
| `unit_price` | DecimalField(14, 2) | Check >= 0 | Item cost at transaction time |
| `reference_number` | CharField(100) | Nullable | External document number |
| `sales_invoice_id` | ForeignKey -> `invoices_salesinvoice` | Nullable, `PROTECT` | Originating sales invoice |
| `purchase_invoice_id` | ForeignKey -> `invoices_purchaseinvoice` | Nullable, `PROTECT` | Originating purchase invoice |
| `created_by_id` | ForeignKey -> `accounts_user` | Nullable, `PROTECT` | User who authorized movement |
| `created_at` | DateTime | Auto now add | Transaction timestamp |

---

### 3.3 Customer Relationship Management (`apps.customers`)

#### Table: `customers_customer`
Profiles of retail and fleet clients.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Customer ID |
| `full_name` | CharField(150) | Indexed | Customer legal or personal name |
| `phone_number` | CharField(20) | Conditional Unique | Normalized phone number |
| `national_code`| CharField(20) | Conditional Unique | Iranian National ID / Tax ID |
| `address` | TextField | Blankable | Physical or mailing address |

#### Table: `customers_vehicle`
Vehicles associated with registered customers, tracking Iranian license plates.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Vehicle ID |
| `customer_id` | ForeignKey -> `customers_customer` | `on_delete=CASCADE` | Vehicle owner |
| `license_plate`| CharField(30) | Unique, Indexed | Normalized Iranian plate |
| `model` | CharField(100) | Indexed | Vehicle model (e.g. Samand, Pride, Tara) |
| `tire_size_recommended` | CharField(50) | Blankable | Recommended OEM tire size |

---

### 3.4 Invoicing & Sales Operations (`apps.invoices`)

#### Table: `invoices_salesinvoice`
Header record for customer sales invoices.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Internal invoice ID |
| `invoice_number` | CharField(50) | Unique, Indexed | Sequential number (`INV-2026-000001`) |
| `customer_id` | ForeignKey -> `customers_customer` | `on_delete=PROTECT` | Bill-to customer |
| `vehicle_id` | ForeignKey -> `customers_vehicle` | Nullable, `PROTECT` | Service vehicle |
| `status` | CharField(20) | Indexed | State (`DRAFT`, `CONFIRMED`, `CANCELLED`) |
| `payment_status` | CharField(20) | Indexed | Payment state (`UNPAID`, `PARTIAL`, `PAID`) |
| `total_amount` | DecimalField(14, 2) | Check >= 0 | Final payable total after discounts |
| `discount_amount`| DecimalField(14, 2) | Default 0.00 | Applied cash discount |
| `created_by_id` | ForeignKey -> `accounts_user` | `on_delete=PROTECT` | Creator/cashier |
| `created_at` | DateTime | Auto now add, Indexed | Invoice creation timestamp |

#### Table: `invoices_salesinvoicetireitem`
Line items for tire products sold on a sales invoice.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `id` | BigAutoField | Primary Key | Line item ID |
| `sales_invoice_id` | ForeignKey -> `invoices_salesinvoice`| `on_delete=CASCADE` | Parent invoice |
| `tire_id` | ForeignKey -> `catalog_tire` | `on_delete=PROTECT` | Selected tire SKU |
| `quantity` | IntegerField | Check > 0 | Units sold |
| `unit_price` | DecimalField(14, 2) | Check >= 0 | Selling unit price |
| `unit_cost` | DecimalField(14, 2) | Check >= 0 | Snapshot of purchase cost at sale confirmation |
| `total_price` | DecimalField(14, 2) | Check >= 0 | Line total (`quantity * unit_price`) |

---

### 3.5 Treasury & Financial Vouchers (`apps.finance`)

#### Table: `finance_receiptvoucher`
Tracks incoming payments from customers against sales invoices.

| Column | Type | Constraints | Description |
|:---|:---|:---|:---|
| `receipt_id` | BigAutoField | Primary Key | Unique voucher ID |
| `sales_invoice_id` | ForeignKey -> `invoices_salesinvoice`| `on_delete=PROTECT` | Associated invoice |
| `amount` | DecimalField(14, 2) | Check > 0 | Amount received (IRR) |
| `payment_method` | CharField(50) | Required | POS Card, Cash, Bank Transfer |
| `reference_number`| CharField(100) | Nullable, Indexed | Bank/POS transaction trace code |
| `is_cancelled` | Boolean | Default False | Cancellation flag |
| `cancellation_reason` | TextField | Blankable | Reason for cancellation |
| `created_by_id` | ForeignKey -> `accounts_user` | `on_delete=PROTECT` | Voucher cashier |
| `created_at` | DateTime | Auto now add | Receipt timestamp |

---

## 4. Integrity Constraints & Foreign Key Protection

1. **Deletion Protection (`on_delete=models.PROTECT`)**:
   - Master data (Customers, Suppliers, Tires, Brands, Sizes) cannot be deleted if historical invoices or stock movements reference them.
   - Prevents accidental destruction of financial audit trails.
2. **Zero Negative Inventory Constraint**:
   - `models.CheckConstraint(check=models.Q(stock_quantity__gte=0))` guarantees the database itself will abort any operation resulting in negative inventory.
3. **Decimal Precision for Iranian Rial**:
   - `max_digits=14, decimal_places=2` enables transaction values up to 999 billion Tomans / ~10 trillion Rials with exact decimal precision, preventing floating-point rounding discrepancies.
