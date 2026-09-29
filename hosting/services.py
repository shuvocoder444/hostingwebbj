"""
Hosting Service Layer
======================
All provisioning business logic lives here.
Views and Celery tasks call services — never touch drivers directly.

Service layer responsibilities:
  - Select the correct server for new accounts (load balancing).
  - Generate unique, valid cPanel usernames.
  - Compute next_due_date from billing cycle.
  - Coordinate driver calls with DB state transitions (atomically).
  - Update cache after state changes.
"""
import logging
import random
import string
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from core.cache import make_cache_key, invalidate_cache, TTL_CLIENT_DASHBOARD
from core.exceptions import ProvisioningError, SuspensionError

from .models import HostingAccount, HostingPackage, Server, BillingCycle
from .drivers.factory import get_driver

logger = logging.getLogger('hosting')

# Maps billing cycle to number of months (for due date calculation)
CYCLE_MONTHS: dict[str, int] = {
    BillingCycle.MONTHLY: 1,
    BillingCycle.QUARTERLY: 3,
    BillingCycle.SEMI_ANNUAL: 6,
    BillingCycle.ANNUAL: 12,
}


def _compute_next_due_date(cycle: str, from_date: date = None) -> date:
    """
    Compute the next billing due date based on the billing cycle.

    Args:
        cycle:     BillingCycle choice string ('monthly', 'annual', etc.)
        from_date: Starting date (defaults to today).

    Returns:
        date object for the next due date.
    """
    from_date = from_date or timezone.now().date()
    months = CYCLE_MONTHS.get(cycle, 1)
    # Add months properly (handles month-end edge cases)
    month = from_date.month - 1 + months
    year = from_date.year + month // 12
    month = month % 12 + 1
    day = min(from_date.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30,
                               31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _generate_cpanel_username(domain: str) -> str:
    """
    Generate a valid cPanel username (max 16 chars, alphanumeric, starts with letter).

    Strategy: Take up to 8 chars from domain label + 4-char random suffix.
    This is collision-resistant for typical hosting deployments.

    Args:
        domain: The primary domain (e.g., 'example.com').

    Returns:
        A unique username candidate (uniqueness verified by caller).
    """
    # Extract domain label (before first dot), strip non-alphanumeric
    label = domain.split('.')[0]
    label = ''.join(c for c in label.lower() if c.isalnum())[:8]
    if not label or not label[0].isalpha():
        label = 'u' + label  # Ensure starts with letter

    # 4-char random alphanumeric suffix for uniqueness
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return (label + suffix)[:16]


def _get_username_unique(domain: str) -> str:
    """Generate a username guaranteed to not exist in the DB."""
    for _ in range(10):  # Max 10 attempts before giving up
        candidate = _generate_cpanel_username(domain)
        if not HostingAccount.objects.filter(username=candidate).exists():
            return candidate
    raise ProvisioningError(
        f"Could not generate a unique username for domain '{domain}' after 10 attempts."
    )


def _select_server(package: HostingPackage) -> Server:
    """
    Select the best server for a new account.

    Strategy: least-loaded active server that hosts the given package.
    'Least loaded' = server with fewest ACTIVE accounts below max_accounts limit.
    """
    # Count active accounts per server hosting this package's server
    server = package.server
    if not server.is_active:
        raise ProvisioningError(
            f"Server '{server.name}' for package '{package.name}' is not active."
        )

    active_count = HostingAccount.objects.filter(
        server=server,
        status=HostingAccount.Status.ACTIVE,
    ).count()

    if active_count >= server.max_accounts:
        raise ProvisioningError(
            f"Server '{server.name}' is at capacity ({active_count}/{server.max_accounts} accounts)."
        )

    return server


class ProvisioningService:
    """
    Handles the full lifecycle of hosting account provisioning.
    """

    @staticmethod
    @db_transaction.atomic
    def create_pending_account(
        user,
        package: HostingPackage,
        domain: str,
        billing_cycle: str = BillingCycle.MONTHLY,
        password: str = None,
    ) -> HostingAccount:
        """
        Create a PENDING HostingAccount record in the DB.
        Does NOT provision on the server — that happens after payment via Celery.

        Args:
            user:          Client User instance.
            package:       HostingPackage the client ordered.
            domain:        Primary domain for the account.
            billing_cycle: Billing frequency (monthly/quarterly/annual).
            password:      cPanel password (generated if not provided).

        Returns:
            The newly created HostingAccount in PENDING status.
        """
        import secrets
        server = _select_server(package)
        username = _get_username_unique(domain)
        password = password or secrets.token_urlsafe(16)

        # Determine price from cycle
        price_map = {
            BillingCycle.MONTHLY: package.monthly_price,
            BillingCycle.QUARTERLY: package.quarterly_price or package.monthly_price * 3,
            BillingCycle.SEMI_ANNUAL: package.semi_annual_price or package.monthly_price * 6,
            BillingCycle.ANNUAL: package.annual_price or package.monthly_price * 12,
        }
        amount = price_map.get(billing_cycle, package.monthly_price)

        account = HostingAccount.objects.create(
            user=user,
            package=package,
            server=server,
            domain=domain,
            username=username,
            billing_cycle=billing_cycle,
            amount=amount,
            status=HostingAccount.Status.PENDING,
        )

        logger.info(
            "Pending hosting account created: domain=%s username=%s package=%s",
            domain, username, package.name
        )
        return account

    @staticmethod
    def provision_account(account_id: str) -> None:
        """
        Actually create the account on the server panel.
        Called by Celery task after payment confirmation.

        This method is idempotent: if the account is already ACTIVE, it's a no-op.

        Args:
            account_id: UUID string of the HostingAccount to provision.

        Raises:
            ProvisioningError: If the server API call fails.
        """
        try:
            # select_related avoids extra queries for package/server
            account = HostingAccount.objects.select_related(
                'package', 'server', 'user', 'user__profile'
            ).get(id=account_id)
        except HostingAccount.DoesNotExist:
            raise ProvisioningError(f"HostingAccount {account_id} not found.")

        # Idempotency: skip if already provisioned
        if account.status == HostingAccount.Status.ACTIVE:
            logger.info("Account %s already ACTIVE — skipping provisioning.", account_id)
            return

        driver = get_driver(account.server)

        import secrets
        password = secrets.token_urlsafe(16)

        try:
            driver.create_account(
                domain=account.domain,
                username=account.username,
                password=password,
                package_name=account.package.panel_package_name,
                email=account.user.email,
            )
        except Exception as exc:
            # Record failure in DB for admin visibility
            account.status = HostingAccount.Status.FAILED
            account.last_error = str(exc)
            account.save(update_fields=['status', 'last_error', 'updated_at'])
            logger.error(
                "Provisioning FAILED for account %s domain=%s: %s",
                account_id, account.domain, exc
            )
            raise  # Re-raise so Celery can retry

        # ── Update DB atomically on success ───────────────────────────────
        with db_transaction.atomic():
            account.mark_active()
            account.next_due_date = _compute_next_due_date(account.billing_cycle)
            account.last_error = ''
            account.save(update_fields=[
                'status', 'provisioned_at', 'next_due_date', 'last_error', 'updated_at'
            ])

        logger.info(
            "Account PROVISIONED: domain=%s username=%s next_due=%s",
            account.domain, account.username, account.next_due_date
        )

        # Invalidate client dashboard cache
        invalidate_cache(
            make_cache_key('client_dashboard', str(account.user_id)),
            make_cache_key('hosting_accounts', str(account.user_id)),
        )

    @staticmethod
    def suspend_account(account_id: str, reason: str = 'Non-payment') -> None:
        """
        Suspend a hosting account on the server and update DB.
        Called by Celery beat task for overdue accounts.
        """
        account = HostingAccount.objects.select_related('server').get(id=account_id)

        if account.status == HostingAccount.Status.SUSPENDED:
            logger.info("Account %s already suspended — skipping.", account_id)
            return

        driver = get_driver(account.server)

        try:
            driver.suspend_account(account.username, reason=reason)
        except Exception as exc:
            account.last_error = str(exc)
            account.save(update_fields=['last_error', 'updated_at'])
            logger.error("Suspend FAILED for account %s: %s", account_id, exc)
            raise

        account.mark_suspended()
        account.save(update_fields=['status', 'updated_at'])
        logger.info("Account SUSPENDED: domain=%s reason=%s", account.domain, reason)

        invalidate_cache(make_cache_key('client_dashboard', str(account.user_id)))

    @staticmethod
    def unsuspend_account(account_id: str) -> None:
        """
        Unsuspend a hosting account. Called after renewal payment confirmation.
        """
        account = HostingAccount.objects.select_related('server').get(id=account_id)

        if account.status == HostingAccount.Status.ACTIVE:
            logger.info("Account %s already ACTIVE — skipping unsuspend.", account_id)
            return

        driver = get_driver(account.server)

        try:
            driver.unsuspend_account(account.username)
        except Exception as exc:
            account.last_error = str(exc)
            account.save(update_fields=['last_error', 'updated_at'])
            logger.error("Unsuspend FAILED for account %s: %s", account_id, exc)
            raise

        with db_transaction.atomic():
            account.status = HostingAccount.Status.ACTIVE
            # Extend the next due date from today
            account.next_due_date = _compute_next_due_date(account.billing_cycle)
            account.last_error = ''
            account.save(update_fields=['status', 'next_due_date', 'last_error', 'updated_at'])

        logger.info("Account UNSUSPENDED: domain=%s next_due=%s", account.domain, account.next_due_date)
        invalidate_cache(make_cache_key('client_dashboard', str(account.user_id)))
