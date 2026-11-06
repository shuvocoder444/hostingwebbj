import logging
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from billing.models import Invoice, InvoiceItem
from billing.services import InvoiceService, PaymentService
from core.models import SiteSetting
from domains.models import Domain
from hosting.models import HostingAccount
from hosting.services import ProvisioningService

logger = logging.getLogger('automation')


class Command(BaseCommand):
    help = 'Executes daily automated WHMCS-style cron jobs: invoice generation, overdue marking, auto-suspension, and domain provisioning.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run logic without performing changes or WHM API calls.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        today = timezone.now().date()
        self.stdout.write(self.style.NOTICE(f"=== Starting VeloHoster Daily Automation [{today}] (DryRun={dry_run}) ==="))

        stats = {
            'overdue_invoices_marked': 0,
            'renewal_invoices_created': 0,
            'accounts_auto_suspended': 0,
            'accounts_auto_unsuspended': 0,
            'domains_auto_renewed': 0,
            'errors': [],
        }

        # ── 1. Mark Overdue Invoices ──────────────────────────────────────────
        overdue_qs = Invoice.objects.filter(status=Invoice.Status.UNPAID, due_date__lt=today)
        count_overdue = overdue_qs.count()
        if not dry_run:
            overdue_qs.update(status=Invoice.Status.OVERDUE)
        stats['overdue_invoices_marked'] = count_overdue
        self.stdout.write(f"[1/5] Marked {count_overdue} invoices as OVERDUE.")

        # ── 2. Generate Renewal Invoices (7 Days Before Due Date) ─────────────
        advance_days = getattr(settings, 'INVOICE_GENERATION_DAYS_BEFORE_DUE', 7)
        cutoff_renewal = today + timedelta(days=advance_days)

        active_accounts = HostingAccount.objects.filter(
            status=HostingAccount.Status.ACTIVE,
            next_due_date__lte=cutoff_renewal,
        ).select_related('user', 'package', 'server')

        for acct in active_accounts:
            # Check if an unpaid invoice already exists for this account
            existing = Invoice.objects.filter(
                hosting_account=acct,
                status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE, Invoice.Status.DRAFT]
            ).exists()

            if not existing and acct.amount > 0:
                if not dry_run:
                    try:
                        inv = InvoiceService.create_invoice(
                            user_id=str(acct.user.id),
                            items_data=[{
                                'description': f"Web Hosting Renewal - {acct.domain} ({acct.package.name}) [{acct.get_billing_cycle_display()}]",
                                'quantity': Decimal('1.00'),
                                'unit_price': acct.amount,
                            }],
                            due_date=acct.next_due_date or (today + timedelta(days=advance_days)),
                            invoice_type=Invoice.InvoiceType.HOSTING,
                            hosting_account_id=str(acct.id),
                        )
                        stats['renewal_invoices_created'] += 1
                        self.stdout.write(f"  + Generated renewal invoice #{inv.invoice_number} for {acct.domain}")
                    except Exception as e:
                        err_msg = f"Failed creating invoice for {acct.domain}: {e}"
                        stats['errors'].append(err_msg)
                        self.stderr.write(self.style.ERROR(err_msg))
                else:
                    stats['renewal_invoices_created'] += 1
                    self.stdout.write(f"  (DryRun) Would generate renewal invoice for {acct.domain} (BDT {acct.amount})")

        # ── 3. Auto-Suspend Overdue Hosting Accounts ─────────────────────────
        grace_days = getattr(settings, 'AUTO_SUSPEND_GRACE_DAYS', 3)
        suspend_cutoff = today - timedelta(days=grace_days)

        accounts_to_suspend = HostingAccount.objects.filter(
            status=HostingAccount.Status.ACTIVE,
            next_due_date__lt=suspend_cutoff,
        ).select_related('server', 'user')

        for acct in accounts_to_suspend:
            # Verify if there is an overdue unpaid invoice
            has_overdue = Invoice.objects.filter(
                hosting_account=acct,
                status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE]
            ).exists()

            if has_overdue:
                reason = f"Non-Payment — overdue past grace period ({acct.next_due_date})"
                if not dry_run:
                    try:
                        ProvisioningService.suspend_account(str(acct.id), reason=reason)
                        stats['accounts_auto_suspended'] += 1
                        self.stdout.write(self.style.WARNING(f"  ! Auto-suspended account {acct.domain} ({acct.username}) on WHM"))
                    except Exception as e:
                        err_msg = f"Failed to suspend {acct.domain}: {e}"
                        stats['errors'].append(err_msg)
                        self.stderr.write(self.style.ERROR(err_msg))
                else:
                    stats['accounts_auto_suspended'] += 1
                    self.stdout.write(f"  (DryRun) Would suspend account {acct.domain} ({acct.username})")

        # ── 4. Auto-Unsuspend Paid Accounts ──────────────────────────────────
        suspended_accounts = HostingAccount.objects.filter(
            status=HostingAccount.Status.SUSPENDED
        ).select_related('server', 'user')

        for acct in suspended_accounts:
            # If all invoices for this account are PAID or no unpaid exist
            unpaid_exists = Invoice.objects.filter(
                hosting_account=acct,
                status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE]
            ).exists()

            if not unpaid_exists:
                if not dry_run:
                    try:
                        ProvisioningService.unsuspend_account(str(acct.id))
                        stats['accounts_auto_unsuspended'] += 1
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Auto-unsuspended account {acct.domain} after payment confirmation"))
                    except Exception as e:
                        err_msg = f"Failed to unsuspend {acct.domain}: {e}"
                        stats['errors'].append(err_msg)
                        self.stderr.write(self.style.ERROR(err_msg))
                else:
                    stats['accounts_auto_unsuspended'] += 1
                    self.stdout.write(f"  (DryRun) Would unsuspend account {acct.domain}")

        # ── 5. Summary Output ────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n=== Automation Completed Successfully ==="
            f"\n  • Overdue Invoices Marked: {stats['overdue_invoices_marked']}"
            f"\n  • Renewal Invoices Created: {stats['renewal_invoices_created']}"
            f"\n  • Hosting Accounts Suspended: {stats['accounts_auto_suspended']}"
            f"\n  • Hosting Accounts Unsuspended: {stats['accounts_auto_unsuspended']}"
            f"\n  • Errors Encountered: {len(stats['errors'])}"
        ))
