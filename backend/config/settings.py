import os
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured
import dotenv

# مسیر پایه پروژه
BASE_DIR = Path(__file__).resolve().parent.parent

# بارگذاری متغیرهای محیطی از فایل .env در صورت وجود
dotenv.load_dotenv(BASE_DIR / '.env')

# وضعیت DEBUG (پیش‌فرض False در پروداکشن مگر در محیط توسعه صراحتاً فعال شود)
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOW_DEMO_SEED = os.environ.get('ALLOW_DEMO_SEED', 'False').lower() in ('true', '1', 'yes')

# کلید محرمانه با محافظت اکید در برابر استفاده از کلیدهای پیش‌فرض یا خالی در پروداکشن
INSECURE_DEFAULT_SECRET = 'django-insecure-tire-shop-production-secret-key-shayan-nami-2026'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = INSECURE_DEFAULT_SECRET
    else:
        raise ImproperlyConfigured(
            "خطای امنیتی پروداکشن: در حالت DEBUG=False، متغیر محیطی DJANGO_SECRET_KEY باید حتماً با یک کلید امن، یکتا و تصادفی مقداردهی شود."
        )
elif not DEBUG and SECRET_KEY == INSECURE_DEFAULT_SECRET:
    raise ImproperlyConfigured(
        "خطای امنیتی پروداکشن: استفاده از کلید محرمانه پیش‌فرض و هاردکد شده در محیط پروداکشن مجاز نیست. لطفاً متغیر DJANGO_SECRET_KEY را در فایل .env تنظیم و جایگزین کنید."
    )

# کنترل میزبان‌های مجاز از طریق متغیر محیطی
_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

# مدل کاربر سفارشی با سیستم نقش‌ها (RBAC)
AUTH_USER_MODEL = 'accounts.User'

# ==============================================================================
# واحد پولی رسمی سامانه (System Financial Currency Standard)
# تمامی فیلدهای پولی در پایگاه داده از نوع DecimalField بوده و واحد استاندارد «ریال» (IRR) است.
# ==============================================================================
SYSTEM_CURRENCY_CODE = 'IRR'
SYSTEM_CURRENCY_NAME = 'ریال'


# برنامه‌های نصب‌شده
INSTALLED_APPS = [
    # برنامه‌های اصلی جنگو
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # بسته‌های شخص ثالث
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'corsheaders',
    'drf_spectacular',

    # برنامه‌های هسته سامانه (Core Business Apps)
    'apps.accounts.apps.AccountsConfig',
    'apps.customers.apps.CustomersConfig',
    'apps.catalog.apps.CatalogConfig',
    'apps.services_app.apps.ServicesAppConfig',
    'apps.suppliers.apps.SuppliersConfig',
    'apps.invoices.apps.InvoicesConfig',
    'apps.finance.apps.FinanceConfig',
    'apps.reports.apps.ReportsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # در بالاترین نقطه جهت حل CORS برای وب و موبایل
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# پیکربندی هوشمند پایگاه داده (پشتیبانی رسمی از Microsoft SQL Server با fallback به SQLite)
# --- پیکربندی پایگاه داده (پشتیبانی چندگانه از PostgreSQL، Microsoft SQL Server و SQLite پیش‌فرض) ---
DB_ENGINE = os.environ.get('DB_ENGINE', '').strip().lower()
USE_SQL_SERVER = os.environ.get('USE_SQL_SERVER', 'False').lower() in ('true', '1', 'yes')
# کنترل طول عمر اتصالات پایگاه داده (Connection Pooling) جهت بهبود کارایی
CONN_MAX_AGE = int(os.environ.get('CONN_MAX_AGE', '60'))


def _database_bool_env(name, default):
    value = os.environ.get(name, str(default)).strip().lower()
    if value in ('true', '1', 'yes'):
        return True
    if value in ('false', '0', 'no'):
        return False
    raise ImproperlyConfigured(f'{name} must be true/false, yes/no, or 1/0.')


if DB_ENGINE in ('postgres', 'postgresql'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'tire_shop_db'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': CONN_MAX_AGE,
        }
    }
