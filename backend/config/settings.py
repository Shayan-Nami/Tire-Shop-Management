import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
import dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

if os.environ.get('PYTHON_DOTENV_DISABLED', '').lower() not in ('1', 'true', 'yes'):
    dotenv.load_dotenv(BASE_DIR / '.env')


def _env_bool(name: str, default: bool = False) -> bool:
    default_str = 'True' if default else 'False'
    return os.environ.get(name, default_str).lower() in ('true', '1', 'yes')


DEBUG = _env_bool('DJANGO_DEBUG', False)
TESTING = _env_bool('DJANGO_TESTING', False)
_strict_prod = not DEBUG and not TESTING
ALLOW_DEMO_SEED = _env_bool('ALLOW_DEMO_SEED', False)
ENABLE_DOCS_IN_PROD = _env_bool('ENABLE_DOCS_IN_PROD', False)

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

_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
elif _strict_prod:
    ALLOWED_HOSTS = []
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

AUTH_USER_MODEL = 'accounts.User'

SYSTEM_CURRENCY_CODE = 'IRR'
SYSTEM_CURRENCY_NAME = 'ریال'


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'corsheaders',
    'drf_spectacular',

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
    'corsheaders.middleware.CorsMiddleware',
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

DB_ENGINE = os.environ.get('DB_ENGINE', '').strip().lower()
USE_SQL_SERVER = os.environ.get('USE_SQL_SERVER', 'False').lower() in ('true', '1', 'yes')
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

_cors_allowed_env = os.environ.get('CORS_ALLOWED_ORIGINS')
if _cors_allowed_env:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_allowed_env.split(',') if o.strip()]
elif _strict_prod:
    CORS_ALLOWED_ORIGINS = []
else:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

_csrf_trusted_env = os.environ.get('CSRF_TRUSTED_ORIGINS')
if _csrf_trusted_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted_env.split(',') if o.strip()]
elif _strict_prod:
    CSRF_TRUSTED_ORIGINS = []
else:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]

NUM_PROXIES = int(os.environ.get('NUM_PROXIES', '0'))

REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', '').strip()
if REDIS_CACHE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_CACHE_URL,
        }
    }
elif _strict_prod:
    raise ImproperlyConfigured(
        "خطای امنیتی پروداکشن: در حالت DEBUG=False، متغیر محیطی REDIS_CACHE_URL باید مقداردهی شود."
    )
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'tire-shop-cache',
        }
    }

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': (
        (
            'rest_framework.renderers.JSONRenderer',
            'rest_framework.renderers.BrowsableAPIRenderer',
        )
        if DEBUG
        else ('rest_framework.renderers.JSONRenderer',)
    ),
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

_jwt_access_minutes = int(os.environ.get('JWT_ACCESS_MINUTES', '30'))
if os.environ.get('JWT_REFRESH_HOURS', '').strip():
    _jwt_refresh_hours = int(os.environ['JWT_REFRESH_HOURS'])
elif os.environ.get('JWT_REFRESH_DAYS', '').strip():
    _jwt_refresh_hours = int(os.environ['JWT_REFRESH_DAYS']) * 24
else:
    _jwt_refresh_hours = 12

if os.environ.get('JWT_MAX_SESSION_HOURS', '').strip():
    _jwt_max_session_hours = int(os.environ['JWT_MAX_SESSION_HOURS'])
else:
    _jwt_max_session_hours = _jwt_refresh_hours

_jwt_rotate_refresh_tokens = _env_bool('JWT_ROTATE_REFRESH_TOKENS', True)
JWT_MAX_SESSION_HOURS = _jwt_max_session_hours

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=_jwt_access_minutes),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=_jwt_refresh_hours),
    'ROTATE_REFRESH_TOKENS': _jwt_rotate_refresh_tokens,
    'BLACKLIST_AFTER_ROTATION': True,
    'CHECK_REVOKE_TOKEN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

if _env_bool('SECURE_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_PROXY_SSL_HEADER = None

SESSION_COOKIE_AGE = _jwt_max_session_hours * 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', _strict_prod)
CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', _strict_prod)
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', _strict_prod)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000' if _strict_prod else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', _strict_prod)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', _strict_prod)

SPECTACULAR_SETTINGS = {
    'TITLE': 'سامانه مدیریت فروشگاه لاستیک - API Documentation',
    'DESCRIPTION': 'مستندات تعاملی وب‌سرویس‌های سیستم مدیریت فروشگاه، انبار و خدمات لاستیک برای وب و موبایل',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['apps.accounts.permissions.IsDocManagerOrDebug'],
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'backend_errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'delay': True,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_security': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'security.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'delay': True,
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
