"""
HostPro Custom Admin Dashboard Views
====================================
Complete custom web management portal allowing staff administrators
to manage the entire platform without relying on Django's default admin.

Features:
  - Overview Analytics & KPIs (Revenue, Servers, Accounts, Domains, Clients)
  - WHM / cPanel Servers (Add, Edit, Test Connection live, Delete)
  - Domain Registrars (Add, Edit, Check Balance live, Toggle Default)
  - TLD Pricing Manager (Add, Edit, Delete TLD pricing)
  - Hosting Packages (Add, Edit, Toggle Featured)
  - Client Hosting Accounts (Live Suspend, Unsuspend, Terminate, Provision)
  - Client Domains (Manual Registrar Provisioning trigger)
  - Invoices & Transactions (Mark PAID & Trigger Automated Provisioning)
  - Clients & Wallets (User overview, Add / Adjust wallet credit)
"""
import uuid
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Q

from hosting.models import Server, HostingPackage, HostingAccount, ServerDriver
from hosting.drivers.factory import get_driver
from hosting.services import ProvisioningService
from hosting.tasks import provision_hosting_account, unsuspend_hosting_account

from domains.models import DomainRegistrar, TLDPricing, Domain, RegistrarType
from domains.drivers.factory import get_registrar_driver
from domains.tasks import register_domain_task
from domains.services import DomainService

from billing.models import Invoice, Transaction, Gateway
from billing.services import PaymentService
from accounts.models import ClientProfile

User = get_user_model()
logger = logging.getLogger(__name__)


def is_staff_or_admin(user):
    """Check if user has administrative rights."""
    return user.is_authenticated and (user.is_staff or user.is_superuser or user.role == User.Role.ADMIN)


@user_passes_test(is_staff_or_admin, login_url='login')
def admin_dashboard_view(request):
    """
    Main Custom Admin Dashboard.
    Renders all administrative sections in one unified modern interface.
    """
    # ── 1. KPI Calculations ───────────────────────────────────────────────────
    total_revenue = Invoice.objects.filter(status=Invoice.Status.PAID).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    unpaid_revenue = Invoice.objects.filter(status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE]).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

    active_accounts_count = HostingAccount.objects.filter(status=HostingAccount.Status.ACTIVE).count()
    pending_accounts_count = HostingAccount.objects.filter(status=HostingAccount.Status.PENDING).count()

    active_domains_count = Domain.objects.filter(status=Domain.Status.ACTIVE).count()
    pending_domains_count = Domain.objects.filter(status=Domain.Status.PENDING).count()

    total_clients_count = User.objects.filter(role__in=[User.Role.CLIENT, User.Role.RESELLER]).count()
    total_servers_count = Server.objects.count()

    # ── 2. Data Lists ─────────────────────────────────────────────────────────
    servers = Server.objects.annotate(
        active_accts=Count('accounts', filter=Q(accounts__status=HostingAccount.Status.ACTIVE))
    ).order_by('name')

    registrars = DomainRegistrar.objects.order_by('-is_default', 'name')
    tld_prices = TLDPricing.objects.order_by('tld')
    packages = HostingPackage.objects.select_related('server').order_by('monthly_price')

    hosting_accounts = HostingAccount.objects.select_related('user', 'package', 'server').order_by('-created_at')
    domains = Domain.objects.select_related('user', 'registrar').order_by('-created_at')
    invoices = Invoice.objects.select_related('user', 'hosting_account', 'domain').prefetch_related('items').order_by('-created_at')
    clients = User.objects.select_related('profile').filter(role__in=[User.Role.CLIENT, User.Role.RESELLER]).order_by('-date_joined')
    recent_transactions = Transaction.objects.select_related('user', 'invoice').order_by('-created_at')[:10]

    context = {
        'total_revenue': total_revenue,
        'unpaid_revenue': unpaid_revenue,
        'active_accounts_count': active_accounts_count,
        'pending_accounts_count': pending_accounts_count,
        'active_domains_count': active_domains_count,
        'pending_domains_count': pending_domains_count,
        'total_clients_count': total_clients_count,
        'total_servers_count': total_servers_count,

        'servers': servers,
        'registrars': registrars,
        'tld_prices': tld_prices,
        'packages': packages,
        'hosting_accounts': hosting_accounts,
        'domains': domains,
        'invoices': invoices,
        'clients': clients,
        'recent_transactions': recent_transactions,

        'server_driver_choices': ServerDriver.choices,
        'registrar_driver_choices': RegistrarType.choices,
    }
    return render(request, 'admin_dashboard.html', context)


# ─── AJAX DIAGNOSTIC ENDPOINTS ────────────────────────────────────────────────

@user_passes_test(is_staff_or_admin, login_url='login')
def admin_test_server_view(request, server_id):
    """
    Live test connection to a WHM/CyberPanel server.
    Returns JSON response with diagnostics.
    """
    server = get_object_or_404(Server, id=server_id)
    try:
        driver = get_driver(server)
        info = driver.get_account_info('root')
        return JsonResponse({
            'success': True,
            'message': f"Connection to '{server.name}' ({server.hostname}) was SUCCESSFUL! WHM API token is valid."
        })
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'message': f"Connection ping returned: {str(exc)}"
        })


