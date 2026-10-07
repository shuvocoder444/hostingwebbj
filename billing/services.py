"""
Billing Service Layer
======================
Contains ALL business logic for invoice creation, payment processing,
and the post-payment provisioning trigger.

Design principles:
  - Services are plain Python classes (no model inheritance).
  - All DB writes happen inside atomic transactions to guarantee consistency.
  - Cache is invalidated after every state-changing operation.
  - IPN callbacks funnel through confirm_payment() which is idempotent.
"""
import logging
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings

from .models import Invoice, Transaction, InvoiceItem
from core.cache import make_cache_key, invalidate_cache, TTL_INVOICE_LIST
from core.exceptions import InvoiceAlreadyPaid, BillingError

logger = logging.getLogger('billing')


class InvoiceNumberGenerator:
    """Generates sequential, collision-safe invoice numbers."""

    @staticmethod
    def generate() -> str:
        """
        Generate next invoice number using DB MAX() + 1.
        Atomic to prevent race conditions under concurrent requests.

        Format: INV-00001, INV-00002, ...
        """
        from django.db.models import Max

        with db_transaction.atomic():
            max_num = Invoice.objects.aggregate(Max('invoice_number'))['invoice_number__max']
            if max_num:
                try:
                    next_num = int(max_num.split('-')[1]) + 1
                except (IndexError, ValueError):
                    next_num = 1
            else:
                next_num = 1
            return f'INV-{next_num:05d}'  # Zero-pad to 5 digits: INV-00001


class InvoiceService:
    """Handles invoice creation and lifecycle management."""

    @staticmethod
    @db_transaction.atomic
    def create_hosting_invoice(
        user,
        hosting_account,
        amount: Decimal,
        description: str,
        due_days: int = 7,
    ) -> Invoice:
        """
        Create a hosting invoice for a client.

        Args:
            user:            The client User instance.
            hosting_account: HostingAccount this invoice is for (or None).
            amount:          Total amount in platform currency (BDT).
            description:     Human-readable invoice description.
            due_days:        Days from today until invoice is due.

        Returns:
            The created Invoice instance.
        """
        today = timezone.now().date()
        invoice = Invoice.objects.create(
            invoice_number=InvoiceNumberGenerator.generate(),
            user=user,
            invoice_type=Invoice.InvoiceType.HOSTING,
            hosting_account=hosting_account,
            status=Invoice.Status.UNPAID,
            subtotal=amount,
            total=amount,
            issued_date=today,
            due_date=today + timezone.timedelta(days=due_days),
        )

        InvoiceItem.objects.create(
            invoice=invoice,
            description=description,
            quantity=Decimal('1.00'),
            unit_price=amount,
            line_total=amount,
        )

        logger.info(
            "Invoice %s created for user %s, amount BDT %s",
            invoice.invoice_number, user.email, amount
        )
        # Invalidate the user's cached invoice list
        invalidate_cache(make_cache_key('invoice_list', str(user.id)))
        return invoice

    @staticmethod
    @db_transaction.atomic
    def create_domain_invoice(
        user,
        domain,
        amount: Decimal,
        description: str,
        due_days: int = 7,
    ) -> Invoice:
        """Create an invoice for a domain registration or renewal."""
        today = timezone.now().date()
        invoice = Invoice.objects.create(
            invoice_number=InvoiceNumberGenerator.generate(),
            user=user,
            invoice_type=Invoice.InvoiceType.DOMAIN,
            domain=domain,
            status=Invoice.Status.UNPAID,
            subtotal=amount,
            total=amount,
            issued_date=today,
            due_date=today + timezone.timedelta(days=due_days),
        )

        InvoiceItem.objects.create(
            invoice=invoice,
            description=description,
            quantity=Decimal('1.00'),
            unit_price=amount,
            line_total=amount,
        )

        logger.info("Domain Invoice %s created for %s, BDT %s", invoice.invoice_number, user.email, amount)
        invalidate_cache(make_cache_key('invoice_list', str(user.id)))
        return invoice

    @staticmethod
    def mark_overdue_invoices() -> int:
        """
        Batch-update all unpaid invoices past their due date to OVERDUE.
        Called by a Celery beat task daily.

        Returns:
            Number of invoices updated.
        """
        today = timezone.now().date()
        count = Invoice.objects.filter(
            status=Invoice.Status.UNPAID,
            due_date__lt=today,
        ).update(status=Invoice.Status.OVERDUE)

        if count:
            logger.info("Marked %d invoices as OVERDUE", count)
        return count


