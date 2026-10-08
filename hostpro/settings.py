"""
HostPro Production Settings
============================
All secrets loaded from environment via python-decouple.
Never hardcode credentials here.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# ─── Base ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-hostpro-live-key-xyz-77889900112233')

# Use a safe boolean cast that won't fail on system env vars like DEBUG=release
def _safe_bool(val):
    """Cast to bool safely; non-standard values (e.g. 'release') default to False."""
    if isinstance(val, bool):
        return val
    return str(val).lower() in ('true', '1', 'yes')

DEBUG = config('DEBUG', default=False, cast=_safe_bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='host.webkoders.com,195.250.26.201,127.0.0.1,localhost,testserver,*', cast=Csv())

CSRF_TRUSTED_ORIGINS = [
    'https://host.webkoders.com',
    'http://host.webkoders.com',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://195.250.26.201',
    'https://195.250.26.201',
]


# ─── Installed Apps ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',

    # Internal apps
    'core',
    'accounts',
    'billing',
    'hosting',
    'domains',
    'notifications',
]

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',  # High-speed HTTP response compression
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hostpro.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.global_brand_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'hostpro.wsgi.application'

# ─── Database ─────────────────────────────────────────────────────────────────

# ─── Database (SQLite High-Performance Tuned) ──────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
            'init_command': (
                'PRAGMA journal_mode=WAL;'
                'PRAGMA synchronous=NORMAL;'
                'PRAGMA cache_size=-64000;'  # 64MB cache in RAM
                'PRAGMA temp_store=MEMORY;'
                'PRAGMA busy_timeout=30000;'
            ),
        },
    }
}

# ─── Cache Strategy (Redis with Seamless In-Memory Fallback) ─────────────────
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/1')
USE_REDIS = config('USE_REDIS', default=True, cast=_safe_bool)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache' if USE_REDIS else 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': REDIS_URL if USE_REDIS else 'velohoster-fast-cache',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 100, 'retry_on_timeout': True},
            'SOCKET_CONNECT_TIMEOUT': 3,
            'SOCKET_TIMEOUT': 3,
            'IGNORE_EXCEPTIONS': True,  # Fallback gracefully if Redis is momentarily unavailable
        } if USE_REDIS else {},
        'KEY_PREFIX': 'velohoster',
        'TIMEOUT': 600,  # 10 minutes default TTL
    }
}

# Use DB sessions so user login and authentication always works reliably
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# Retry failed tasks 3 times with exponential back-off
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_MAX_RETRIES = 3

# If Redis is disabled (e.g. local development), execute Celery tasks eagerly in-memory
CELERY_TASK_ALWAYS_EAGER = not USE_REDIS
CELERY_TASK_EAGER_PROPAGATES = True

# ─── Authentication ───────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'  # Custom user model in accounts app

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions_handler.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': config('SECRET_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ─── DRF Spectacular (OpenAPI) ────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'HostPro API',
    'DESCRIPTION': 'Web Hosting Automation & Billing Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ─── Password Validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# ─── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'

WHATSAPP_SUPPORT_NUMBER = config('WHATSAPP_SUPPORT_NUMBER', default='8801700000000')
WHATSAPP_DISPLAY_NUMBER = config('WHATSAPP_DISPLAY_NUMBER', default='+880 1700-000000')

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@hostpro.com')

# ─── Encryption ───────────────────────────────────────────────────────────────
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='OGtjeXFEUZevmNXtDSR_SwQb0_W_N38B5yu1uoQ4cBQ=')

# ─── Billing Settings ─────────────────────────────────────────────────────────
RENEWAL_INVOICE_DAYS_BEFORE = config('RENEWAL_INVOICE_DAYS_BEFORE', default=7, cast=int)
AUTO_SUSPEND_GRACE_DAYS = config('AUTO_SUSPEND_GRACE_DAYS', default=3, cast=int)

# ─── Security Headers & Hardening ───────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=_safe_bool)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=_safe_bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=_safe_bool)

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'hostpro': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'billing': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'hosting': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Celery Beat Schedule ────────────────────────────────────────────────────
from hostpro.beat_schedule import CELERY_BEAT_SCHEDULE  # noqa: F401