@user_passes_test(is_staff_or_admin, login_url='login')
def admin_check_registrar_balance_view(request, registrar_id):
    """
    Live balance check from wholesale registrar API (ResellerClub/Namecheap).
    Returns JSON response.
    """
    registrar = get_object_or_404(DomainRegistrar, id=registrar_id)
    try:
        driver = get_registrar_driver(registrar)
        balance_info = driver.get_account_balance()
        return JsonResponse({
            'success': True,
            'balance': balance_info.get('balance', '0.00'),
            'currency': balance_info.get('currency', 'USD'),
            'message': f"Live Balance: {balance_info.get('currency', 'USD')} {balance_info.get('balance', '0.00')}"
        })
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'message': f"Registrar API error: {str(exc)}"
        })


# ─── UNIFIED ACTION HANDLER ───────────────────────────────────────────────────

@user_passes_test(is_staff_or_admin, login_url='login')
@require_http_methods(['POST'])
def admin_action_handler_view(request, action_type):
    """
    Dispatches CRUD & Automation actions from the Custom Admin Dashboard.
    """
    # ── 1. ADD NEW SERVER ─────────────────────────────────────────────────────
    if action_type == 'add_server':
        name = request.POST.get('name', '').strip()
        hostname = request.POST.get('hostname', '').strip()
        ip_address = request.POST.get('ip_address', '').strip()
        driver = request.POST.get('driver', 'cpanel')
        port = int(request.POST.get('port', 2087))
        api_username = request.POST.get('api_username', 'root').strip()
        api_token = request.POST.get('api_token', '').strip()
        max_accounts = int(request.POST.get('max_accounts', 100))

        if not name or not hostname or not api_token:
            messages.error(request, "Server Name, Hostname, and API Token are required.")
            return redirect('admin_dashboard')

        server = Server(
            name=name,
            hostname=hostname,
            ip_address=ip_address,
            driver=driver,
            port=port,
            api_username=api_username,
            max_accounts=max_accounts,
            is_active=True,
        )
        server.set_api_token(api_token)
        server.save()
        messages.success(request, f"Server '{name}' added successfully with encrypted WHM credentials!")

    # ── 2. ADD DOMAIN REGISTRAR ───────────────────────────────────────────────
    elif action_type == 'add_registrar':
        name = request.POST.get('name', '').strip()
        driver = request.POST.get('driver', 'mock')
        api_user = request.POST.get('api_user', '').strip()
        api_key = request.POST.get('api_key', '').strip()
        is_sandbox = request.POST.get('is_sandbox') == 'on'
        is_default = request.POST.get('is_default') == 'on'

        if not name or not api_key:
            messages.error(request, "Registrar Name and API Key are required.")
            return redirect('admin_dashboard')

        if is_default:
            DomainRegistrar.objects.update(is_default=False)

        registrar = DomainRegistrar(
            name=name,
            driver=driver,
            api_user=api_user,
            is_sandbox=is_sandbox,
            is_default=is_default,
            is_active=True,
        )
        registrar.set_api_key(api_key)
        registrar.save()
        messages.success(request, f"Registrar '{name}' added successfully with encrypted credentials!")

    # ── 3. ADD / UPDATE TLD PRICING ───────────────────────────────────────────
    elif action_type == 'save_tld':
        tld = request.POST.get('tld', '').strip().lower()
        if not tld.startswith('.'):
            tld = '.' + tld
        register_price = Decimal(request.POST.get('register_price', '0.00'))
        renew_price = Decimal(request.POST.get('renew_price', '0.00'))
        is_active = request.POST.get('is_active') == 'on'

        TLDPricing.objects.update_or_create(
            tld=tld,
            defaults={
                'register_price': register_price,
                'renew_price': renew_price,
                'is_active': is_active,
            }
        )
        messages.success(request, f"TLD Pricing for '{tld}' saved: Register ৳{register_price}, Renew ৳{renew_price}.")

    # ── 4. ADD HOSTING PACKAGE ────────────────────────────────────────────────
    elif action_type == 'add_package':
        name = request.POST.get('name', '').strip()
        server_id = request.POST.get('server_id')
        whm_package_name = request.POST.get('whm_package_name', '').strip()
        monthly_price = Decimal(request.POST.get('monthly_price', '0.00'))
        annual_price = Decimal(request.POST.get('annual_price', '0.00'))
        disk_quota_mb = int(request.POST.get('disk_quota_mb', 5120))
        bandwidth_mb = int(request.POST.get('bandwidth_mb', 0))
        max_databases = int(request.POST.get('max_databases', 5))
        max_email_accounts = int(request.POST.get('max_email_accounts', 5))
        description = request.POST.get('description', '')
        is_featured = request.POST.get('is_featured') == 'on'

        server = get_object_or_404(Server, id=server_id)
        HostingPackage.objects.create(
            name=name,
            server=server,
            whm_package_name=whm_package_name,
            monthly_price=monthly_price,
            annual_price=annual_price,
            disk_quota_mb=disk_quota_mb,
            bandwidth_mb=bandwidth_mb,
            max_databases=max_databases,
            max_email_accounts=max_email_accounts,
            description=description,
            is_featured=is_featured,
            is_active=True,
        )
        messages.success(request, f"Hosting Package '{name}' created on server '{server.name}'!")

    # ── 5. HOSTING ACCOUNT ACTIONS (SUSPEND / UNSUSPEND / TERMINATE / PROVISION)
    elif action_type == 'hosting_account_action':
        account_id = request.POST.get('account_id')
        action = request.POST.get('action')
        account = get_object_or_404(HostingAccount, id=account_id)

        if action == 'provision':
            account.status = HostingAccount.Status.ACTIVE
            account.provisioned_at = timezone.now()
            account.save(update_fields=['status', 'provisioned_at'])
            provision_hosting_account.delay(str(account.id))
            messages.success(request, f"Manual WHM provisioning triggered for '{account.domain}'!")

        elif action == 'suspend':
            try:
                ProvisioningService.suspend_account(str(account.id), reason="Suspended by Administrator")
                messages.warning(request, f"Hosting account '{account.domain}' has been SUSPENDED on WHM.")
            except Exception as exc:
                account.status = HostingAccount.Status.SUSPENDED
                account.save(update_fields=['status'])
                messages.warning(request, f"Account '{account.domain}' marked SUSPENDED locally: {exc}")

        elif action == 'unsuspend':
            try:
                ProvisioningService.unsuspend_account(str(account.id))
                messages.success(request, f"Hosting account '{account.domain}' has been UNSUSPENDED on WHM.")
            except Exception as exc:
                account.status = HostingAccount.Status.ACTIVE
                account.save(update_fields=['status'])
                messages.warning(request, f"Account '{account.domain}' marked ACTIVE locally: {exc}")

        elif action == 'terminate':
            try:
                driver = get_driver(account.server)
                driver.terminate_account(account.username)
            except Exception as exc:
                logger.warning("WHM terminate call: %s", exc)
            account.status = HostingAccount.Status.TERMINATED
            account.save(update_fields=['status'])
            messages.error(request, f"Hosting account '{account.domain}' has been TERMINATED.")

    # ── 6. DOMAIN ACTION (REGISTER AT REGISTRAR NOW) ───────────────────────────
    elif action_type == 'domain_action':
        domain_id = request.POST.get('domain_id')
        domain = get_object_or_404(Domain, id=domain_id)
        try:
            DomainService.provision_domain(str(domain.id))
            messages.success(request, f"Domain '{domain.domain_name}' registered successfully via Registrar API!")
        except Exception as exc:
            messages.error(request, f"Failed to register '{domain.domain_name}': {str(exc)}")

    # ── 7. INVOICE ACTION (MARK PAID & TRIGGER AUTOMATION) ─────────────────────
    elif action_type == 'invoice_action':
        invoice_id = request.POST.get('invoice_id')
        invoice = get_object_or_404(Invoice, id=invoice_id)

        if invoice.status != Invoice.Status.PAID:
            Transaction.objects.create(
                invoice=invoice,
                user=invoice.user,
                gateway=Gateway.MANUAL,
                status=Transaction.Status.SUCCESS,
                gateway_transaction_id=f"ADMIN-MANUAL-{uuid.uuid4().hex[:8].upper()}",
                amount=invoice.total,
                gateway_response={'channel': 'admin_custom_dashboard', 'operator': request.user.email},
            )
            invoice.mark_paid()
            invoice.save(update_fields=['status', 'paid_at', 'updated_at'])

            # Trigger automated provisioning for hosting
            if invoice.hosting_account:
                acct = invoice.hosting_account
                acct.status = HostingAccount.Status.ACTIVE
                acct.provisioned_at = timezone.now()
                acct.save(update_fields=['status', 'provisioned_at'])
                provision_hosting_account.delay(str(acct.id))

            # Trigger automated provisioning for domain
            if invoice.domain:
                try:
                    DomainService.provision_domain(str(invoice.domain.id))
                except Exception as exc:
                    logger.error("Admin invoice domain auto-provision failed: %s", exc)

            messages.success(request, f"Invoice #{invoice.invoice_number} marked PAID! Automated provisioning dispatched.")

    # ── 8. CLIENT WALLET CREDIT ADJUSTMENT ─────────────────────────────────────
    elif action_type == 'adjust_credit':
        user_id = request.POST.get('user_id')
        amount = Decimal(request.POST.get('amount', '0.00'))
        target_user = get_object_or_404(User, id=user_id)
        profile, _ = ClientProfile.objects.get_or_create(user=target_user)

        profile.credit_balance += amount
        if profile.credit_balance < Decimal('0.00'):
            profile.credit_balance = Decimal('0.00')
        profile.save(update_fields=['credit_balance'])

        messages.success(
            request,
            f"Wallet credit for '{target_user.email}' updated by ৳{amount}. New Balance: ৳{profile.credit_balance}"
        )

    return redirect('admin_dashboard')
