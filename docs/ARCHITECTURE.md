# System Architecture & Technical Specifications

## 1. Architectural Philosophy

The **Tire Shop Management System** is engineered as an enterprise-grade, transactional web platform. It enforces strict separation of concerns, transactional consistency, auditability, and defense-in-depth security.

The system addresses the operational and financial challenges of retail and wholesale tire dealerships:
1. **Accurate Stock Valuation & Double-Entry Inventory**: Stock is tracked through immutable ledgers rather than simple counters.
2. **Strict Financial Integrity**: Every monetary transfer, invoice payment, and refund creates double-entry financial vouchers.
3. **High-Concurrency Resilience**: Critical inventory and treasury operations are protected against race conditions and deadlocks using pessimistic row-level locking.
4. **Role-Based Access Control (RBAC)**: Zero-trust resource access boundaries tailored to distinct organizational roles.

---

## 2. High-Level System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                 Client Layer (Browser / Mobile)             │
│   React 19 + TypeScript + Tailwind CSS + Lucide + Recharts  │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / JSON REST API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                Reverse Proxy & Edge Security                │
│                 (Nginx / Traefik / Cloudflare)              │
│       SSL Termination • Rate Throttling • Static Assets     │
└──────────────────────────────┬──────────────────────────────┘
                               │ WSGI (Gunicorn) / ASGI
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Backend Layer (Django 5.x / 6.x & DRF)         │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Authentication &    │       │    REST API Views     │  │
│  │      RBAC Guard       │       │    & ViewSets         │  │
│  └───────────┬───────────┘       └───────────┬───────────┘  │
│              │                               │              │
│              ▼                               ▼              │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Validation Layer    │       │    Service Layer      │  │
│  │     (Serializers)     │◄─────►│    (services.py)      │  │
│  └───────────────────────┘       └───────────┬───────────┘  │
│                                              │              │
│                                              ▼              │
│                                  ┌───────────────────────┐  │
│                                  │   ORM & Transactions  │  │
│                                  │  (Row Locks & Atomic) │  │
│                                  └───────────┬───────────┘  │
└──────────────────────────────────────────────┼──────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
┌──────────────────────────────┐                               ┌──────────────────────────────┐
│  Primary Relational Database │                               │   Shared Cache & Broker      │
│  PostgreSQL 16+ / SQLite     │                               │      Redis (Production)      │
│  ACID Transactions & MVCC    │                               │ Rate Limits & Distributed    │
└──────────────────────────────┘                               └──────────────────────────────┘
```

---

## 3. Backend Architecture: Clean Service Layer Pattern

The backend follows a four-tier architecture designed to keep controllers thin and domain logic testable:

```
[ HTTP Request ]
       │
       ▼
1. View Layer (views.py)
   - Route handling & HTTP verb dispatching
   - Permission verification (IsAuthenticated, HasRole)
   - Pagination, search, and ordering backend
       │
       ▼
2. Serializer Layer (serializers.py)
   - Type coercion and field-level validation
   - Nested schema serialization
   - Masking sensitive financial metrics (e.g. unit_cost) for unauthorized roles
       │
       ▼
3. Service Layer (services.py)
   - Core domain business logic execution
   - Atomic transaction boundaries (`transaction.atomic`)
   - Pessimistic locking (`select_for_update`)
   - Cross-domain coordination (Invoicing -> Catalog -> Treasury)
       │
       ▼
4. Persistence Layer (models.py)
   - Schema definitions, constraints, indexes
   - Computed properties and domain queries
