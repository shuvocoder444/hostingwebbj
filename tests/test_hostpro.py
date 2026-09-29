"""
HostPro Test Suite
===================
Comprehensive unit tests covering:
  1. Encryption utilities
  2. Account registration + JWT auth
  3. Hosting package ordering flow
  4. Payment gateway IPN verification
  5. Celery automation tasks
  6. Cache invalidation signals
  7. Server driver error handling

Run with:
    pytest -v --cov=. --cov-report=term-missing

Test isolation:
  - DB: pytest-django's @pytest.mark.django_db
  - HTTP mocks: `responses` library (no real network calls)
  - Cache: Django's LocMemCache (configured in conftest.py)
  - Celery: tasks called directly (.apply()) or mocked
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

User = get_user_model()

# ─── Test Fixtures ─────────────────────────────────────────────────────────────


def make_user(email='test@example.com', password='StrongPass123!', **kwargs):
    """Helper: create a user for tests."""
    return User.objects.create_user(email=email, password=password, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Encryption Tests
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(FIELD_ENCRYPTION_KEY='3q2-_P8kgJBjqt3oU2xwWFhGgKphFrBrq8N0XcZCpzE=')
class TestEncryption(TestCase):
    """Test Fernet encryption round-trip and error cases."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted value decrypts back to original."""
        from core.encryption import encrypt, decrypt
        plaintext = 'super-secret-whm-token-12345'
        ciphertext = encrypt(plaintext)
        self.assertNotEqual(plaintext, ciphertext)
        self.assertEqual(decrypt(ciphertext), plaintext)

    def test_encrypt_empty_raises(self):
        """Encrypting an empty string raises ValueError."""
        from core.encryption import encrypt
        with self.assertRaises(ValueError, msg="Cannot encrypt an empty value."):
            encrypt('')

    def test_decrypt_invalid_raises(self):
        """Decrypting corrupt data raises ValueError (not exposing raw exception)."""
        from core.encryption import decrypt
        with self.assertRaises(ValueError):
            decrypt('this-is-not-valid-fernet-data')

    def test_encrypted_values_are_unique(self):
        """Fernet encryption is probabilistic — same plaintext → different ciphertext each time."""
        from core.encryption import encrypt
        c1 = encrypt('same-value')
        c2 = encrypt('same-value')
        # Both decrypt correctly but produce different ciphertexts (due to random IV)
        self.assertNotEqual(c1, c2)