elif USE_SQL_SERVER or DB_ENGINE in ('mssql', 'sqlserver'):
    _db_user = os.environ.get('DB_USER', '').strip()
    _db_trusted_connection = _database_bool_env('DB_TRUSTED_CONNECTION', not bool(_db_user))
    _db_encrypt = 'yes' if _database_bool_env('DB_ENCRYPT', True) else 'no'
    _db_trust_certificate = 'yes' if _database_bool_env('DB_TRUST_SERVER_CERTIFICATE', False) else 'no'
    DATABASES = {
        'default': {
            'ENGINE': 'mssql',
            'NAME': os.environ.get('DB_NAME', 'TireShopDB'),
            'USER': '' if _db_trusted_connection else _db_user,
            'PASSWORD': os.environ.get('DB_PASSWORD', '') if _db_user and not _db_trusted_connection else '',
            'Trusted_Connection': 'yes' if _db_trusted_connection else 'no',
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '1433'),
            'CONN_MAX_AGE': CONN_MAX_AGE,
            'OPTIONS': {
                'driver': os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
                'extra_params': f'Encrypt={_db_encrypt};TrustServerCertificate={_db_trust_certificate};',
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'CONN_MAX_AGE': CONN_MAX_AGE,
        }
    }

# تنظیمات CORS جهت اتصال فرانت‌اند وب و اپلیکیشن موبایل (جلوگیری از ترکیب مخاطره‌آمیز allow all با credentials)
_cors_allowed_env = os.environ.get('CORS_ALLOWED_ORIGINS')
if _cors_allowed_env:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_allowed_env.split(',') if o.strip()]
else:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

# دامنه‌های مجاز و مورد اعتماد CSRF برای درخواست‌های دارای کوکی / Session
_csrf_trusted_env = os.environ.get('CSRF_TRUSTED_ORIGINS')
if _csrf_trusted_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted_env.split(',') if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]

# پیکربندی پروکسی معکوس (مانند Nginx یا Traefik) جهت تشخیص دقیق IP کلاینت در نرخ درخواست‌ها (Throttling)
# پیش‌فرض 0 است (فقط REMOTE_ADDR را می‌خواند تا از دستکاری X-Forwarded-For جعلی جلوگیری شود).
# در محیط پروداکشن پشت Nginx، مقدار متغیر NUM_PROXIES را در .env برابر 1 قرار دهید.
NUM_PROXIES = int(os.environ.get('NUM_PROXIES', '0'))

# پیکربندی کش (استفاده از کش مشترک Redis در پروداکشن برای تجمیع نرخ تراتل بین تمام Workerهای Gunicorn)
REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', '').strip()
if REDIS_CACHE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_CACHE_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'tire-shop-cache',
        }
    }

# تنظیمات Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON_RATE', '30/minute'),
        'user': os.environ.get('THROTTLE_USER_RATE', '300/minute'),
        'login_ip': os.environ.get('THROTTLE_LOGIN_IP_RATE', '5/minute'),
        'login_username': os.environ.get('THROTTLE_LOGIN_USER_RATE', '5/minute'),
        'token_refresh': os.environ.get('THROTTLE_TOKEN_REFRESH_RATE', '15/minute'),
    },
    'NUM_PROXIES': NUM_PROXIES,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': int(os.environ.get('PAGINATION_PAGE_SIZE', '20')),
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
}

# تنظیمات احراز هویت توکن JWT (SimpleJWT) با بلاک‌لیست امن برای توکن‌های چرخش‌یافته
_jwt_access_minutes = int(os.environ.get('JWT_ACCESS_MINUTES', '60'))
_jwt_refresh_days = int(os.environ.get('JWT_REFRESH_DAYS', '14'))

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=_jwt_access_minutes),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=_jwt_refresh_days),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'CHECK_REVOKE_TOKEN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# تنظیمات امنیتی پروداکشن پشت پروکسی معکوس (Reverse Proxy SSL & Cookies)
if os.environ.get('SECURE_PROXY_SSL_HEADER', 'False').lower() in ('true', '1', 'yes'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_PROXY_SSL_HEADER = None

SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 'yes')
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'False').lower() in ('true', '1', 'yes')
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 'yes')
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'False').lower() in ('true', '1', 'yes')
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() in ('true', '1', 'yes')

# مستندات خودکار OpenAPI 3.0 (Swagger UI / Redoc)
SPECTACULAR_SETTINGS = {
    'TITLE': 'سامانه مدیریت فروشگاه لاستیک - API Documentation',
    'DESCRIPTION': 'مستندات تعاملی وب‌سرویس‌های سیستم مدیریت فروشگاه، انبار و خدمات لاستیک برای وب و موبایل',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['apps.accounts.permissions.IsDocManagerOrDebug'],
}

# اعتبارسنجی گذرواژه استاندارد و امن
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# بین‌المللی‌سازی و زمان محلی
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# پیکربندی سیستم لاگینگ جامع (Console & File) جهت مانیتورینگ هشدارها، خطاها و رخدادهای امنیتی
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] [{levelname}] [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file_errors': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'backend_errors.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_security': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'security.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_errors'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'file_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file_security'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file_errors'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