class PaymentService:
    """
    Handles payment recording and post-payment automation triggers.
    All gateway IPN callbacks funnel through confirm_payment().
    """

    @staticmethod
    @db_transaction.atomic
    def confirm_payment(
        invoice_id: str,
        gateway: str,
        gateway_transaction_id: str,
        amount: Decimal,
        gateway_response: dict,
    ) -> Transaction:
        """
        Record a confirmed payment and trigger provisioning/unsuspension.

        This method is IDEMPOTENT: calling it twice with the same
        gateway_transaction_id is safe — the second call returns the existing txn.

        Args:
            invoice_id:             UUID of the invoice being paid.
            gateway:                Gateway name (e.g., 'bkash', 'sslcommerz').
            gateway_transaction_id: Transaction ID from the gateway.
            amount:                 Amount received (validated against invoice total).
            gateway_response:       Raw gateway JSON for audit trail.

        Returns:
            The Transaction record.

        Raises:
            InvoiceAlreadyPaid: If invoice already has a successful transaction.
            BillingError:       If amount doesn't match invoice total.
        """
        # ── Idempotency: prevent double-processing of duplicate IPNs ──────
        existing = Transaction.objects.filter(
            gateway_transaction_id=gateway_transaction_id,
            status=Transaction.Status.SUCCESS,
        ).first()
        if existing:
            logger.warning(
                "Duplicate IPN for txn %s — returning existing record", gateway_transaction_id
            )
            return existing

        # ── Load and validate invoice ──────────────────────────────────────
        try:
            # select_for_update prevents concurrent payment of the same invoice
            invoice = Invoice.objects.select_for_update().get(id=invoice_id)
        except Invoice.DoesNotExist:
            raise BillingError(f"Invoice {invoice_id} not found.")

        if invoice.status == Invoice.Status.PAID:
            raise InvoiceAlreadyPaid(
                f"Invoice {invoice.invoice_number} is already paid.",
                detail={'invoice_id': str(invoice_id)}
            )

        if invoice.total != amount:
            logger.warning(
                "Amount mismatch for invoice %s: expected %s, got %s",
                invoice.invoice_number, invoice.total, amount
            )
            raise BillingError(
                f"Payment amount BDT {amount} does not match invoice total BDT {invoice.total}."
            )

        # ── Record the transaction ─────────────────────────────────────────
        txn = Transaction.objects.create(
            invoice=invoice,
            user=invoice.user,
            gateway=gateway,
            status=Transaction.Status.SUCCESS,
            gateway_transaction_id=gateway_transaction_id,
            amount=amount,
            gateway_response=gateway_response,
        )

        # ── Mark invoice as paid ───────────────────────────────────────────
        invoice.mark_paid()
        invoice.save(update_fields=['status', 'paid_at', 'updated_at'])

        logger.info(
            "Invoice %s paid via %s. TxnID: %s",
            invoice.invoice_number, gateway, gateway_transaction_id
        )

        # ── Invalidate user caches ─────────────────────────────────────────
        user_id = str(invoice.user_id)
        invalidate_cache(
            make_cache_key('invoice_list', user_id),
            make_cache_key('client_dashboard', user_id),
        )

        # ── Trigger post-payment automation ───────────────────────────────
        PaymentService._trigger_post_payment(invoice)

        return txn

    @staticmethod
    def _trigger_post_payment(invoice: Invoice) -> None:
        """
        Trigger the appropriate Celery task based on invoice type and account status.
        Called internally after a payment is confirmed.
        """
        if invoice.invoice_type == Invoice.InvoiceType.HOSTING and invoice.hosting_account:
            account = invoice.hosting_account
            if account.status == account.Status.PENDING:
                # First payment → provision the account
                from hosting.tasks import provision_hosting_account
                provision_hosting_account.apply_async(
                    args=[str(account.id)],
                    countdown=5,  # Small delay to let transaction commit
                )
                logger.info("Provisioning task queued for account %s", account.id)

            else:
                # Renewal payment → advance next_due_date based on billing cycle
                cycle = getattr(account, 'billing_cycle', 'monthly')
                days_map = {
                    'monthly': 30,
                    'quarterly': 90,
                    'semi_annual': 180,
                    'annual': 365,
                    'biennial': 730,
                    'triennial': 1095,
                }
                add_days = days_map.get(cycle, 30)
                today = timezone.now().date()
                base_date = account.next_due_date if (account.next_due_date and account.next_due_date >= today) else today
                account.next_due_date = base_date + timezone.timedelta(days=add_days)

                if account.status == account.Status.SUSPENDED:
                    account.status = account.Status.ACTIVE
                    from hosting.tasks import unsuspend_hosting_account
                    unsuspend_hosting_account.apply_async(
                        args=[str(account.id)],
                        countdown=5,
                    )
                    logger.info("Unsuspend task queued for account %s", account.id)

                account.save(update_fields=['next_due_date', 'status'])
                logger.info("Account %s extended to %s (+%d days)", account.domain, account.next_due_date, add_days)

        # ── Domain Post-Payment Trigger ───────────────────────────────────
        if invoice.invoice_type == Invoice.InvoiceType.DOMAIN or invoice.domain:
            if invoice.domain and invoice.domain.status == invoice.domain.Status.PENDING:
                from domains.tasks import register_domain_task
                register_domain_task.apply_async(
                    args=[str(invoice.domain.id)],
                    countdown=5,
                )
                logger.info("Domain registration task queued for domain %s", invoice.domain.id)
