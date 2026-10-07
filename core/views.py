"""
Frontend Views for HostPro Web Platform
=========================================
Handles:
  - Landing Page (Hero, Features, Live Packages, Domain Search mockup)
  - User Authentication (Login, Register, Logout)
  - Client Dashboard (Services, Invoices, Orders, Profile)
  - Direct Service Ordering & Invoice Payment
"""
import logging
import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import ClientProfile
from billing.models import Invoice, Transaction
from billing.services import InvoiceService
from hosting.models import BillingCycle, HostingAccount, HostingPackage
from hosting.services import ProvisioningService

User = get_user_model()
logger = logging.getLogger(__name__)


def landing_page_view(request):
    """
    Public Landing Page.
    Fetches active hosting packages and full TLD pricing from DB.
    """
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    from domains.models import TLDPricing
    tld_prices = TLDPricing.objects.filter(is_active=True).order_by('register_price')
    context = {
        'packages': packages,
        'tld_prices': tld_prices,
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

        # Try authenticating via Django backend
        user = authenticate(request, username=email, password=password)
        if user is None:
            user = authenticate(request, email=email, password=password)
        if user is None:
            # Fallback direct check for custom user model
            try:
                candidate = User.objects.get(email__iexact=email)
                if candidate.check_password(password):
                    user = candidate
            except User.DoesNotExist:
                user = None

        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account is inactive. Please contact support.')
                return render(request, 'login.html', {'next': next_url, 'email': email})

            if not hasattr(user, 'backend') or not user.backend:
                user.backend = 'django.contrib.auth.backends.ModelBackend'

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
            # Create client profile
            ClientProfile.objects.create(
                user=user,
                phone=phone,
                company_name=company_name,
                credit_balance=Decimal('0.00'),
                currency='BDT',
            )

            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome to HostPro, {user.first_name}.')
            return redirect('dashboard')

        except Exception as exc:
            logger.error("Registration error: %s", exc)
            messages.error(request, f'Registration failed: {exc!s}')
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

    from domains.models import Domain, TLDPricing
    client_domains = Domain.objects.filter(user=user).select_related('registrar').order_by('-created_at')
    tld_prices = TLDPricing.objects.filter(is_active=True).order_by('register_price')

    # Compute key stats
    active_accounts_count = hosting_accounts.filter(status=HostingAccount.Status.ACTIVE).count()
    active_domains_count = client_domains.filter(status=Domain.Status.ACTIVE).count()
    unpaid_invoices = invoices.filter(status=Invoice.Status.UNPAID)
    unpaid_invoices_count = unpaid_invoices.count()
    total_unpaid_amount = sum(inv.total for inv in unpaid_invoices)

    # Expiration notice (50 days window)
    today = timezone.now().date()
    expiring_accounts = []
    for acc in hosting_accounts:
        if acc.status == HostingAccount.Status.ACTIVE and acc.next_due_date:
            days_left = (acc.next_due_date - today).days
            if days_left <= 50:
                expiring_accounts.append({
                    'account': acc,
                    'days_left': days_left,
                    'is_expired': days_left <= 0,
                    'is_critical': days_left <= 7,
                })

    expiring_domains = []
    for dom in client_domains:
        if dom.status == Domain.Status.ACTIVE and dom.expiry_date:
            exp_date = dom.expiry_date
            days_left = (exp_date - today).days
            if days_left <= 50:
                expiring_domains.append({
                    'domain': dom,
                    'days_left': days_left,
                    'is_expired': days_left <= 0,
                    'is_critical': days_left <= 7,
                })

    context = {
        'user': user,
        'profile': profile,
        'hosting_accounts': hosting_accounts,
        'client_domains': client_domains,
        'tld_prices': tld_prices,
        'invoices': invoices,
        'packages': packages,
        'active_accounts_count': active_accounts_count,
        'active_domains_count': active_domains_count,
        'unpaid_invoices_count': unpaid_invoices_count,
        'total_unpaid_amount': total_unpaid_amount,
        'billing_cycles': BillingCycle.choices,
        'expiring_accounts': expiring_accounts,
        'expiring_domains': expiring_domains,
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

    existing = HostingAccount.objects.filter(domain=domain).first()
    if existing and existing.status == HostingAccount.Status.ACTIVE:
        messages.error(request, f"The domain '{domain}' is already hosted and active on our platform.")
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
        price_map = {
            BillingCycle.MONTHLY: package.monthly_price,
            BillingCycle.QUARTERLY: package.quarterly_price or package.monthly_price * 3,
            BillingCycle.SEMI_ANNUAL: package.semi_annual_price or package.monthly_price * 6,
            BillingCycle.ANNUAL: package.annual_price or package.monthly_price * 12,
            BillingCycle.BIENNIAL: getattr(package, 'biennial_price', None) or package.monthly_price * 24,
            BillingCycle.TRIENNIAL: getattr(package, 'triennial_price', None) or package.monthly_price * 36,
        }
        amount = price_map.get(billing_cycle, package.monthly_price)

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
            f"Invoice #{invoice.invoice_number} (৳{invoice.total} BDT) is ready for payment. "
            f"Please submit your payment details (bKash/Nagad/Rocket/Bank) below to activate your service."
        )
        return redirect(f"/dashboard/?tab=invoices&pay_invoice={invoice.id}")

    except Exception as exc:
        logger.error("Order error: %s", exc)
        messages.error(request, f"Could not create order: {exc!s}")
        return redirect('dashboard')


@login_required(login_url='login')
@require_http_methods(['POST'])
def pay_invoice_view(request, invoice_id):
    """
    Process manual payment submission for an invoice (bKash/Nagad/Rocket/Bank Transfer/Card).
    Records a PENDING transaction with the customer's TrxID and Sender Phone/Account.
    Does NOT automatically provision domain/hosting — requires Administrator verification and approval.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)

    if invoice.status == Invoice.Status.PAID:
        messages.info(request, f"Invoice #{invoice.invoice_number} is already settled.")
        return redirect('dashboard')

    gateway = request.POST.get('gateway', 'bkash').lower()
    sender_number = request.POST.get('sender_number', '').strip()
    trx_id = request.POST.get('trx_id', '').strip()
    notes = request.POST.get('notes', '').strip()

    profile = getattr(request.user, 'profile', None)

    # If paying via account wallet credit
    if gateway == 'credit':
        if not profile or profile.credit_balance < invoice.total:
            messages.error(request, "Insufficient wallet credit balance. Please submit payment via bKash, Nagad, Rocket or Bank.")
            return redirect('/dashboard/?tab=invoices')
        # Deduct wallet credit & submit for admin instant approval
        profile.credit_balance -= invoice.total
        profile.save(update_fields=['credit_balance'])
        trx_id = f"WALLET-{uuid.uuid4().hex[:8].upper()}"
        sender_number = request.user.email

    if not trx_id and gateway != 'credit':
        messages.error(request, "Transaction ID (TrxID) is required. Please provide your payment TrxID.")
        return redirect('/dashboard/?tab=invoices')

    if not sender_number and gateway != 'credit':
        messages.error(request, "Sender Phone Number or Account Number is required.")
        return redirect('/dashboard/?tab=invoices')

    try:
        # 1. Create or update PENDING Transaction record
        txn, created = Transaction.objects.update_or_create(
            invoice=invoice,
            status=Transaction.Status.PENDING,
            defaults={
                'user': request.user,
                'gateway': gateway,
                'gateway_transaction_id': trx_id,
                'amount': invoice.total,
                'gateway_response': {
                    'sender_number': sender_number,
                    'notes': notes,
                    'gateway': gateway,
                    'channel': 'manual_client_submission',
                    'submitted_by': request.user.email,
                    'submitted_at': timezone.now().isoformat(),
                },
            }
        )

        # 2. Append note to invoice for admin reference
        invoice.notes = f"Payment submitted via {gateway.upper()} | TrxID: {trx_id} | Sender: {sender_number}"
        invoice.save(update_fields=['notes', 'updated_at'])

        messages.success(
            request,
            f"Payment submitted successfully! Method: {gateway.upper()} | Sender: {sender_number} | TrxID: {trx_id}. "
            f"Your order is now under Admin Verification. Once approved, your hosting & domain will be automatically activated."
        )

    except Exception as exc:
        logger.error("Payment submission failed: %s", exc)
        messages.error(request, f"Could not submit payment: {exc!s}")

    return redirect('/dashboard/?tab=invoices')


@login_required(login_url='login')
def service_detail_view(request, account_id):
    """
    WHMCS-style Service Details / Product Management Dashboard.
    Provides:
      - Real-time disk & bandwidth usage gauges via WHM API
      - 1-Click cPanel SSO & Webmail SSO launch links
      - Quick Shortcuts (Email Accounts, Forwarders, File Manager, Backup, Databases, phpMyAdmin, etc.)
      - Server Information & encrypted cPanel credentials (with copy/reveal)
      - Change Password Modal & Cancellation Request Modal
    """
    account = get_object_or_404(HostingAccount, id=account_id)

    # Ownership & Staff permission check
    if account.user != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        messages.error(request, "You do not have permission to access this service.")
        return redirect('dashboard')

    server = account.server

    # Fetch live usage from WHM
    live_stats = {
        'disk_used_mb': 0.0,
        'disk_limit_mb': float(account.package.disk_quota_mb) if account.package else 0.0,
        'disk_percent': 0,
        'bandwidth_used_mb': 0.0,
        'bandwidth_limit_mb': float(account.package.bandwidth_mb) if account.package else 0.0,
        'bandwidth_percent': 0,
        'ip': server.ip_address if server else '195.250.26.201',
        'domain': account.domain,
        'plan': account.package.name if account.package else '',
    }

    if server and account.username and account.status == HostingAccount.Status.ACTIVE:
        try:
            from hosting.drivers import get_driver
            driver = get_driver(server)
            if hasattr(driver, 'get_live_usage'):
                res_stats = driver.get_live_usage(account.username)
                if res_stats:
                    live_stats.update(res_stats)
                    # If WHM reported disk_limit_mb is 0 (unlimited), use package quota for visual gauge
                    if live_stats['disk_limit_mb'] == 0 and account.package and account.package.disk_quota_mb > 0:
                        live_stats['disk_limit_mb'] = float(account.package.disk_quota_mb)
                        live_stats['disk_percent'] = min(int((live_stats['disk_used_mb'] / live_stats['disk_limit_mb']) * 100), 100)
                    if live_stats['bandwidth_limit_mb'] == 0 and account.package and account.package.bandwidth_mb > 0:
                        live_stats['bandwidth_limit_mb'] = float(account.package.bandwidth_mb)
                        live_stats['bandwidth_percent'] = min(int((live_stats['bandwidth_used_mb'] / live_stats['bandwidth_limit_mb']) * 100), 100)
        except Exception as exc:
            logger.warning("Could not fetch live usage for account %s: %s", account.username, exc)

    # Shortcuts list
    shortcuts = [
        {'id': 'email', 'name': 'Email Accounts', 'icon': 'fa-solid fa-envelope', 'color': 'from-blue-500 to-indigo-600', 'desc': 'Create and manage email addresses'},
        {'id': 'forwarders', 'name': 'Forwarders', 'icon': 'fa-solid fa-share', 'color': 'from-indigo-500 to-purple-600', 'desc': 'Forward incoming mail to other addresses'},
        {'id': 'autoresponders', 'name': 'Autoresponders', 'icon': 'fa-solid fa-reply-all', 'color': 'from-purple-500 to-pink-600', 'desc': 'Send automated reply messages'},
        {'id': 'filemanager', 'name': 'File Manager', 'icon': 'fa-solid fa-folder-open', 'color': 'from-amber-500 to-orange-600', 'desc': 'Upload, edit and organize website files'},
        {'id': 'backup', 'name': 'Backup', 'icon': 'fa-solid fa-box-archive', 'color': 'from-teal-500 to-emerald-600', 'desc': 'Download and restore site backups'},
        {'id': 'domains', 'name': 'Domains', 'icon': 'fa-solid fa-globe', 'color': 'from-sky-500 to-cyan-600', 'desc': 'Manage addon domains and subdomains'},
        {'id': 'cron', 'name': 'Cron Jobs', 'icon': 'fa-solid fa-clock-rotate-left', 'color': 'from-slate-600 to-slate-800', 'desc': 'Automate scheduled background tasks'},
        {'id': 'mysql', 'name': 'MySQL® Databases', 'icon': 'fa-solid fa-database', 'color': 'from-orange-500 to-red-600', 'desc': 'Create databases and manage database users'},
        {'id': 'phpmyadmin', 'name': 'phpMyAdmin', 'icon': 'fa-solid fa-table-cells', 'color': 'from-yellow-500 to-amber-600', 'desc': 'Visual database administration tool'},
        {'id': 'awstats', 'name': 'Awstats', 'icon': 'fa-solid fa-chart-line', 'color': 'from-emerald-500 to-teal-700', 'desc': 'Web traffic and visitor statistics'},
    ]

    # Decrypt stored cPanel password if available
    cpanel_password = account.get_account_password()

    # Check if a matching domain registration exists
    from domains.models import Domain
    domain_obj = Domain.objects.filter(domain_name=account.domain, user=account.user).first()

    # Sidebar counters
    active_accounts_count = HostingAccount.objects.filter(user=request.user, status=HostingAccount.Status.ACTIVE).count()
    active_domains_count = Domain.objects.filter(user=request.user, status=Domain.Status.ACTIVE).count()
    unpaid_invoices_count = request.user.invoices.filter(status=Invoice.Status.UNPAID).count()
    profile = getattr(request.user, 'profile', None)

    # Check latest invoice
    latest_invoice = account.invoices.order_by('-issued_date').first()

    context = {
        'account': account,
        'package': account.package,
        'server': server,
        'live_stats': live_stats,
        'shortcuts': shortcuts,
        'cpanel_password': cpanel_password,
        'domain_obj': domain_obj,
        'latest_invoice': latest_invoice,
        'user': request.user,
        'profile': profile,
        'active_accounts_count': active_accounts_count,
        'active_domains_count': active_domains_count,
        'unpaid_invoices_count': unpaid_invoices_count,
    }
    return render(request, 'service_detail.html', context)


@login_required(login_url='login')
def service_sso_view(request, account_id, shortcut=None):
    """
    Generate dynamic Single Sign-On (SSO) session token via WHM create_user_session API
    and redirect directly to cPanel or the selected shortcut application.
    """
    account = get_object_or_404(HostingAccount, id=account_id)

    if account.user != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        messages.error(request, "Permission denied.")
        return redirect('dashboard')

    if account.status != HostingAccount.Status.ACTIVE:
        messages.error(request, "Control panel access is only available for active hosting services.")
        return redirect('service_detail', account_id=account.id)

    server = account.server
    if not server:
        messages.error(request, "Server configuration not found.")
        return redirect('service_detail', account_id=account.id)

    # App and service mapping
    shortcut_map = {
        'cpanel': ('cpaneld', None),
        'webmail': ('webmaild', None),
        'email': ('cpaneld', 'Email_Accounts'),
        'forwarders': ('cpaneld', 'Email_Forwarders'),
        'autoresponders': ('cpaneld', 'Email_AutoResponders'),
        'filemanager': ('cpaneld', 'FileManager_Home'),
        'backup': ('cpaneld', 'Backup_Home'),
        'domains': ('cpaneld', 'Domains_Home'),
        'cron': ('cpaneld', 'Cron_Home'),
        'mysql': ('cpaneld', 'Database_MySQL'),
        'phpmyadmin': ('cpaneld', 'Database_phpMyAdmin'),
        'awstats': ('cpaneld', 'Stats_AWStats'),
    }

    service_name, app_name = shortcut_map.get(shortcut, ('cpaneld', None))

    try:
        from hosting.drivers import get_driver
        driver = get_driver(server)
        if hasattr(driver, 'get_user_session_url'):
            sso_url = driver.get_user_session_url(account.username, service=service_name, app=app_name)
            return redirect(sso_url)
        else:
            # Fallback direct cPanel port
            port = 2096 if service_name == 'webmaild' else 2083
            return redirect(f"https://{server.hostname}:{port}/")
    except Exception as exc:
        logger.error("SSO generation error for %s: %s", account.username, exc)
        messages.error(request, f"Could not log in to control panel automatically: {exc!s}")
        return redirect('service_detail', account_id=account.id)


@login_required(login_url='login')
@require_http_methods(['POST'])
def service_change_password_view(request, account_id):
    """
    Change cPanel account password via live WHM API (passwd) and update encrypted DB record.
    """
    account = get_object_or_404(HostingAccount, id=account_id)

    if account.user != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        messages.error(request, "Permission denied.")
        return redirect('dashboard')

    if account.status != HostingAccount.Status.ACTIVE:
        messages.error(request, "Password can only be changed for active hosting services.")
        return redirect('service_detail', account_id=account.id)

    new_password = request.POST.get('new_password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()

    if not new_password or len(new_password) < 8:
        messages.error(request, "Password must be at least 8 characters long.")
        return redirect('service_detail', account_id=account.id)

    if new_password != confirm_password:
        messages.error(request, "Passwords do not match.")
        return redirect('service_detail', account_id=account.id)

    server = account.server
    try:
        from hosting.drivers import get_driver
        driver = get_driver(server)
        if hasattr(driver, 'change_password'):
            driver.change_password(account.username, new_password)
        account.set_account_password(new_password)
        account.save(update_fields=['password_encrypted'])
        messages.success(request, f"cPanel password for user '{account.username}' has been successfully updated.")
    except Exception as exc:
        logger.error("Failed to change cPanel password: %s", exc)
        messages.error(request, f"Failed to update cPanel password on server: {exc!s}")

    return redirect('service_detail', account_id=account.id)


@login_required(login_url='login')
@require_http_methods(['POST'])
def service_request_cancellation_view(request, account_id):
    """
    Submit a service cancellation request.
    """
    account = get_object_or_404(HostingAccount, id=account_id)

    if account.user != request.user and not (request.user.is_staff or request.user.role == 'admin'):
        messages.error(request, "Permission denied.")
        return redirect('dashboard')

    reason = request.POST.get('reason', '').strip()
    cancellation_type = request.POST.get('cancellation_type', 'end_of_billing_period')

    logger.info("Cancellation requested for %s: type=%s, reason=%s", account.domain, cancellation_type, reason)
    messages.success(request, f"Cancellation request for '{account.domain}' has been submitted. Our team will process it accordingly.")
    return redirect('service_detail', account_id=account.id)
