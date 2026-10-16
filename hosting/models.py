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

from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from core.encryption import decrypt, encrypt

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


class PackageCategory(models.Model):
    """
    Category/Group for hosting packages (e.g., Domain & Hosting Offer, BDIX Hosting, USA Hosting, etc.)
    Allows dynamic tab filtering on homepage and specialized landing pages.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text='Category Title (e.g. Domain & Hosting OFFER, BDIX Hosting)')
    slug = models.SlugField(max_length=100, unique=True, help_text='URL friendly identifier, e.g. bdix-hosting, domain-hosting-offer')
    description = models.TextField(blank=True, help_text='Short description of this hosting category')
    sort_order = models.PositiveIntegerField(default=0, help_text='Display order of tabs (lowest first)')
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Package Category'
        verbose_name_plural = 'Package Categories'
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name


class HostingPackage(models.Model):
    """
    A hosting plan definition (the product catalogue).
    Maps 1:1 to a WHM/CyberPanel package on the server.
    """
    class TargetPage(models.TextChoices):
        ALL = 'all', 'All Pages'
        HOME = 'home', 'Home Page Only'
        BDIX = 'bdix', 'BDIX Hosting Page'
        SINGAPORE = 'singapore', 'Singapore Hosting Page'
        USA = 'usa', 'USA Hosting Page'
        GERMANY = 'germany', 'Germany Hosting Page'
        FINLAND = 'finland', 'Finland Hosting Page'
        TURBO = 'turbo', 'Turbo Cloud Page'
        PREMIUM = 'premium', 'Premium Business Page'
        RESELLER = 'reseller', 'Reseller Hosting Page'
        VPS = 'vps', 'VPS Hosting Page'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    server = models.ForeignKey(
        Server,
        on_delete=models.PROTECT,
        related_name='packages',
        db_index=True,
    )
    category = models.ForeignKey(
        PackageCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='packages',
        db_index=True,
        help_text='Assign package to a tab/category group'
    )
    target_page = models.CharField(
        max_length=30,
        choices=TargetPage.choices,
        default=TargetPage.ALL,
        db_index=True,
        help_text='Choose which dedicated page this package should show on (Legacy fallback)'
    )
    categories = models.ManyToManyField(
        PackageCategory,
        blank=True,
        related_name='multi_packages',
        help_text='Assign package to one or multiple category tabs'
    )
    target_pages = models.JSONField(
        default=list,
        blank=True,
        help_text='List of dedicated pages where this package will be displayed'
    )

    def get_all_categories(self):
        """Return list of categories assigned to this package (M2M with fallback to single category FK)."""
        try:
            cats = list(self.categories.all())
            if cats:
                return cats
        except Exception:
            pass
        if self.category:
            return [self.category]
        return []

    def get_target_pages_list(self) -> list:
        """Return list of target page codes (e.g. ['home', 'bdix', 'usa'])."""
        if self.target_pages and isinstance(self.target_pages, list) and len(self.target_pages) > 0:
            return self.target_pages
        if self.target_page:
            if self.target_page == 'all':
                return ['usa', 'singapore', 'germany', 'finland', 'bdix', 'vps', 'turbo', 'premium', 'reseller']
            return [self.target_page]
        return []

    def shows_on_page(self, page_name: str) -> bool:
        """Determine if package should be displayed on a specific page."""
        p_name = (page_name or '').lower().strip()
        pages = self.get_target_pages_list()
        if p_name in pages or 'all' in pages:
            return True
        for cat in self.get_all_categories():
            if p_name in (cat.slug or '').lower():
                return True
        return False

    # ── Display Badges & Highlight Subtitles ──────────────────────────────
    badge_text = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Discount or promo badge, e.g. "Save 45%", "Most Popular", "Save 35%"'
    )
    subtitle = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text='Offer subtitle, e.g. "10 GB Hosting + Free .com", "Unlimited Hosting + Free .com"'
    )
    features_list = models.TextField(
        blank=True,
        default='',
        help_text='Custom bullet features list (one feature per line). Example:\nFREE Domain 1st Year\n10GB NVMe SSD Disk Space\ncPanel Control Panel\nLife Time Free SSL Certificate'
    )
    sort_order = models.PositiveIntegerField(default=0, help_text='Display ordering within category/page')

    # ── Resource limits ────────────────────────────────────────────────────
    disk_quota_mb = models.PositiveIntegerField(help_text='Disk quota in MB. 0 = unlimited.')
    bandwidth_mb = models.PositiveIntegerField(help_text='Monthly bandwidth in MB. 0 = unlimited.')
    max_databases = models.PositiveIntegerField(default=10)
    max_email_accounts = models.PositiveIntegerField(default=20)
    max_subdomains = models.PositiveIntegerField(default=10)
    max_ftp_accounts = models.PositiveIntegerField(default=5)

    # ── Pricing (use DecimalField — NEVER float for money) ─────────────────
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=Decimal('0.00'))
    quarterly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    semi_annual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Strikethrough old regular price, e.g. 3099.00')
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
        ordering = ['sort_order', 'id']

    def __str__(self) -> str:
        if self.monthly_price and self.monthly_price > 0:
            return f'{self.name} (BDT {self.monthly_price}/mo)'
        elif self.annual_price:
            return f'{self.name} (BDT {self.annual_price}/yr)'
        return self.name

    def get_features(self):
        """Returns list of feature strings parsed from newline-separated features_list."""
        if self.features_list:
            lines = [line.strip() for line in self.features_list.splitlines() if line.strip()]
            if lines:
                return lines
        # Default fallback features if not customized
        disk_str = "Unlimited Pure NVMe SSD" if self.disk_quota_mb == 0 else f"{self.disk_quota_mb} MB NVMe SSD Disk Space"
        bw_str = "Unlimited Bandwidth" if self.bandwidth_mb == 0 else f"{self.bandwidth_mb} MB Monthly Bandwidth"
        return [
            disk_str,
            bw_str,
            f"{self.max_databases} MySQL Database(s) + phpMyAdmin",
            f"{self.max_email_accounts} Professional Email Account(s)",
            "cPanel Control Panel + Softaculous 1-Click",
            "Life Time Free SSL Certificate",
            "Automatic Weekly/Daily Backup",
            "LiteSpeed Enterprise + LSCache",
        ]


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
