# REST API Reference & Specification

## 1. Overview & Conventions

All endpoints in the Tire Shop Management System adhere to RESTful conventions, using standard HTTP methods and JSON request/response bodies.

- **Base URL**: `/api/v1`
- **Authentication Scheme**: JWT Bearer Token (`Authorization: Bearer <access_token>`)
- **Character Encoding**: UTF-8
- **Date/Time Standard**: ISO 8601 UTC (`2026-10-29T12:00:00Z`) with dual Jalali representation

---

## 2. Global Error Envelope

When a client request fails due to validation errors, business rule violations, or unauthorized access, the API responds with a structured envelope:

```json
{
  "success": false,
  "status_code": 400,
  "errors": {
    "field_name": [
      "Validation message in localized language"
    ]
  }
}
```

Common status codes:
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Payload validation or domain business invariant failure.
- `401 Unauthorized`: Missing, expired, or revoked JWT token.
- `403 Forbidden`: Authenticated user lacks RBAC permissions for the target resource.
- `404 Not Found`: Resource does not exist.
- `429 Too Many Requests`: Rate limit threshold exceeded.

---

## 3. Authentication Endpoints (`/api/v1/auth`)

### 3.1 Obtain JWT Pair
```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "admin",
  "password": "secure_password"
}
```
**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 3.2 Refresh Access Token
```http
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 3.3 Current User Profile
```http
GET /api/v1/auth/profile/
Authorization: Bearer <access_token>
```
**Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "full_name": "مدیر فروشگاه",
  "role": "MANAGER",
  "role_display": "مدیر سیستم",
  "phone_number": "09121112233"
}
```

### 3.4 Change Password
Immediately invalidates all existing JWT access and refresh tokens across all user devices.
```http
POST /api/v1/auth/change-password/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "old_password": "current_password",
  "new_password": "NewComplexPassword!827"
}
```

---

## 4. Tire Catalog & Inventory (`/api/v1/catalog`)

### 4.1 List Tires
Supports search, brand filtering, size filtering, and pagination.
```http
GET /api/v1/catalog/tires/?search=Barez&brand=1&size=2&page=1
Authorization: Bearer <access_token>
```
**Response (200 OK):**
```json
{
  "count": 48,
  "next": "/api/v1/catalog/tires/?page=2",
  "previous": null,
  "results": [
    {
      "id": 12,
      "brand_name": "بارز (Barez)",
      "size_name": "185/65R14",
      "pattern": "Alborz P648",
      "sale_price": "28500000.00",
      "stock_quantity": 24,
      "min_stock_alert": 4,
      "is_low_stock": false
    }
  ]
}
```
*Note: The `purchase_price` field is automatically hidden from users with the `TECHNICIAN` role.*

### 4.2 Stock Movement Ledger
```http
GET /api/v1/catalog/movements/?movement_type=SALE&tire=12
Authorization: Bearer <access_token>
```

---

## 5. Sales Invoices (`/api/v1/invoices/sales`)

### 5.1 Create Sales Invoice
```http
POST /api/v1/invoices/sales/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "customer": 5,
  "vehicle": 3,
  "status": "CONFIRMED",
  "payment_status": "PAID",
  "payment_method": "کارتخوان سامان",
  "reference_number": "POS-TRACE-992817",
  "discount_amount": "0.00",
  "tire_items": [
    {
      "tire": 12,
      "quantity": 4,
      "unit_price": "28500000.00"
    }
  ],
  "service_items": [
    {
      "service": 1,
      "quantity": 4,
      "unit_price": "1500000.00"
    }
  ]
}
```
**Response (201 Created):**
```json
{
  "sales_invoice_id": 104,
  "invoice_number": "INV-2026-000104",
  "customer": 5,
  "total_amount": "120000000.00",
  "paid_amount": "120000000.00",
  "remaining_amount": "0.00",
  "status": "CONFIRMED",
  "payment_status": "PAID"
}
```

### 5.2 Confirm Draft Invoice
Atomically locks catalog items, deducts inventory, records ledger movements, and transitions state from `DRAFT` to `CONFIRMED`.
```http
POST /api/v1/invoices/sales/104/confirm/
Authorization: Bearer <access_token>
```

### 5.3 Cancel Sales Invoice
```http
POST /api/v1/invoices/sales/104/cancel/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "reason": "Customer changed mind before tire fitting"
}
```

---

## 6. Treasury Vouchers (`/api/v1/treasury`)

### 6.1 Issue Receipt Voucher
```http
POST /api/v1/treasury/receipts/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "sales_invoice": 104,
  "amount": "50000000.00",
  "payment_method": "کارتخوان پاسارگاد",
  "reference_number": "POS-554433"
}
```

### 6.2 Cancel Voucher
```http
POST /api/v1/treasury/receipts/42/cancel/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "reason": "Duplicate transaction entry"
}
```

---

## 7. Reports & Analytics (`/api/v1/reports`)

### 7.1 Executive Dashboard Metrics
```http
GET /api/v1/reports/dashboard-stats/
Authorization: Bearer <access_token>
```
**Response (200 OK):**
```json
{
  "total_sales_month": "850000000.00",
  "total_purchases_month": "620000000.00",
  "net_profit_month": "180000000.00",
  "unpaid_invoices_count": 6,
  "total_receivables": "45000000.00",
  "low_stock_tires_count": 3
}
```
