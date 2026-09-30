"""
HostPro — SQLite Development Settings
========================================
Inherits from production settings and overrides database, cache, and celery
to run locally with zero external dependencies (no PostgreSQL or Redis needed).
"""

from hostpro.settings import *  # noqa: F401, F403

# ─── SQLite DB ────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_dev.sqlite3',
    }
}

DEBUG = True
ALLOWED_HOSTS = ['*']

# ─── LocMemCache (No Redis needed for local dev) ──────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'hostpro-dev-cache',
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ─── Dev Security Overrides ───────────────────────────────────────────────────
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ─── Celery In-Memory Eager Execution ─────────────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Also support session-based auth / standard Django login in DRF / views
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
    'rest_framework.authentication.SessionAuthentication',
    'rest_framework_simplejwt.authentication.JWTAuthentication',
)
