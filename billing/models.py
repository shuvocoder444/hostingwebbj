"""
Billing Models — Invoices, Transactions, Payment Methods
=========================================================
Design principles:
  - Invoice is append-only: once issued, never mutate paid invoices.
  - Transaction records every payment attempt (success AND failure).
  - DecimalField everywhere for money — NEVER float.
  - Composite index on (user, status) for dashboard queries.
  - post_save signals invalidate Redis cache for affected user.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Invoice(models.Model):
    """Represents a billing invoice issued to a client."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UNPAID = 'unpaid', 'Unpaid'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    class InvoiceType(models.TextChoices):
        HOSTING = 'hosting', 'Hosting'
        DOMAIN = 'domain', 'Domain'
        ADDON = 'addon', 'Add-on'
        CREDIT = 'credit', 'Credit'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(
        max_length=20, unique=True, db_index=True,
        help_text='Human-readable invoice number, e.g. INV-00001'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='invoices',
        db_index=True,
    )
    invoice_type = models.CharField(
        max_length=20, choices=InvoiceType.choices, default=InvoiceType.HOSTING
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
        db_index=True,
    )

    # ── Related object (nullable: invoice may be standalone) ──────────────
    # GenericForeignKey would work, but explicit FKs are simpler to query
    hosting_account = models.ForeignKey(
        'hosting.HostingAccount',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )
    domain = models.ForeignKey(
        'domains.Domain',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )

    # ── Financials ─────────────────────────────────────────────────────────
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BDT')

    # ── Dates ─────────────────────────────────────────────────────────────
    issued_date = models.DateField(default=timezone.now)
    due_date = models.DateField(db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-issued_date']
        indexes = [
            # Primary dashboard query: user's open invoices sorted by due date
            models.Index(fields=['user', 'status', 'due_date'], name='idx_invoice_user_status_due'),
            # Celery task: find all overdue unpaid invoices
            models.Index(fields=['status', 'due_date'], name='idx_invoice_status_due'),
        ]

    def __str__(self) -> str:
        return f'{self.invoice_number} [{self.status}] BDT {self.total}'

    def mark_paid(self) -> None:
        """Mark invoice as paid and record timestamp. Do not call directly; use PaymentService."""
        self.status = self.Status.PAID
        self.paid_at = timezone.now()

    @property
    def is_overdue(self) -> bool:
        from django.utils.timezone import now
        return self.status == self.Status.UNPAID and self.due_date < now().date()


class InvoiceItem(models.Model):
    """A line item within an invoice."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        # Auto-compute line total
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.description} x{self.quantity} = {self.line_total}'


class Gateway(models.TextChoices):
    WEBKODERS = 'webkoders', 'WebKoders Pay (bKash, Nagad, Rocket, Cards)'
    BKASH = 'bkash', 'bKash'
    NAGAD = 'nagad', 'Nagad'
    ROCKET = 'rocket', 'DBBL Rocket'
    SSLCOMMERZ = 'sslcommerz', 'SSLCommerz'
    CRYPTOMUS = 'cryptomus', 'Cryptomus (Crypto & Global Cards)'
    DIRECT_CRYPTO = 'direct_crypto', 'Direct Crypto (USDT / Binance Pay)'
    MANUAL = 'manual', 'Manual / Bank Transfer'
    CREDIT = 'credit', 'Account Credit'


class Transaction(models.Model):
    """
    Records every payment attempt — success, failure, pending.
    Never deleted; provides full audit trail.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='transactions',
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    gateway = models.CharField(max_length=20, choices=Gateway.choices, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    # ── Gateway reference IDs ─────────────────────────────────────────────
    gateway_transaction_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text='Transaction ID returned by payment gateway (e.g., bKash TrxID)'
    )
    gateway_order_id = models.CharField(
        max_length=255, blank=True,
        help_text='Our order ID sent to the gateway.'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BDT')

    # ── Raw gateway response stored for debugging/dispute resolution ───────
    gateway_response = models.JSONField(
        default=dict, blank=True,
        help_text='Raw JSON response from payment gateway for audit.'
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Txn {self.gateway_transaction_id} [{self.status}] BDT {self.amount}'


class Coupon(models.Model):
    """Promo Code / Discount Voucher model."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage (%)'
        FIXED = 'fixed', 'Fixed Amount (৳)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text='Promo voucher code (e.g., EID50, WELCOME10)'
    )
    discount_type = models.CharField(
        max_length=15, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percentage (e.g. 20.00 for 20%) or Fixed amount in BDT (e.g. 200.00)'
    )
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Minimum cart/subtotal amount required to apply this coupon'
    )
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Optional cap on discount amount for percentage coupons'
    )
    max_uses = models.PositiveIntegerField(
        default=0, help_text='Maximum times this coupon can be used overall (0 for unlimited)'
    )
    used_count = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(
        default=1, help_text='Maximum uses per customer'
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promo Code'
        verbose_name_plural = 'Promo Codes'
        ordering = ['-created_at']

    def __str__(self):
        val_str = f"{self.discount_value}%" if self.discount_type == self.DiscountType.PERCENTAGE else f"৳{self.discount_value}"
        return f"{self.code} ({val_str} Off)"

    def is_valid_for_cart(self, subtotal: Decimal, user=None) -> tuple[bool, str]:
        """Validate if coupon can be applied."""
        now = timezone.now()
        if not self.is_active:
            return False, "This promo code is currently inactive."
        if self.valid_from and now < self.valid_from:
            return False, "This promo code has not started yet."
        if self.valid_until and now > self.valid_until:
            return False, "This promo code has expired."
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, "This promo code has reached its maximum usage limit."
        if Decimal(str(subtotal)) < self.min_order_amount:
            return False, f"Minimum order amount of ৳{self.min_order_amount} required to use this coupon."
        if user and user.is_authenticated:
            user_uses = self.usages.filter(user=user).count()
            if user_uses >= self.max_uses_per_user:
                return False, f"You have already used this coupon code {user_uses} time(s)."
        return True, ""

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """Calculate discount amount based on type and limits."""
        subtotal = Decimal(str(subtotal))
        if self.discount_type == self.DiscountType.PERCENTAGE:
            disc = (subtotal * self.discount_value) / Decimal('100.00')
            if self.max_discount_amount and disc > self.max_discount_amount:
                disc = self.max_discount_amount
        else:
            disc = self.discount_value
        return min(disc, subtotal)


class CouponUsage(models.Model):
    """Audit log of coupon usages."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usages')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupon_usages')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} used {self.coupon.code} (-৳{self.discount_amount})"

