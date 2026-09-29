"""
Pytest configuration for HostPro test suite.
"""
import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for tests."""
    if not settings.configured:
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'rest_framework',
                'rest_framework_simplejwt',
                'rest_framework_simplejwt.token_blacklist',
                'django_filters',
                'drf_spectacular',
                'django_celery_beat',
                'django_celery_results',
                'core',
                'accounts',
                'billing',
                'hosting',
                'domains',
                'notifications',
            ],
            AUTH_USER_MODEL='accounts.User',
            SECRET_KEY='test-secret-key-not-for-production',
            FIELD_ENCRYPTION_KEY='3q2-_P8kgJBjqt3oU2xwWFhGgKphFrBrq8N0XcZCpzE=',
            # Use in-memory cache for tests (no Redis required)
            CACHES={
                'default': {
                    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                }
            },
            CELERY_TASK_ALWAYS_EAGER=True,       # Run tasks synchronously in tests
            CELERY_TASK_EAGER_PROPAGATES=True,   # Re-raise task exceptions in tests
            REST_FRAMEWORK={
                'DEFAULT_AUTHENTICATION_CLASSES': (
                    'rest_framework_simplejwt.authentication.JWTAuthentication',
                ),
                'DEFAULT_PERMISSION_CLASSES': (
                    'rest_framework.permissions.IsAuthenticated',
                ),
                'EXCEPTION_HANDLER': 'core.exceptions_handler.custom_exception_handler',
            },
            ROOT_URLCONF='hostpro.urls',
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            USE_TZ=True,
            TIME_ZONE='Asia/Dhaka',
            RENEWAL_INVOICE_DAYS_BEFORE=7,
            AUTO_SUSPEND_GRACE_DAYS=3,
            # Dummy gateway settings for tests
            BKASH_APP_KEY='test-key',
            BKASH_APP_SECRET='test-secret',
            BKASH_USERNAME='test-user',
            BKASH_PASSWORD='test-pass',
            SSLCOMMERZ_STORE_ID='test-store',
            SSLCOMMERZ_STORE_PASS='test-pass',
            SSLCOMMERZ_SANDBOX=True,
        )
