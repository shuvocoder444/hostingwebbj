"""
Hosting Models — Servers, Packages, Accounts
==============================================
Core data models for the hosting provisioning engine.

Design:
  - Server stores encrypted credentials (never plaintext in DB).
  - HostingPackage is the "product catalogue" item clients purchase.
  - HostingAccount represents a provisioned cPanel/CyberPanel account.

Indexing strategy:
  - Composite index on (status, next_due_date) for Celery suspension queries.
  - ForeignKey to User is indexed by default by Django.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.encryption import encrypt, decrypt

User = get_user_model()


class ServerDriver(models.TextChoices):
    """Supported control panel types for provisioning."""
    CPANEL = 'cpanel', 'cPanel/WHM'
    CYBERPANEL = 'cyberpanel', 'CyberPanel'


class Server(models.Model):
    """
    A physical/virtual hosting server managed by HostPro.

    API credentials are stored encrypted at rest.
    Use the `get_api_token()` method to decrypt at runtime — NEVER read _api_token directly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text='Friendly name, e.g. "SG01-cPanel"')
    hostname = models.CharField(max_length=255, db_index=True)
    ip_address = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=2087)

    driver = models.CharField(
        max_length=20,
        choices=ServerDriver.choices,
        default=ServerDriver.CPANEL,
        db_index=True,
    )

    # ── Encrypted credentials ───────────────────────────────────────────────
    api_username = models.CharField(max_length=100)
    _api_token = models.TextField(
        db_column='api_token',
        help_text='Fernet-encrypted API token/WHM hash. Use get_api_token().'
    )

    max_accounts = models.PositiveIntegerField(
        default=500,
        help_text='Maximum number of hosting accounts on this server.'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    nameserver_1 = models.CharField(max_length=100, blank=True)
    nameserver_2 = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Server'
        verbose_name_plural = 'Servers'

    def __str__(self) -> str:
        return f'{self.name} ({self.hostname})'

    def set_api_token(self, plaintext_token: str) -> None:
        """Encrypt and store the API token. Always use this — never set _api_token directly."""
        self._api_token = encrypt(plaintext_token)

    def get_api_token(self) -> str:
        """Decrypt and return the API token for runtime use in driver calls."""
        return decrypt(self._api_token)


class HostingPackage(models.Model):
    """
    A hosting plan definition (the product catalogue).
    Maps 1:1 to a WHM/CyberPanel package on the server.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    server = models.ForeignKey(
        Server,
        on_delete=models.PROTECT,
        related_name='packages',
        db_index=True,
    )

    # ── Resource limits ────────────────────────────────────────────────────
    disk_quota_mb = models.PositiveIntegerField(help_text='Disk quota in MB. 0 = unlimited.')
    bandwidth_mb = models.PositiveIntegerField(help_text='Monthly bandwidth in MB. 0 = unlimited.')
    max_databases = models.PositiveIntegerField(default=10)
    max_email_accounts = models.PositiveIntegerField(default=20)
    max_subdomains = models.PositiveIntegerField(default=10)
    max_ftp_accounts = models.PositiveIntegerField(default=5)

    # ── Pricing (use DecimalField — NEVER float for money) ─────────────────
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    quarterly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    semi_annual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    setup_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Metadata ──────────────────────────────────────────────────────────
    panel_package_name = models.CharField(
        max_length=100,
        help_text='Exact package name as configured on the server panel.'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hosting Package'
        verbose_name_plural = 'Hosting Packages'
        ordering = ['monthly_price']

    def __str__(self) -> str:
        return f'{self.name} (BDT {self.monthly_price}/mo)'


class BillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly (1 Month)'
    QUARTERLY = 'quarterly', 'Quarterly (3 Months)'
    SEMI_ANNUAL = 'semi_annual', 'Semi-Annual (6 Months)'
    ANNUAL = 'annual', 'Annually (1 Year)'
    BIENNIAL = 'biennial', 'Biennially (2 Years)'
    TRIENNIAL = 'triennial', 'Triennially (3 Years)'


class HostingAccount(models.Model):
    """
    A live provisioned hosting account on a server.
    Created as PENDING after order, transitioned to ACTIVE after provisioning.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Provisioning'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        TERMINATED = 'terminated', 'Terminated'
        FAILED = 'failed', 'Provisioning Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='hosting_accounts',
        db_index=True,
    )
    package = models.ForeignKey(
        HostingPackage,
        on_delete=models.PROTECT,
        related_name='accounts',
    )
    server = models.ForeignKey(
        Server,
        on_delete=models.PROTECT,
        related_name='accounts',
        db_index=True,
    )

    # ── Account identity on server ─────────────────────────────────────────
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    username = models.CharField(
        max_length=16,
        unique=True,
        help_text='cPanel/CyberPanel username (max 16 chars, alphanumeric).'
    )

    # ── Billing ───────────────────────────────────────────────────────────
    billing_cycle = models.CharField(
        max_length=15,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Price paid per billing cycle in platform currency (BDT).'
    )

    # ── Lifecycle dates ───────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True, db_index=True)
    terminated_at = models.DateTimeField(null=True, blank=True)

    # ── Error tracking ─────────────────────────────────────────────────────
    last_error = models.TextField(
        blank=True,
        help_text='Last error message from provisioning/suspension for admin debugging.'
    )

    # ── Password (Encrypted) ──────────────────────────────────────────────
    password_encrypted = models.TextField(
        blank=True,
        default='',
        db_column='password_encrypted',
        help_text='Fernet-encrypted cPanel password. Use get_account_password().'
    )

    class Meta:
        verbose_name = 'Hosting Account'
        verbose_name_plural = 'Hosting Accounts'
        indexes = [
            # Primary index for Celery Beat: find overdue active accounts efficiently
            models.Index(fields=['status', 'next_due_date'], name='idx_account_status_due'),
        ]

    def __str__(self) -> str:
        return f'{self.domain} [{self.status}]'

    def set_account_password(self, plaintext_password: str) -> None:
        """Encrypt and store cPanel password."""
        if plaintext_password:
            self.password_encrypted = encrypt(plaintext_password)
        else:
            self.password_encrypted = ''

    def get_account_password(self) -> str:
        """Decrypt and return cPanel password."""
        if not self.password_encrypted:
            return ''
        try:
            return decrypt(self.password_encrypted)
        except Exception:
            return ''

    def mark_active(self) -> None:
        """Called by provisioning task on success."""
        self.status = self.Status.ACTIVE
        self.provisioned_at = timezone.now()

    def mark_suspended(self) -> None:
        self.status = self.Status.SUSPENDED

    def mark_terminated(self) -> None:
        self.status = self.Status.TERMINATED
        self.terminated_at = timezone.now()

    @property
    def days_until_due(self) -> int:
        if not self.next_due_date:
            return 999
        return (self.next_due_date - timezone.now().date()).days

    @property
    def is_expiring_soon(self) -> bool:
        """Returns True if account expires within 50 days."""
        return self.status == self.Status.ACTIVE and self.days_until_due <= 50

