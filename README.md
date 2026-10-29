# Tire Shop Management System (سامانه مدیریت فروشگاه و خدمات لاستیک) 🛞

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x%20%7C%206.x-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19.x-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.x-646cff.svg)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38bdf8.svg)](https://tailwindcss.com/)
[![Pytest](https://img.shields.io/badge/Pytest-323%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

An enterprise-grade, full-stack ERP and Point-of-Sale (POS) management platform engineered for automotive tire dealerships, warehouses, and mechanical workshops. Built with **Django REST Framework** on the backend and **React 19 + TypeScript + Tailwind CSS** on the frontend, the system delivers high-concurrency transactional consistency, double-entry inventory auditability, strict financial controls, and seamless bilingual support (Persian RTL & English LTR).

---

## 📑 Table of Contents

- [Executive Summary](#-executive-summary)
- [System Architecture](#-system-architecture)
- [Key Enterprise Features](#-key-enterprise-features)
- [Role-Based Access Control (RBAC)](#-role-based-access-control-rbac)
- [Technology Stack](#-technology-stack)
- [Repository Structure](#-repository-structure)
- [Getting Started & Local Setup](#-getting-started--local-setup)
  - [Prerequisites](#prerequisites)
  - [Backend Setup (Django)](#backend-setup-django)
  - [Frontend Setup (React + Vite)](#frontend-setup-react--vite)
  - [One-Click Launcher (Windows)](#one-click-launcher-windows)
- [Configuration & Environment Variables](#-configuration--environment-variables)
- [Testing & Quality Assurance](#-testing--quality-assurance)
  - [Backend Test Suite (Pytest)](#backend-test-suite-pytest)
  - [Frontend Test Suite (Node Test Runner)](#frontend-test-suite-node-test-runner)
- [API Documentation & Swagger](#-api-documentation--swagger)
- [Database Schema & ERD](#-database-schema--erd)
- [Security Hardening & Best Practices](#-security-hardening--best-practices)
- [Documentation Directory](#-documentation-directory)
- [License](#-license)

---

## 🌟 Executive Summary

Retail and wholesale tire operations involve complex logistical and financial challenges: fluctuating purchase costs, bulk stock inflows, multi-line sales with workshop labor, warranty returns, and card-present POS settlements.

This platform replaces fragmented, error-prone manual spreadsheets with an audited, high-throughput management system:
- **Zero Inventory Drift**: Physical stock is derived from an immutable double-entry ledger (`StockMovement`) rather than untracked scalar counters.
- **Race Condition & Deadlock Immunity**: Critical sales confirmation and inventory deduction flows use deterministic pessimistic row-level locking (`select_for_update`) to prevent overselling under concurrent load.
- **Strict Financial Safeguards**: Overpayment rejections, automated cash receipt voucher issuance, and real-time ledger reconciliation.
- **Localized Experience**: Native support for Iranian vehicle license plates, Persian/Arabic digit normalization, Jalali calendar dates, and dynamic RTL/LTR switching.

---

## 🏛 System Architecture

The application adopts a **Clean Architecture / Service Layer pattern**, isolating business invariants from HTTP controllers and serialization logic:

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

For an in-depth architectural breakdown, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 🚀 Key Enterprise Features

### 1. Catalog & Double-Entry Stock Ledger
- Categorization across manufacturer **Brands**, standardized **Sizes** (e.g., `185/65R14`, `205/55R16`), and tread patterns.
- Every inventory modification produces an auditable `StockMovement` entry (`INITIAL`, `PURCHASE`, `SALE`, `SALE_RETURN`, `SALE_CANCEL`, `PURCHASE_CANCEL`, `MANUAL_ADJUSTMENT`).
- Low-stock threshold alerts (`min_stock_alert`) highlighted automatically across dashboards.

### 2. Sequential Invoicing & POS Sales Workflow
- Annual gapless invoice numbering format (`INV-YYYY-XXXXXX`) powered by row-locked counters.
- Multi-line support combining physical tires and workshop mechanical services (mounting, balancing, tire repair).
- Draft vs. Confirmed states: draft invoices hold provisional costs, while confirmation locks catalog items and snapshots historical purchase costs at the moment of stock-out.
- Automatic creation of cash `ReceiptVoucher` records when a sale is confirmed with `payment_status=PAID`.

### 3. Purchasing & Supplier Management
- Inflow management linking purchases to registered suppliers.
- Cost-basis tracking: purchase invoices record acquisition prices that inform weighted historical margins.
- Protected cancellation: purchase invoices can only be cancelled if on-hand stock is sufficient to deduct, preventing negative inventory states.

### 4. Treasury & Double-Entry Financial Vouchers
- Three dedicated voucher instruments: `ReceiptVoucher`, `PaymentVoucher`, and `CustomerRefundVoucher`.
- Preservation of POS bank trace codes via `reference_number`.
- Enforced overpayment protection: receipt amounts exceeding remaining invoice balances are strictly rejected at both service and API levels.
- Full voucher cancellation lifecycle with mandatory audit reason logging.

### 5. Iranian Vehicle & Plate Management
- Vehicle registry tracking Iranian license plate schemas (e.g. `12ب345-ایران11`).
- Custom SVG/CSS badge component rendering authentic national plates with the flag of Iran and regional code identifiers.
- Automatic normalization of Persian/Arabic digits (`۱۲۳` -> `123`) before validation.

### 6. Executive BI & Reporting
- Real-time dashboard KPI metrics: Monthly gross revenue, net profit margins, outstanding customer receivables, and inventory valuations.
- Comprehensive date-range sales analytics and brand profitability breakdowns.
- Automated reconciliation commands: `python manage.py reconcile_stock` and `python manage.py reconcile_payments`.

---

## 🛡 Role-Based Access Control (RBAC)

The system enforces least-privilege access across four distinct roles:

| Module / Operation | Manager (`MANAGER`) | Accountant (`ACCOUNTANT`) | Warehouse (`WAREHOUSE`) | Technician (`TECHNICIAN`) |
|:---|:---:|:---:|:---:|:---:|
| **Create Sales Invoices** | ✅ | ❌ | ❌ | ✅ |
| **View Sales Invoices** | All Invoices | All Invoices | All (Read-Only) | **Own Invoices Only (BOLA)** |
| **Confirm Draft Invoices** | ✅ | ❌ | ❌ | ✅ |
| **Cancel Sales Invoices** | ✅ | ❌ | ❌ | ❌ |
| **View Unit Purchase Costs** | ✅ | ✅ | ❌ (Masked) | ❌ (Masked) |
| **Create Purchase Invoices** | ✅ | ❌ | ✅ | ❌ (403 Forbidden) |
| **Cancel Purchase Invoices** | ✅ | ❌ | ❌ | ❌ |
| **Stock Movement Ledger** | ✅ | ✅ | ✅ (Masked Costs) | ❌ (403 Forbidden) |
| **Issue Receipt / Payment Vouchers** | ✅ | ✅ | ❌ | ❌ |
| **Issue Customer Refunds** | ✅ | ❌ | ❌ | ❌ |
| **Financial & Profitability Reports** | ✅ | ✅ | ❌ | ❌ |
| **User & Role Administration** | ✅ | ❌ | ❌ | ❌ |

---

## 💻 Technology Stack

### Backend
- **Core**: Python 3.12–3.14, Django 5.x / 6.x
- **API**: Django REST Framework (DRF) 3.15+
- **Authentication**: `djangorestframework-simplejwt` with token rotation and blacklist
- **Database**: PostgreSQL 16+ (production), SQLite 3 (development)
- **API Documentation**: OpenAPI 3.0 via `drf-spectacular`
- **Testing**: `pytest`, `pytest-django`, `pytest-cov`

### Frontend
- **Framework**: React 19, TypeScript 5.x
- **Build Tool**: Vite 6
- **Styling**: Tailwind CSS 3.4, PostCSS, Autoprefixer
- **Routing**: React Router 7
- **HTTP Client**: Axios with custom error-parsing interceptors
- **Icons**: Lucide React
- **Data Visualization**: Recharts 3.x
- **Testing**: Node.js Native Test Runner (`node --test`)

---

## 📁 Repository Structure

```text
Tire-Shop-Management/
│
├── backend/                       # Django REST Framework backend
│   ├── apps/
│   │   ├── accounts/              # Users, RBAC permissions, and JWT auth
│   │   ├── catalog/               # Tires, brands, sizes, and stock movements
│   │   ├── customers/             # Customers, vehicles, and plate normalization
│   │   ├── services_app/          # Mechanical workshop service definitions
│   │   ├── suppliers/             # Vendor and supplier management
│   │   ├── invoices/              # Sales/purchase invoices, returns, numbering
│   │   ├── finance/               # Receipt, payment, and refund vouchers
│   │   └── reports/               # Executive KPI dashboard and reporting
│   ├── config/                    # Django project settings, URLs, and ASGI/WSGI
│   ├── utils/                     # Persian normalization, Jalali dates, exceptions
│   ├── requirements.txt           # Production dependencies
│   ├── requirements-dev.txt       # Testing and development dependencies
│   ├── manage.py                  # Django CLI entrypoint
│   └── pytest.ini                 # Pytest test runner configuration
│
├── frontend/                      # React 19 + TypeScript + Vite SPA
│   ├── src/
│   │   ├── api/                   # Axios API service clients
│   │   ├── components/            # Reusable UI widgets, modals, plate badge
│   │   │   ├── auth/              # Profile and password change dialogs
│   │   │   ├── catalog/           # Stock adjustment modals
│   │   │   ├── finance/           # Receipt and voucher cancellation modals
│   │   │   ├── invoices/          # Invoice detail and return modals
│   │   │   ├── layout/            # MainLayout, Navbar, Sidebar, RoleGuard
│   │   │   └── plates/            # Iranian license plate component
│   │   ├── context/               # AuthContext and LanguageContext (i18n)
│   │   ├── pages/                 # Full-page views (Dashboard, Sales, Catalog...)
│   │   ├── types/                 # TypeScript interfaces and domain schemas
│   │   └── utils/                 # Formatters, plate parser, error extractor
│   ├── tests/                     # Frontend unit and component tests
│   ├── package.json               # Node packages and scripts
│   ├── tailwind.config.js         # Tailwind theme configuration
│   └── vite.config.ts             # Vite bundler configuration
│
├── docs/                          # Comprehensive technical documentation
│   ├── ARCHITECTURE.md            # System architecture, concurrency, and security
│   ├── DATABASE_DESIGN.md         # Schema design, relational models, constraints
│   ├── API_REFERENCE.md           # REST API endpoints, schemas, error formats
│   └── DEPLOYMENT_GUIDE.md        # Nginx, Gunicorn, PostgreSQL, production guide
│
├── ERD-Diagram.png                # Visual Entity-Relationship Diagram (ERD)
├── ERD-Diagram.svg                # Vector ERD diagram
├── ERD-Viewer.html                # Interactive browser-based ERD viewer
├── start_project.bat              # One-click Windows development launcher
├── .gitignore                     # Git ignore rules (secrets, cache, databases)
├── LICENSE                        # MIT License
└── README.md                      # Primary project overview
```

---

## 🛠 Getting Started & Local Setup

### Prerequisites
- **Python**: Version 3.12 or newer
- **Node.js**: Version 20.x or newer (with `npm`)
- **Git**: Installed and configured

---

### Backend Setup (Django)

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Configure environment settings**:
   Copy the example environment file to `.env`:
   ```bash
   cp .env.example .env
   ```
   *(By default, SQLite is pre-configured for instant zero-configuration local development).*

5. **Apply database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Seed demo data (Optional)**:
   To populate the system with standard brands, tire sizes, initial stock, and sample accounts:
   ```bash
   python manage.py seed_tire_shop
   ```
   *Default seed credentials (development only):*
   - Manager: `admin` / `admin123`
   - Technician: `technician` / `tech123`
   - Warehouse: `warehouse` / `warehouse123`

7. **Start the backend development server**:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```
   The backend API will be available at `http://127.0.0.1:8000/api/v1/`.

---

### Frontend Setup (React + Vite)

1. **Open a new terminal and navigate to `frontend/`**:
   ```bash
   cd frontend
   ```

2. **Install JavaScript dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   The frontend application will start at `http://localhost:5173/`.

---

### One-Click Launcher (Windows)

For rapid development on Windows machines, double-click the root batch script:
```cmd
start_project.bat
```
This automatically boots both Django and Vite servers in separate terminal sessions.

---

## ⚙️ Configuration & Environment Variables

All configuration is managed securely via environment variables. See [`.env.example`](backend/.env.example) for the complete template.

| Variable | Default (Dev) | Production Requirement | Purpose |
|:---|:---:|:---:|:---|
| `DJANGO_SECRET_KEY` | *dev-key* | **Mandatory** (50-char random) | Cryptographic signature key |
| `DJANGO_DEBUG` | `True` | **Must be `False`** | Disables stacktrace leaks |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Your domain name(s) | Host header injection defense |
| `DB_ENGINE` | `sqlite` | `postgres` | Database backend engine |
| `DB_NAME` | `tire_shop_db` | Production DB name | Database schema name |
| `DB_USER` | `postgres` | Dedicated DB user | Database connection user |
| `DB_PASSWORD` | *(empty)* | **Strong password** | Database authentication |
| `DB_HOST` | `127.0.0.1` | DB server address | Database host |
| `DB_PORT` | `5432` | `5432` | Database TCP port |
| `CORS_ALLOWED_ORIGINS` | `localhost:5173...` | Frontend production URL | Cross-Origin resource sharing |
| `REDIS_CACHE_URL` | *(empty)* | `redis://127.0.0.1:6379/1` | Shared rate limit cache |
| `NUM_PROXIES` | `0` | `1` (behind Nginx) | Reverse proxy IP resolution |

---

## 🧪 Testing & Quality Assurance

The codebase maintains rigorous automated test coverage across both backend and frontend layers.

### Backend Test Suite (Pytest)
Run the full backend test suite containing **323 unit, integration, and concurrency tests**:
```bash
# From the repository root:
python -m pytest -c backend/pytest.ini

# Or from inside backend/:
cd backend
python -m pytest -v
```

Test coverage spans:
- **RBAC & Authorization**: Strict role isolation across all endpoints.
- **Financial Integrity**: Multi-step payment lifecycles, overpayment safeguards, and remaining debt calculation.
- **Stock Movement Ledger**: Invariant verification for all 7 stock transaction types.
- **Concurrency & Locking**: Multi-threaded race condition tests verifying overselling prevention and sequential invoice number gaplessness.
- **Security**: Token rotation, blacklist verification, and immediate token invalidation on password change.

### Frontend Test Suite (Node Test Runner)
Run the **55 automated frontend unit and component tests**:
```bash
cd frontend
npm test
```

Verify production TypeScript compilation:
```bash
cd frontend
npm run build
```

---

## 📖 API Documentation & Swagger

Interactive API documentation is generated via `drf-spectacular` adhering to the **OpenAPI 3.0** specification:

- **Swagger UI**: `http://127.0.0.1:8000/api/schema/swagger-ui/`
- **Redoc**: `http://127.0.0.1:8000/api/schema/redoc/`
- **Raw OpenAPI Schema (YAML)**: `http://127.0.0.1:8000/api/schema/`

*(In production environments with `DJANGO_DEBUG=False`, documentation endpoints are restricted strictly to authorized managers).*

---

## 📊 Database Schema & ERD

The complete relational schema comprises 18 normalized tables with foreign key delete protection (`on_delete=PROTECT`), conditional uniqueness constraints, and non-negative field checks.

- **Interactive Viewer**: Open [`ERD-Viewer.html`](ERD-Viewer.html) in any modern web browser to interactively inspect entities, fields, and relationships.
- **Mermaid Source**: Available in [`ERD-Diagram.mmd`](ERD-Diagram.mmd).
- **High-Resolution Visuals**: Available as [`ERD-Diagram.png`](ERD-Diagram.png) and [`ERD-Diagram.svg`](ERD-Diagram.svg).
- **Schema Deep-Dive**: See [`docs/DATABASE_DESIGN.md`](docs/DATABASE_DESIGN.md).

---

## 🔒 Security Hardening & Best Practices

1. **Zero Secret Leakage**:
   - Production secrets, database credentials, and `.env` files are strictly excluded from version control via [`.gitignore`](.gitignore).
   - If `DJANGO_DEBUG=False` is set without an explicit `DJANGO_SECRET_KEY`, Django aborts immediately with an `ImproperlyConfigured` exception.
2. **Password-Bound JWT Token Invalidation**:
   - Password changes embed a hash fingerprint claim in the JWT. Changing a password immediately revokes all outstanding access and refresh tokens across all devices.
3. **Pessimistic Concurrency Control**:
   - Inventory deductions and invoice confirmations acquire row locks on tires in sorted order (`select_for_update().order_by('pk')`), eliminating race conditions and deadlocks.
4. **Defense-in-Depth Throttling**:
   - Throttles requests per IP and per username to eliminate brute-force and credential stuffing threats.
5. **SQL Injection & XSS Protection**:
   - 100% of database queries use Django ORM parameterized statements.
   - Frontend inputs are sanitized, and raw HTML injection is strictly prohibited.

For complete deployment hardening instructions, see [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md).

---

## 📚 Documentation Directory

Detailed engineering documentation is organized inside the [`docs/`](docs/) directory:

- [System Architecture & Concurrency Model](docs/ARCHITECTURE.md)
- [Database Design & Schema Specifications](docs/DATABASE_DESIGN.md)
- [REST API Reference & Endpoints](docs/API_REFERENCE.md)
- [Production Deployment & Hardening Guide](docs/DEPLOYMENT_GUIDE.md)

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).
