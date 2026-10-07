"""
Domains Models — Registrar, TLD Pricing & Domain Portfolio
===========================================================
Encrypted API credentials at rest via Fernet.
Supports ResellerClub, Namecheap, and wholesale registrars.
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models

from core.encryption import decrypt, encrypt

User = get_user_model()


class RegistrarType(models.TextChoices):
    SPACESHIP = 'spaceship', 'Spaceship.com (Namecheap Cloud)'
    BDWEBS = 'bdwebs', 'BDWebs / WHMCS Domain Reseller'
    RESELLERCLUB = 'resellerclub', 'ResellerClub'
    NAMECHEAP = 'namecheap', 'Namecheap'
    MOCK = 'mock', 'Mock / Sandbox Registrar'


class DomainRegistrar(models.Model):
    """
    Wholesale Domain Registrar provider credentials.
    API keys are symmetrically encrypted at rest via Fernet.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text='Friendly name, e.g. "ResellerClub Production"')
    driver = models.CharField(
        max_length=30,
        choices=RegistrarType.choices,
        default=RegistrarType.MOCK,
        db_index=True
    )
    api_user = models.CharField(max_length=150, help_text='Reseller ID or API User')
    _api_key = models.TextField(
        db_column='api_key',
        help_text='Fernet-encrypted API key / Secret. Use get_api_key().'
    )
    is_sandbox = models.BooleanField(
        default=True,
        help_text='If checked, requests point to the registrar test sandbox.'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, help_text='Default registrar for new orders')
    extra_config = models.JSONField(
        default=dict, blank=True,
        help_text='Additional options (customer_id, client_ip, etc.)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def api_endpoint(self) -> str:
        return self.extra_config.get('api_endpoint', 'https://cp.bdwebs.com/modules/addons/DomainsReseller/api/index.php')

    @api_endpoint.setter
    def api_endpoint(self, value: str):
        if not self.extra_config:
            self.extra_config = {}
        self.extra_config['api_endpoint'] = value

    class Meta:
        verbose_name = 'Domain Registrar'
        verbose_name_plural = 'Domain Registrars'

    def __str__(self) -> str:
        mode = "Sandbox" if self.is_sandbox else "Live"
        return f"{self.name} ({self.get_driver_display()} - {mode})"

    def set_api_key(self, plaintext_key: str) -> None:
        """Encrypt and store the API key."""
        self._api_key = encrypt(plaintext_key)

    def get_api_key(self) -> str:
        """Decrypt and return the API key for runtime API calls."""
        return decrypt(self._api_key)


class TLDPricing(models.Model):
    """
    Top Level Domain (TLD) pricing catalogue (e.g. .com, .net, .com.bd).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tld = models.CharField(max_length=20, unique=True, help_text='e.g. .com, .net, .org, .com.bd')
    registrar = models.ForeignKey(
        DomainRegistrar,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tld_prices',
        help_text='Default registrar for this TLD'
    )
    register_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='1-Year Registration Price in BDT')
    renew_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='1-Year Renewal Price in BDT')
    transfer_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text='Transfer Price in BDT')
    currency = models.CharField(max_length=3, default='BDT')
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'TLD Pricing'
        verbose_name_plural = 'TLD Pricing Catalogue'
        ordering = ['register_price']

    def __str__(self) -> str:
        return f"{self.tld} (৳{self.register_price}/yr)"


class Domain(models.Model):
    """
    Client registered domain portfolio item.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Payment'
        PROCESSING = 'processing', 'Processing Registration'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='domains',
        db_index=True
    )
    domain_name = models.CharField(max_length=255, unique=True, db_index=True)
    registrar = models.ForeignKey(
        DomainRegistrar,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='domains'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    registration_years = models.PositiveSmallIntegerField(default=1)
    registration_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    next_due_date = models.DateField(null=True, blank=True, db_index=True)

    nameserver_1 = models.CharField(max_length=150, default='ns1.hostpro.bd')
    nameserver_2 = models.CharField(max_length=150, default='ns2.hostpro.bd')
    nameserver_3 = models.CharField(max_length=150, blank=True)
    nameserver_4 = models.CharField(max_length=150, blank=True)

    auto_renew = models.BooleanField(default=True)
    epp_code = models.CharField(max_length=100, blank=True, help_text='Domain EPP/Auth transfer code')
    registrar_order_id = models.CharField(max_length=100, blank=True, help_text='Order reference from registrar API')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Client Domain'
        verbose_name_plural = 'Client Domains'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.domain_name} [{self.get_status_display()}]"
