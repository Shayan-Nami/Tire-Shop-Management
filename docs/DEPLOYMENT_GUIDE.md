# Production Deployment & Hardening Guide

## 1. Production Topology & Architecture

For production deployments, the system is designed to run behind a high-performance reverse proxy (e.g. Nginx, Caddy, or Cloudflare) with Gunicorn WSGI workers, PostgreSQL as the primary ACID relational database, and Redis for distributed caching and rate-limiting counters.

```
       [ Client HTTPS Requests ]
                   │
                   ▼
         ┌───────────────────┐
         │       Nginx       │ (SSL / Static Assets / Gzip)
         └─────────┬─────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│ /api, /admin    │ │ / (Frontend SPA)│
│ Proxy to        │ │ Serve static    │
│ Gunicorn:8000   │ │ /var/www/dist   │
└────────┬────────┘ └─────────────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│  PostgreSQL 16  │◄─────►│      Redis      │
│  (ACID MVCC)    │       │ (Throttling)    │
└─────────────────┘       └─────────────────┘
```

---

## 2. Infrastructure Prerequisites

| Component | Minimum Version | Recommended |
|:---|:---|:---|
| **Operating System** | Ubuntu 22.04 LTS / Debian 12 / Windows Server 2022 | Ubuntu 24.04 LTS |
| **Python** | 3.12+ | 3.14 / 3.13 |
| **Node.js** | 20 LTS | 22 LTS |
| **Database** | PostgreSQL 15 | PostgreSQL 16+ |
| **Cache Broker** | Redis 7.0 | Redis 7.2 |
| **Reverse Proxy**| Nginx 1.22+ | Nginx 1.24+ |

---

## 3. Environment Security & Secret Management

Create a production `.env` file in `backend/` owned strictly by the application user (`chmod 600 .env`).

### 3.1 Generating a Cryptographically Secure Secret Key
Never use default or shared keys in production. Generate a random key:
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```

### 3.2 Production `.env` Template
```ini
# Django Core Settings
DJANGO_SECRET_KEY=paste-your-generated-50-character-secret-key-here
DJANGO_DEBUG=False
ALLOWED_HOSTS=tireshop.yourdomain.com,127.0.0.1

# Database Configuration (PostgreSQL)
DB_ENGINE=postgres
DB_NAME=tire_shop_production
DB_USER=tire_admin
DB_PASSWORD=your_strong_postgres_password_here
DB_HOST=127.0.0.1
DB_PORT=5432
CONN_MAX_AGE=60

# Redis Cache for Multi-Worker Rate Limiting
REDIS_CACHE_URL=redis://127.0.0.1:6379/1
NUM_PROXIES=1

# CORS & CSRF Whitelist
CORS_ALLOWED_ORIGINS=https://tireshop.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://tireshop.yourdomain.com

# Production Security & SSL Headers
SECURE_PROXY_SSL_HEADER=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Rate Limiting Thresholds
THROTTLE_ANON_RATE=30/minute
THROTTLE_USER_RATE=300/minute
THROTTLE_LOGIN_IP_RATE=5/minute
THROTTLE_LOGIN_USER_RATE=5/minute
THROTTLE_TOKEN_REFRESH_RATE=15/minute

# JWT Lifetimes
JWT_ACCESS_MINUTES=60
JWT_REFRESH_DAYS=14
```

---

## 4. Step-by-Step Installation

### Step 1: Clone Repository & Create Virtual Environment
```bash
cd /opt
git clone https://github.com/Shayan-Nami/Tire-Shop-Management.git
cd Tire-Shop-Management/backend

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg[binary] gunicorn
```

### Step 2: Database Initialization & Migrations
```bash
# Verify database connection and apply migrations
python manage.py migrate

# Collect static files for Django admin and Swagger UI
python manage.py collectstatic --noinput

# Create the initial system administrator
python manage.py createsuperuser
```

### Step 3: Frontend Production Build
```bash
cd ../frontend
npm ci
npm run build

# Verify dist/ output contains index.html and assets/
ls -la dist/
```

---

## 5. Systemd Service Configuration

### Gunicorn Service (`/etc/systemd/system/tire-shop-backend.service`)
```ini
[Unit]
Description=Tire Shop Management Django Backend
After=network.target postgresql.service redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/Tire-Shop-Management/backend
ExecStart=/opt/Tire-Shop-Management/backend/.venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    --timeout 60 \
    --access-logfile /var/log/tireshop/gunicorn_access.log \
    --error-logfile /var/log/tireshop/gunicorn_error.log \
    config.wsgi:application

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tire-shop-backend
```

---

## 6. Nginx Web Server Configuration

`/etc/nginx/sites-available/tireshop`:
```nginx
server {
    listen 80;
    server_name tireshop.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tireshop.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/tireshop.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tireshop.yourdomain.com/privkey.pem;

    # Frontend Single Page Application
    root /opt/Tire-Shop-Management/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Django Static Files
    location /static/ {
        alias /opt/Tire-Shop-Management/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # API and Admin Reverse Proxy
    location ~ ^/(api|admin)/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }
}
```

---

## 7. Operational Maintenance & Backups

### Automated PostgreSQL Backup (Daily Cron Job)
```bash
# Add to /etc/cron.daily/backup-tireshop-db
#!/bin/bash
BACKUP_DIR="/var/backups/tireshop"
mkdir -p $BACKUP_DIR
DATE=$(date +\%Y\%m\%d_\%H\%M\%S)
pg_dump -U tire_admin tire_shop_production | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"
find $BACKUP_DIR -type f -mtime +14 -delete
```

### Stock & Financial Reconciliation Verification
The system provides built-in management commands to audit data integrity at any time without downtime:
```bash
# Verify ledger balance against tire catalog projections
python manage.py reconcile_stock

# Verify payment vouchers against sales invoices
python manage.py reconcile_payments
```
