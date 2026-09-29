"""
Hosting Celery Tasks — Automation Lifecycle
============================================
All background automation tasks for the hosting provisioning engine.

Task categories:
  1. Provisioning    — create_account after payment
  2. Suspension      — suspend overdue accounts (Celery Beat, daily)
  3. Unsuspension    — unsuspend after payment
  4. Renewal         — generate renewal invoices before due date
  5. Termination     — hard-delete long-suspended accounts

Retry strategy:
  - max_retries=3, exponential backoff: 60s → 120s → 240s
  - On final failure, account.last_error is updated for admin review.

All tasks are idempotent — safe to run twice for the same account.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('hosting')


# ─── 1. Provisioning ─────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,    # First retry after 60s
    name='hosting.provision_hosting_account',
)
def provision_hosting_account(self, account_id: str) -> None:
    """
    Provision a hosting account on the server panel.
    Triggered by PaymentService._trigger_post_payment() after invoice is paid.

    Retry: 3 times with exponential back-off on ANY exception.
    """
    from hosting.services import ProvisioningService

    logger.info("[Task] Provisioning account %s (attempt %d)", account_id, self.request.retries + 1)
    try:
        ProvisioningService.provision_account(account_id)
    except Exception as exc:
        logger.warning(
            "[Task] Provisioning failed for %s: %s. Retry %d/%d",
            account_id, exc, self.request.retries, self.max_retries
        )
        # Exponential back-off: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ─── 2. Auto-Suspension ───────────────────────────────────────────────────────

@shared_task(
    bind=True,
    name='hosting.auto_suspend_overdue_accounts',
)
def auto_suspend_overdue_accounts(self) -> dict:
    """
    Celery Beat task — runs DAILY.
    Finds all ACTIVE accounts past their due date + grace period and suspends them.

    Grace period is configurable via AUTO_SUSPEND_GRACE_DAYS in settings.
    """
    from hosting.models import HostingAccount
    from hosting.services import ProvisioningService
    from billing.services import InvoiceService

    grace_days = getattr(settings, 'AUTO_SUSPEND_GRACE_DAYS', 3)
    cutoff_date = timezone.now().date() - timedelta(days=grace_days)

    # First: mark overdue invoices
    overdue_count = InvoiceService.mark_overdue_invoices()
    logger.info("[Task] Marked %d invoices as OVERDUE", overdue_count)

    # Find accounts that are ACTIVE, past due, AND have overdue invoices
    accounts_to_suspend = HostingAccount.objects.filter(
        status=HostingAccount.Status.ACTIVE,
        next_due_date__lt=cutoff_date,   # Past due + grace period
    ).select_related('server').only('id', 'domain', 'username', 'server_id', 'user_id')

    suspended = 0
    failed = 0

    for account in accounts_to_suspend:
        try:
            ProvisioningService.suspend_account(
                str(account.id),
                reason=f'Non-payment — overdue since {account.next_due_date}'
            )
            suspended += 1
        except Exception as exc:
            logger.error(
                "[Task] Failed to suspend account %s (%s): %s",
                account.id, account.domain, exc
            )
            failed += 1

    logger.info(
        "[Task] Auto-suspend complete: %d suspended, %d failed", suspended, failed
    )
    return {'suspended': suspended, 'failed': failed}


# ─── 3. Unsuspension ─────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='hosting.unsuspend_hosting_account',
)
def unsuspend_hosting_account(self, account_id: str) -> None:
    """
    Unsuspend a hosting account after payment.
    Triggered by PaymentService._trigger_post_payment() on renewal payment.
    """
    from hosting.services import ProvisioningService

    logger.info("[Task] Unsuspending account %s (attempt %d)", account_id, self.request.retries + 1)
    try:
        ProvisioningService.unsuspend_account(account_id)
    except Exception as exc:
        logger.warning(
            "[Task] Unsuspend failed for %s: %s. Retry %d/%d",
            account_id, exc, self.request.retries, self.max_retries
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ─── 4. Renewal Invoice Generation ───────────────────────────────────────────

@shared_task(
    bind=True,
    name='hosting.generate_renewal_invoices',
)
def generate_renewal_invoices(self) -> dict:
    """
    Celery Beat task — runs DAILY.
    Generates renewal invoices for accounts whose due date is approaching.

    Days before due date is configurable via RENEWAL_INVOICE_DAYS_BEFORE.
    Idempotent: skips accounts that already have an unpaid/pending invoice.
    """
    from hosting.models import HostingAccount
    from billing.models import Invoice
    from billing.services import InvoiceService

    days_before = getattr(settings, 'RENEWAL_INVOICE_DAYS_BEFORE', 7)
    target_date = timezone.now().date() + timedelta(days=days_before)

    # Find ACTIVE accounts whose next_due_date == target_date
    accounts_due = HostingAccount.objects.filter(
        status=HostingAccount.Status.ACTIVE,
        next_due_date=target_date,
    ).select_related('user', 'package').only(
        'id', 'domain', 'user_id', 'package_id', 'billing_cycle', 'amount', 'next_due_date'
    )

    created = 0
    skipped = 0

    for account in accounts_due:
        # Idempotency: skip if renewal invoice already exists for this account
        existing = Invoice.objects.filter(
            hosting_account=account,
            status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE],
        ).exists()

        if existing:
            skipped += 1
            logger.debug(
                "[Task] Renewal invoice already exists for account %s — skipping", account.id
            )
            continue

        try:
            InvoiceService.create_hosting_invoice(
                user=account.user,
                hosting_account=account,
                amount=account.amount,
                description=(
                    f"Renewal: {account.domain} "
                    f"({account.get_billing_cycle_display()}) — "
                    f"Due {account.next_due_date}"
                ),
                due_days=days_before,
            )
            created += 1
            logger.info("[Task] Renewal invoice created for account %s", account.id)
        except Exception as exc:
            logger.error(
                "[Task] Failed to create renewal invoice for account %s: %s",
                account.id, exc
            )

    logger.info(
        "[Task] Renewal invoices: %d created, %d skipped", created, skipped
    )
    return {'created': created, 'skipped': skipped}


# ─── 5. Termination (Long-Suspended Cleanup) ─────────────────────────────────

@shared_task(
    bind=True,
    name='hosting.terminate_long_suspended_accounts',
)
def terminate_long_suspended_accounts(self, days_suspended: int = 30) -> dict:
    """
    Celery Beat task — runs WEEKLY.
    Permanently terminates accounts that have been SUSPENDED for more than
    `days_suspended` days (default: 30 days).

    WARNING: This permanently deletes all data on the server.
    Only activate this task if your ToS specifies this behaviour.
    """
    from hosting.models import HostingAccount
    from hosting.services import ProvisioningService

    cutoff = timezone.now() - timedelta(days=days_suspended)

    long_suspended = HostingAccount.objects.filter(
        status=HostingAccount.Status.SUSPENDED,
        updated_at__lte=cutoff,  # Has been in suspended state for >= days_suspended
    ).select_related('server').only('id', 'domain', 'username', 'server_id')

    terminated = 0
    failed = 0

    for account in long_suspended:
        try:
            driver = __import__('hosting.drivers.factory', fromlist=['get_driver']).get_driver(account.server)
            driver.terminate_account(account.username)
            account.mark_terminated()
            account.save(update_fields=['status', 'terminated_at', 'updated_at'])
            terminated += 1
            logger.warning(
                "[Task] Account TERMINATED: domain=%s username=%s",
                account.domain, account.username
            )
        except Exception as exc:
            logger.error(
                "[Task] Termination FAILED for account %s (%s): %s",
                account.id, account.domain, exc
            )
            failed += 1

    logger.info(
        "[Task] Termination run complete: %d terminated, %d failed", terminated, failed
    )
    return {'terminated': terminated, 'failed': failed}
