"""
Frontend Views for HostPro Web Platform
=========================================
Handles:
  - Landing Page (Hero, Features, Live Packages, Domain Search mockup)
  - User Authentication (Login, Register, Logout)
  - Client Dashboard (Services, Invoices, Orders, Profile)
  - Direct Service Ordering & Invoice Payment
"""
import uuid
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.tokens import RefreshToken

from hosting.models import HostingPackage, HostingAccount, BillingCycle
from hosting.services import ProvisioningService
from billing.models import Invoice, Transaction, Gateway
from billing.services import InvoiceService, PaymentService
from accounts.models import ClientProfile

User = get_user_model()
logger = logging.getLogger(__name__)


def landing_page_view(request):
    """
    Public Landing Page.
    Fetches active hosting packages from DB to show real pricing.
    """
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    context = {
        'packages': packages,
        'user': request.user,
    }
    return render(request, 'index.html', context)


def login_view(request):
    """
    User login view.
    Authenticates against email + password.
    Supports session auth and passes JWT tokens.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.GET.get('next') or request.POST.get('next') or '/dashboard/'

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, 'Please provide both email and password.')
            return render(request, 'login.html', {'next': next_url, 'email': email})

        # authenticate uses USERNAME_FIELD which is email
        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account is inactive. Please contact support.')
                return render(request, 'login.html', {'next': next_url, 'email': email})

            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.email}!')

            # Generate JWT for client-side API calls
            refresh = RefreshToken.for_user(user)
            response = redirect(next_url)
            response.set_cookie('access_token', str(refresh.access_token), max_age=3600, httponly=False)
            return response
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
            return render(request, 'login.html', {'next': next_url, 'email': email})

    return render(request, 'login.html', {'next': next_url})


def register_view(request):
    """
    User registration view.
    Creates new Client User + ClientProfile, then auto-logs in.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not email or not password or not first_name:
            messages.error(request, 'First name, email, and password are required.')
            return render(request, 'register.html', request.POST)

        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html', request.POST)

        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'register.html', request.POST)

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists. Please log in.')
            return render(request, 'register.html', request.POST)

        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.CLIENT,
            )
            # Create client profile with default welcome credit
            ClientProfile.objects.create(
                user=user,
                phone=phone,
                company_name=company_name,
                credit_balance=Decimal('100.00'),  # BDT 100 welcome bonus credit
                currency='BDT',
            )

            login(request, user)
            messages.success(request, f'Account created successfully! Welcome to HostPro, {user.first_name}.')
            return redirect('dashboard')

        except Exception as exc:
            logger.error("Registration error: %s", exc)
            messages.error(request, f'Registration failed: {str(exc)}')
            return render(request, 'register.html', request.POST)

    return render(request, 'register.html')


def logout_view(request):
    """Log out user and redirect to home."""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    response = redirect('landing')
    response.delete_cookie('access_token')
    return response


