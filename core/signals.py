"""
Cache Invalidation Signals
============================
Django signals that automatically invalidate Redis cache entries
when model data changes.

Pattern:
  post_save / post_delete → delete specific cache keys → next request repopulates

All signals are connected in AppConfig.ready() to avoid import loops.

Why signals for cache invalidation (not service layer)?
  - Signals catch ALL writes: admin panel, management commands, shell, migrations.
  - Service layer signals only catch service-mediated writes.
  - Belt-and-suspenders: services also call invalidate_cache() directly.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.cache import make_cache_key, invalidate_cache, invalidate_pattern

logger = logging.getLogger(__name__)


# ─── Billing Signals ──────────────────────────────────────────────────────────

def _invalidate_invoice_cache(instance, **kwargs):
    """Invalidate all invoice-related cache keys for the invoice's user."""
    user_id = str(instance.user_id)
    invalidate_cache(
        make_cache_key('invoice_list', user_id),
        make_cache_key('client_dashboard', user_id),
    )
    logger.debug("Invoice cache invalidated for user %s", user_id)


def connect_billing_signals():
    """
    Connect billing model signals.
    Called from billing.apps.BillingConfig.ready().
    """
    from billing.models import Invoice, Transaction

    post_save.connect(_invalidate_invoice_cache, sender=Invoice)
    post_delete.connect(_invalidate_invoice_cache, sender=Invoice)
    post_save.connect(_invalidate_invoice_cache, sender=Transaction)

    logger.info("Billing cache invalidation signals connected.")


# ─── Hosting Signals ──────────────────────────────────────────────────────────

def _invalidate_hosting_cache(instance, **kwargs):
    """Invalidate hosting account cache keys for the account's user."""
    user_id = str(instance.user_id)
    invalidate_cache(
        make_cache_key('hosting_accounts', user_id),
        make_cache_key('client_dashboard', user_id),
    )
    logger.debug("Hosting account cache invalidated for user %s", user_id)


def _invalidate_package_cache(instance, **kwargs):
    """Invalidate the global package list cache when any package changes."""
    invalidate_cache(make_cache_key('hosting_packages'))
    logger.debug("Hosting packages cache invalidated.")


def connect_hosting_signals():
    """
    Connect hosting model signals.
    Called from hosting.apps.HostingConfig.ready().
    """
    from hosting.models import HostingAccount, HostingPackage

    post_save.connect(_invalidate_hosting_cache, sender=HostingAccount)
    post_delete.connect(_invalidate_hosting_cache, sender=HostingAccount)

    post_save.connect(_invalidate_package_cache, sender=HostingPackage)
    post_delete.connect(_invalidate_package_cache, sender=HostingPackage)

    logger.info("Hosting cache invalidation signals connected.")
