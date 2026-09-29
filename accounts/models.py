"""
Accounts Models
================
Custom User model + Client Profile with full audit trail.

Design decisions:
- AbstractBaseUser gives maximum control over auth fields.
- Client profile is 1:1 with User for separation of concerns.
- All monetary fields use DecimalField, never float.
- db_index on frequently filtered fields (email, created_at).
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    """Custom manager that uses email as the unique identifier."""

    def create_user(self, email: str, password: str = None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Platform User.
    Roles: CLIENT (end customer), RESELLER, ADMIN (staff).
    """

    class Role(models.TextChoices):
        CLIENT = 'client', 'Client'
        RESELLER = 'reseller', 'Reseller'
        ADMIN = 'admin', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Can access Django admin
    date_joined = models.DateTimeField(default=timezone.now, db_index=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role', 'is_active']),  # Compound index for filtered lists
        ]

    def __str__(self) -> str:
        return f'{self.get_full_name()} <{self.email}>'

    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_client(self) -> bool:
        return self.role == self.Role.CLIENT

    @property
    def is_reseller(self) -> bool:
        return self.role == self.Role.RESELLER


class ClientProfile(models.Model):
    """
    Extended profile data for CLIENT users.
    Separated from User to keep the auth model lean.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        primary_key=True,
    )
    company_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, default='BD')  # ISO 3166-1 alpha-2
    postal_code = models.CharField(max_length=20, blank=True)

    # Account credit balance (used for manual credits/refunds)
    credit_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Available credit balance in platform currency (BDT).'
    )
    currency = models.CharField(max_length=3, default='BDT')

    class Meta:
        verbose_name = 'Client Profile'

    def __str__(self) -> str:
        return f'Profile of {self.user.email}'