```

### Why a Dedicated Service Layer?
In typical Django REST Framework applications, business logic often leaks into `serializers.save()` or `views.perform_create()`. This application enforces a strict rule:
- **Complex multi-table state transitions MUST reside in `services.py`.**
- For example:
  - `create_sales_invoice_service`: Validates stock, calculates sequential invoice numbers, records tire line items, creates service items, snapshots unit costs, issues automatic cash receipts (if paid), and decrements inventory atomically.
  - `confirm_sales_invoice_service`: Acquires locks on tires in deterministic order, confirms draft state, registers ledger movements, and updates available quantities.
  - `create_sales_return_service`: Validates item return ceilings, records return vouchers, issues customer refunds, and restocks inventory.

---

## 4. Concurrency & Deadlock Prevention

In a busy automotive dealership, multiple cashiers and warehouse staff may concurrently perform transactions affecting the same inventory items.

### 4.1 Pessimistic Locking with `select_for_update`
To avoid lost updates and overselling:
```python
# Acquire row-level locks on tire catalog records inside an atomic block
tires = list(
    Tire.objects.select_for_update()
    .filter(pk__in=sorted_tire_ids)
    .order_by('pk')
)
```

### 4.2 Deterministic Resource Ordering (Deadlock Elimination)
When two transactions concurrently attempt to acquire locks on multiple rows in reverse orders, a relational database can deadlock:
- **Transaction A**: Locks Tire #1, then requests Tire #2.
- **Transaction B**: Locks Tire #2, then requests Tire #1.

**Our Mitigation**:
The system enforces sorted ID ordering (`sorted_tire_ids = sorted(tire_ids)`) before executing `select_for_update()`. All concurrent transactions acquire locks in identical numerical sequence, mathematically eliminating cyclic wait conditions and deadlocks.

### 4.3 Gapless Sequential Invoice Numbering
Invoice numbers follow an annual sequential format (`INV-YYYY-XXXXXX`). To avoid numbering collisions during concurrent invoice creations:
- An isolated counter row is locked using `select_for_update()`.
- The sequence is incremented atomically within the creation transaction.
- If the transaction rolls back, sequence integrity remains consistent without gaps.

---

## 5. Double-Entry Inventory & Financial Ledger

### 5.1 Immutable Stock Movement Ledger
Inventory quantity on `Tire.stock_quantity` is not an unverified scalar counter. It is backed by a transactional audit trail in `StockMovement`:

| Movement Type | Code | Effect on Stock | Triggering Action |
|:---|:---|:---:|:---|
| Initial Inventory | `INITIAL` | `+` | Initial catalog item onboarding |
| Purchase Inflow | `PURCHASE` | `+` | Purchase invoice confirmation |
| Sales Outflow | `SALE` | `-` | Sales invoice confirmation |
| Purchase Cancel | `PURCHASE_CANCEL` | `-` | Purchase invoice cancellation |
| Sales Cancellation | `SALE_CANCEL` | `+` | Sales invoice cancellation |
| Customer Return | `SALE_RETURN` | `+` | Sales return voucher execution |
| Physical Stock Audit | `MANUAL_ADJUSTMENT` | `+/-` | Warehouse manager physical audit |

Every movement records:
- `quantity`: Exact units moved.
- `unit_price`: Cost valuation at movement time.
- `created_by`: Authorized user responsible for the action.
- `created_at`: Jalali and UTC timestamp of the operation.

### 5.2 Treasury & Double-Entry Vouchers
The treasury subsystem maintains financial equilibrium across three voucher types:
1. **ReceiptVoucher**: Inflows from customer invoice payments (Cash, POS, Bank Transfer).
2. **PaymentVoucher**: Outflows to suppliers for purchase invoices.
3. **CustomerRefundVoucher**: Outflows returning funds for returned goods or overpayments.

Each voucher tracks:
- Unique voucher ID and optional external POS/bank tracking number (`reference_number`).
- Invoice association and remaining balance recalculation.
- Cancellation audit metadata (`is_cancelled`, `cancellation_reason`, `cancelled_at`).

---

## 6. Security Architecture & Threat Modeling

### 6.1 Authentication & Password-Bound JWT Invalidation
Authentication uses JSON Web Tokens (`djangorestframework-simplejwt`) with critical security enhancements:
1. **Stateless JWTs with Short Lifetimes**: Access tokens expire in 60 minutes; refresh tokens rotate upon use.
2. **Immediate Password-Change Revocation**:
   - Standard JWT implementations cannot invalidate active access tokens before expiry when a password is changed.
   - This system embeds a truncated password hash fingerprint into token claims.
   - When a user changes their password, all previously issued access and refresh tokens are immediately rejected by middleware, terminating compromised sessions instantly.
3. **Blacklisting on Logout**: Refresh tokens are blacklisted in Redis / database upon logout.

### 6.2 Broken Object Level Authorization (BOLA/IDOR) Protection
- Multi-tenant data segregation:
  - Technicians can only view invoices they personally created.
  - Managers and Accountants have visibility across the organization.
  - Warehouse operators have zero access to financial totals, profit margins, or unit purchase costs.

### 6.3 Rate Limiting & Throttling
Protects against brute force and credential stuffing:
- `AnonRateThrottle`: 30 requests/minute.
- `UserRateThrottle`: 300 requests/minute.
- `LoginIPThrottle`: 5 login attempts/minute per IP address.
- `LoginUsernameThrottle`: 5 login attempts/minute per username.

---

## 7. Frontend Architecture

### 7.1 Single Page Application Structure
Built on **React 19**, **TypeScript 5.x**, and **Vite 6**:
- **Tailwind CSS**: Utility-first responsive styling with dark/light theme foundation.
- **Lucide React**: Modern, consistent iconography.
- **Recharts**: Responsive SVG charts for revenue, margins, and sales volume analytics.

### 7.2 Context Providers
- `AuthContext`: Manages active user identity, token lifecycle, local session persistence, and permission queries (`hasRole()`).
- `LanguageContext`: Manages bilingual state (Persian / English), document direction (`rtl` / `ltr`), and localized application strings.

### 7.3 Resilient HTTP Layer & Error Envelope
The Axios client interceptor transforms backend validation envelopes (`{ success: false, errors: {...} }`) into human-readable Persian or English notifications, handling network drops, token refreshes, and 401 unauthenticated transitions automatically.