@login_required(login_url='login')
def dashboard_view(request):
    """
    Main Client Dashboard.
    Displays:
      - Overview stats (Active accounts, Invoices, Balance)
      - User's hosting services with live statuses
      - Invoices with quick 'Pay Now' action
      - Available packages catalogue with instant order modal
      - Profile settings
    """
    user = request.user
    profile, _ = ClientProfile.objects.get_or_create(user=user)

    hosting_accounts = (
        HostingAccount.objects
        .filter(user=user)
        .select_related('package', 'server')
        .order_by('-created_at')
    )

    invoices = (
        Invoice.objects
        .filter(user=user)
        .prefetch_related('items', 'transactions')
        .order_by('-issued_date')
    )

    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')

    # Compute key stats
    active_accounts_count = hosting_accounts.filter(status=HostingAccount.Status.ACTIVE).count()
    unpaid_invoices = invoices.filter(status=Invoice.Status.UNPAID)
    unpaid_invoices_count = unpaid_invoices.count()
    total_unpaid_amount = sum(inv.total for inv in unpaid_invoices)

    context = {
        'user': user,
        'profile': profile,
        'hosting_accounts': hosting_accounts,
        'invoices': invoices,
        'packages': packages,
        'active_accounts_count': active_accounts_count,
        'unpaid_invoices_count': unpaid_invoices_count,
        'total_unpaid_amount': total_unpaid_amount,
        'billing_cycles': BillingCycle.choices,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
@require_http_methods(['POST'])
def order_hosting_view(request):
    """
    Places a new hosting order from the dashboard or packages page.
    Creates:
      1. HostingAccount in PENDING state
      2. Invoice in UNPAID state
    """
    user = request.user
    package_id = request.POST.get('package_id')
    domain = request.POST.get('domain', '').strip().lower()
    billing_cycle = request.POST.get('billing_cycle', BillingCycle.MONTHLY)

    if not package_id or not domain:
        messages.error(request, 'Please select a package and provide a valid domain name.')
        return redirect('dashboard')

    # Basic domain sanitize
    if domain.startswith('http://') or domain.startswith('https://'):
        domain = domain.split('://')[1]
    domain = domain.split('/')[0]

    try:
        package = HostingPackage.objects.select_related('server').get(id=package_id, is_active=True)
    except HostingPackage.DoesNotExist:
        messages.error(request, 'Selected hosting package not found.')
        return redirect('dashboard')

    if HostingAccount.objects.filter(domain=domain).exists():
        messages.error(request, f"The domain '{domain}' is already hosted on our platform.")
        return redirect('dashboard')

    try:
        # 1. Create Pending Account
        account = ProvisioningService.create_pending_account(
            user=user,
            package=package,
            domain=domain,
            billing_cycle=billing_cycle,
        )

        # 2. Determine price based on cycle
        if billing_cycle == BillingCycle.ANNUAL and package.annual_price:
            amount = package.annual_price
        else:
            amount = package.monthly_price

        # 3. Create hosting invoice
        invoice = InvoiceService.create_hosting_invoice(
            user=user,
            hosting_account=account,
            amount=amount,
            description=f"{package.name} - {domain} ({billing_cycle.title()} Hosting)",
            due_days=7,
        )

        messages.success(
            request,
            f"Order placed successfully! Hosting account for '{domain}' created. "
            f"Invoice #{invoice.invoice_number} (BDT {invoice.total}) is ready for payment."
        )

    except Exception as exc:
        logger.error("Order error: %s", exc)
        messages.error(request, f"Could not create order: {str(exc)}")

    return redirect('dashboard')


@login_required(login_url='login')
@require_http_methods(['POST'])
def pay_invoice_view(request, invoice_id):
    """
    Process payment for an invoice.
    In development mode, simulates immediate verification (bKash/Nagad/SSLCommerz/Account Credit).
    Triggers post-payment automation (e.g. provisions hosting account).
    """
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)

    if invoice.status == Invoice.Status.PAID:
        messages.info(request, f"Invoice #{invoice.invoice_number} is already paid.")
        return redirect('dashboard')

    gateway = request.POST.get('gateway', 'bkash').lower()
    trx_id = request.POST.get('trx_id') or f"TRX-{uuid.uuid4().hex[:10].upper()}"

    profile = getattr(request.user, 'profile', None)

    # If paying via account credit, check balance
    if gateway == 'credit':
        if not profile or profile.credit_balance < invoice.total:
            messages.error(request, "Insufficient account credit balance. Please choose another payment method.")
            return redirect('dashboard')
        # Deduct credit
        profile.credit_balance -= invoice.total
        profile.save(update_fields=['credit_balance'])

    try:
        # Confirm payment via PaymentService (handles idempotency, invoice status, Celery trigger)
        txn = PaymentService.confirm_payment(
            invoice_id=str(invoice.id),
            gateway=gateway,
            gateway_transaction_id=trx_id,
            amount=invoice.total,
            gateway_response={'status': 'SUCCESS', 'gateway': gateway, 'channel': 'web_portal'},
        )

        # In dev mode, if account is pending, activate it directly so user sees instant result
        if invoice.hosting_account and invoice.hosting_account.status == HostingAccount.Status.PENDING:
            acct = invoice.hosting_account
            acct.status = HostingAccount.Status.ACTIVE
            acct.provisioned_at = timezone.now()
            acct.save(update_fields=['status', 'provisioned_at'])

        messages.success(
            request,
            f"Payment of BDT {invoice.total} received via {gateway.upper()}! "
            f"Invoice #{invoice.invoice_number} is now PAID and your service is ACTIVE."
        )

    except Exception as exc:
        logger.error("Payment confirmation failed: %s", exc)
        messages.error(request, f"Payment failed: {str(exc)}")

    return redirect('dashboard')