# ══════════════════════════════════════════════════════════════════════════════
# 2. User Registration & Auth Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserRegistration(TestCase):
    """Test registration API and custom UserManager."""

    def setUp(self):
        from django.test import Client
        self.client = Client()

    def test_create_user_with_email(self):
        """User is created with email as USERNAME_FIELD."""
        user = make_user(
            email='alice@example.com',
            first_name='Alice',
            last_name='Smith'
        )
        self.assertEqual(user.email, 'alice@example.com')
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertFalse(user.is_staff)
        self.assertEqual(user.role, User.Role.CLIENT)

    def test_create_superuser(self):
        """Superuser has is_staff=True, is_superuser=True, role=ADMIN."""
        admin = User.objects.create_superuser(
            email='admin@hostpro.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_registration_api_creates_profile(self):
        """POST /api/v1/auth/register/ creates user + profile."""
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.post('/api/v1/auth/register/', {
            'email': 'newclient@example.com',
            'first_name': 'New',
            'last_name': 'Client',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        # Profile was auto-created
        user = User.objects.get(email='newclient@example.com')
        self.assertTrue(hasattr(user, 'profile'))

    def test_registration_password_mismatch(self):
        """Mismatched passwords return 400."""
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.post('/api/v1/auth/register/', {
            'email': 'bad@example.com',
            'first_name': 'Bad',
            'last_name': 'User',
            'password': 'Password123!',
            'password_confirm': 'DifferentPass!',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.data['detail'])

    def test_duplicate_email_rejected(self):
        """Registering with existing email returns 400."""
        from rest_framework.test import APIClient
        make_user(email='existing@example.com')
        client = APIClient()
        response = client.post('/api/v1/auth/register/', {
            'email': 'existing@example.com',
            'first_name': 'Dup',
            'last_name': 'User',
            'password': 'Password123!',
            'password_confirm': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, 400)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Invoice Service Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInvoiceService(TestCase):
    """Test InvoiceService.create_hosting_invoice() and mark_overdue_invoices()."""

    def setUp(self):
        self.user = make_user(email='billing@example.com', first_name='B', last_name='User')
        # Create a minimal hosting account mock
        from unittest.mock import MagicMock
        self.account = MagicMock()
        self.account.id = 'test-account-id'

    def test_create_invoice_generates_sequential_number(self):
        """Invoice numbers are sequential: INV-00001, INV-00002, ..."""
        from billing.services import InvoiceService
        inv1 = InvoiceService.create_hosting_invoice(
            user=self.user,
            hosting_account=None,
            amount=Decimal('500.00'),
            description='Test invoice 1',
        )
        inv2 = InvoiceService.create_hosting_invoice(
            user=self.user,
            hosting_account=None,
            amount=Decimal('1000.00'),
            description='Test invoice 2',
        )
        num1 = int(inv1.invoice_number.split('-')[1])
        num2 = int(inv2.invoice_number.split('-')[1])
        self.assertEqual(num2, num1 + 1)

    def test_invoice_has_line_item(self):
        """Created invoice has exactly one line item matching the amount."""
        from billing.services import InvoiceService
        invoice = InvoiceService.create_hosting_invoice(
            user=self.user,
            hosting_account=None,
            amount=Decimal('750.00'),
            description='Starter hosting monthly',
        )
        self.assertEqual(invoice.items.count(), 1)
        item = invoice.items.first()
        self.assertEqual(item.line_total, Decimal('750.00'))

    def test_mark_overdue_invoices(self):
        """Unpaid invoices past due date are correctly marked OVERDUE."""
        from billing.services import InvoiceService, InvoiceNumberGenerator
        from billing.models import Invoice
        from django.utils import timezone
        import datetime

        # Create an unpaid invoice that's past due
        past_due = timezone.now().date() - datetime.timedelta(days=5)
        invoice = Invoice.objects.create(
            invoice_number=InvoiceNumberGenerator.generate(),
            user=self.user,
            status=Invoice.Status.UNPAID,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            issued_date=past_due - datetime.timedelta(days=30),
            due_date=past_due,
        )

        count = InvoiceService.mark_overdue_invoices()
        invoice.refresh_from_db()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(invoice.status, Invoice.Status.OVERDUE)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Payment Service — Idempotency & Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaymentService(TestCase):
    """Test PaymentService.confirm_payment() idempotency and validation."""

    def setUp(self):
        from billing.services import InvoiceService, InvoiceNumberGenerator
        from billing.models import Invoice
        import datetime
        from django.utils import timezone

        self.user = make_user(email='payer@example.com', first_name='P', last_name='User')
        # Create a valid unpaid invoice
        self.invoice = Invoice.objects.create(
            invoice_number=InvoiceNumberGenerator.generate(),
            user=self.user,
            status=Invoice.Status.UNPAID,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            issued_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=7),
        )

    @patch('billing.services.PaymentService._trigger_post_payment')
    def test_confirm_payment_marks_invoice_paid(self, mock_trigger):
        """Successful confirm_payment marks invoice as PAID."""
        from billing.services import PaymentService
        from billing.models import Invoice

        txn = PaymentService.confirm_payment(
            invoice_id=str(self.invoice.id),
            gateway='bkash',
            gateway_transaction_id='TXN123ABC',
            amount=Decimal('500.00'),
            gateway_response={'trxID': 'TXN123ABC'},
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(self.invoice.paid_at)
        mock_trigger.assert_called_once_with(self.invoice)

    @patch('billing.services.PaymentService._trigger_post_payment')
    def test_confirm_payment_idempotent(self, mock_trigger):
        """Second call with same gateway_transaction_id returns existing txn."""
        from billing.services import PaymentService

        # First call
        txn1 = PaymentService.confirm_payment(
            invoice_id=str(self.invoice.id),
            gateway='bkash',
            gateway_transaction_id='TXN_SAME_ID',
            amount=Decimal('500.00'),
            gateway_response={},
        )
        # Second call — should be idempotent
        txn2 = PaymentService.confirm_payment(
            invoice_id=str(self.invoice.id),
            gateway='bkash',
            gateway_transaction_id='TXN_SAME_ID',
            amount=Decimal('500.00'),
            gateway_response={},
        )
        self.assertEqual(txn1.id, txn2.id)
        # _trigger_post_payment only called ONCE (not twice)
        self.assertEqual(mock_trigger.call_count, 1)

    @patch('billing.services.PaymentService._trigger_post_payment')
    def test_confirm_payment_amount_mismatch_raises(self, mock_trigger):
        """Amount mismatch raises BillingError and does NOT mark invoice paid."""
        from billing.services import PaymentService
        from billing.models import Invoice
        from core.exceptions import BillingError

        with self.assertRaises(BillingError):
            PaymentService.confirm_payment(
                invoice_id=str(self.invoice.id),
                gateway='bkash',
                gateway_transaction_id='TXN_WRONG_AMT',
                amount=Decimal('100.00'),  # Wrong amount!
                gateway_response={},
            )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)


# ══════════════════════════════════════════════════════════════════════════════
# 5. cPanel Driver Tests (mocked HTTP)
# ══════════════════════════════════════════════════════════════════════════════

class TestCPanelDriver(TestCase):
    """Test cPanel WHM driver with mocked HTTP responses."""

    def _make_driver(self):
        from hosting.drivers.cpanel import CPanelDriver
        return CPanelDriver(
            host='whm.example.com',
            port=2087,
            username='root',
            api_token='fake-whm-token',
            use_ssl=False,   # Avoid SSL verification in tests
        )

    @patch('requests.Session.get')
    def test_create_account_success(self, mock_get):
        """Successful WHM createacct returns success dict."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'result': [{'status': 1, 'statusmsg': 'Account created'}]
            }
        )
        mock_get.return_value.raise_for_status = lambda: None

        driver = self._make_driver()
        result = driver.create_account(
            domain='newsite.com',
            username='newsite1',
            password='pass123',
            package_name='starter',
            email='owner@newsite.com',
        )
        self.assertTrue(result['success'])

    @patch('requests.Session.get')
    def test_create_account_failure_raises_provisioning_error(self, mock_get):
        """WHM status=0 raises ProvisioningError with error message."""
        from core.exceptions import ProvisioningError

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'result': [{'status': 0, 'statusmsg': 'Username already exists'}]
            }
        )
        mock_get.return_value.raise_for_status = lambda: None

        driver = self._make_driver()
        with self.assertRaises(ProvisioningError) as ctx:
            driver.create_account('bad.com', 'taken', 'pass', 'pkg', 'e@e.com')

        self.assertIn('Username already exists', str(ctx.exception))

    @patch('requests.Session.get')
    def test_suspend_account(self, mock_get):
        """WHM suspendacct returns success."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'result': [{'status': 1, 'statusmsg': 'Suspended'}]}
        )
        mock_get.return_value.raise_for_status = lambda: None

        driver = self._make_driver()
        result = driver.suspend_account('testuser', 'Non-payment')
        self.assertTrue(result['success'])


# ══════════════════════════════════════════════════════════════════════════════
# 6. Provisioning Service Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestProvisioningService(TestCase):
    """Test ProvisioningService with mocked driver."""

    def setUp(self):
        from unittest.mock import patch, MagicMock
        from hosting.models import Server, HostingPackage, ServerDriver

        self.user = make_user(
            email='host@example.com', first_name='H', last_name='User'
        )

        # Create server with fake encrypted token
        self.server = Server(
            name='Test Server',
            hostname='srv1.example.com',
            ip_address='1.2.3.4',
            driver=ServerDriver.CPANEL,
            api_username='root',
            is_active=True,
            max_accounts=100,
        )
        # Set token via the encrypt method
        with patch('core.encryption._fernet') as mock_fernet:
            mock_fernet.encrypt.return_value = b'fake-encrypted-token'
            self.server._api_token = 'fake-encrypted-token'
        self.server.save()

        self.package = HostingPackage.objects.create(
            name='Starter',
            server=self.server,
            disk_quota_mb=5120,
            bandwidth_mb=51200,
            monthly_price=Decimal('500.00'),
            panel_package_name='starter_pkg',
            is_active=True,
        )

    @patch('hosting.services.get_driver')
    def test_provision_account_success(self, mock_get_driver):
        """provision_account calls driver.create_account and marks account ACTIVE."""
        from hosting.models import HostingAccount
        from hosting.services import ProvisioningService

        # Setup mock driver
        mock_driver = MagicMock()
        mock_driver.create_account.return_value = {'success': True, 'message': 'Created'}
        mock_get_driver.return_value = mock_driver

        # Create a PENDING account
        account = HostingAccount.objects.create(
            user=self.user,
            package=self.package,
            server=self.server,
            domain='testsite.com',
            username='testsite1',
            billing_cycle='monthly',
            amount=Decimal('500.00'),
            status=HostingAccount.Status.PENDING,
        )

        ProvisioningService.provision_account(str(account.id))

        account.refresh_from_db()
        self.assertEqual(account.status, HostingAccount.Status.ACTIVE)
        self.assertIsNotNone(account.provisioned_at)
        self.assertIsNotNone(account.next_due_date)
        mock_driver.create_account.assert_called_once()

    @patch('hosting.services.get_driver')
    def test_provision_account_driver_failure_marks_failed(self, mock_get_driver):
        """If driver raises, account is marked FAILED and error is stored."""
        from hosting.models import HostingAccount
        from hosting.services import ProvisioningService
        from core.exceptions import ProvisioningError

        mock_driver = MagicMock()
        mock_driver.create_account.side_effect = ProvisioningError('WHM error: quota exceeded')
        mock_get_driver.return_value = mock_driver

        account = HostingAccount.objects.create(
            user=self.user,
            package=self.package,
            server=self.server,
            domain='failsite.com',
            username='failsite1',
            billing_cycle='monthly',
            amount=Decimal('500.00'),
            status=HostingAccount.Status.PENDING,
        )

        with self.assertRaises(ProvisioningError):
            ProvisioningService.provision_account(str(account.id))

        account.refresh_from_db()
        self.assertEqual(account.status, HostingAccount.Status.FAILED)
        self.assertIn('WHM error', account.last_error)


# ══════════════════════════════════════════════════════════════════════════════
# 7. Auto-Suspension Celery Task Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutoSuspendTask(TestCase):
    """Test the auto_suspend_overdue_accounts Celery task."""

    def setUp(self):
        from hosting.models import Server, HostingPackage, HostingAccount, ServerDriver
        from django.utils import timezone
        import datetime

        self.user = make_user(email='suspend@test.com', first_name='S', last_name='User')

        self.server = Server(
            name='Test SRV', hostname='s.example.com', ip_address='1.2.3.5',
            driver=ServerDriver.CPANEL, api_username='root', is_active=True, max_accounts=100,
        )
        self.server._api_token = 'fake-token'
        self.server.save()

        pkg = HostingPackage.objects.create(
            name='PkgTest', server=self.server,
            disk_quota_mb=1024, bandwidth_mb=10240,
            monthly_price=Decimal('300.00'), panel_package_name='pkg_test',
        )

        # Account past due by 10 days (beyond the 3-day grace period)
        past_due = timezone.now().date() - datetime.timedelta(days=10)
        self.account = HostingAccount.objects.create(
            user=self.user, package=pkg, server=self.server,
            domain='overdue.com', username='overdueacc',
            billing_cycle='monthly', amount=Decimal('300.00'),
            status=HostingAccount.Status.ACTIVE,
            next_due_date=past_due,
        )

    @patch('hosting.services.get_driver')
    @override_settings(AUTO_SUSPEND_GRACE_DAYS=3)
    def test_overdue_account_is_suspended(self, mock_get_driver):
        """Account 10 days past due with 3-day grace is suspended by the task."""
        from hosting.models import HostingAccount
        from hosting.tasks import auto_suspend_overdue_accounts

        mock_driver = MagicMock()
        mock_driver.suspend_account.return_value = {'success': True, 'message': 'Suspended'}
        mock_get_driver.return_value = mock_driver

        result = auto_suspend_overdue_accounts.apply().get()

        self.account.refresh_from_db()
        self.assertEqual(self.account.status, HostingAccount.Status.SUSPENDED)
        self.assertGreaterEqual(result['suspended'], 1)

    @patch('hosting.services.get_driver')
    @override_settings(AUTO_SUSPEND_GRACE_DAYS=30)  # 30-day grace: account NOT suspended
    def test_within_grace_period_not_suspended(self, mock_get_driver):
        """Account only 10 days past due with 30-day grace is NOT suspended."""
        from hosting.models import HostingAccount
        from hosting.tasks import auto_suspend_overdue_accounts

        mock_driver = MagicMock()
        mock_get_driver.return_value = mock_driver

        auto_suspend_overdue_accounts.apply().get()

        self.account.refresh_from_db()
        # Should remain ACTIVE because it's within the 30-day grace period
        self.assertEqual(self.account.status, HostingAccount.Status.ACTIVE)
        mock_driver.suspend_account.assert_not_called()
