"""
Custom Admin Control Center Views
===================================
Provides comprehensive, unified management for:
- WHM & Provisioning Servers
- Domain Registrar APIs & TLD Pricing
- Hosting Packages & Real-Time WHM Synchronization
- Client Hosting Accounts (Provision, Suspend, Unsuspend, Terminate)
- Registered Domains
- Invoices & Billing Automation
- Clients & Wallet Credit Management
"""
import logging
import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import ClientProfile
from billing.models import Gateway, Invoice, InvoiceItem, Transaction
from core.models import SiteSetting
from domains.drivers.factory import get_registrar_driver
from domains.models import Domain, DomainRegistrar, RegistrarType, TLDPricing
from domains.services import DomainService
from hosting.drivers.factory import get_driver
from hosting.models import BillingCycle, HostingAccount, HostingPackage, Server
from hosting.services import ProvisioningService
from hosting.tasks import provision_hosting_account

User = get_user_model()
logger = logging.getLogger('admin_dashboard')


def is_staff_or_admin(user) -> bool:
    """Helper to verify if authenticated user has administrative privileges."""
    if not user.is_authenticated:
        return False
    return user.is_staff or user.is_superuser or getattr(user, 'role', '') == 'admin'


# ─── MAIN ADMIN DASHBOARD VIEW ────────────────────────────────────────────────

def admin_dashboard_view(request):
    """
    Unified Single-Page Tabbed Administration Portal.
    Renders all live operational infrastructure and records.
    """
    if not request.user.is_authenticated:
        return redirect(f'/login/?next={request.path}')

    if not is_staff_or_admin(request.user):
        messages.error(request, "Access restricted. Staff or Administrator privileges required.")
        return redirect('dashboard')

    # 1. Connected Servers & Statistics
    servers_qs = Server.objects.all().order_by('-is_active', 'name')
    servers_list = []
    for s in servers_qs:
        active_accts = s.accounts.filter(status=HostingAccount.Status.ACTIVE).count()
        pending_accts = s.accounts.filter(status=HostingAccount.Status.PENDING).count()
        total_accts = s.accounts.count()
        servers_list.append({
            'id': s.id,
            'name': s.name,
            'hostname': s.hostname,
            'ip_address': s.ip_address,
            'port': s.port,
            'driver': s.driver,
            'api_username': s.api_username,
            'is_active': s.is_active,
            'max_accounts': s.max_accounts,
            'active_accts': active_accts,
            'pending_accts': pending_accts,
            'total_accts': total_accts,
        })

    # 2. Domain Registrars & TLD Pricing
    registrars = DomainRegistrar.objects.all().order_by('-is_default', 'name')
    tld_prices = TLDPricing.objects.all().order_by('tld')

    # 3. Hosting Packages
    packages = HostingPackage.objects.select_related('server').prefetch_related('accounts').all().order_by('monthly_price')

    # 4. Operations: Hosting Accounts
    hosting_accounts = HostingAccount.objects.select_related('user', 'server', 'package').all().order_by('-created_at')

    # 5. Operations: Registered Domains
    domains = Domain.objects.select_related('user', 'registrar').all().order_by('-created_at')

    # 6. Operations: Invoices & Transactions
    invoices = Invoice.objects.select_related('user', 'hosting_account', 'domain').all().order_by('-issued_date', '-created_at')
    recent_transactions = Transaction.objects.select_related('user', 'invoice').all().order_by('-created_at')[:15]

    # 7. Clients & Wallets
    clients = User.objects.filter(
        Q(role='client') | Q(role=User.Role.CLIENT) | Q(is_staff=False, is_superuser=False)
    ).distinct().select_related('profile').order_by('-date_joined')
    if not clients.exists():
        # Fallback to non-superuser users
        clients = User.objects.filter(is_superuser=False).select_related('profile').order_by('-date_joined')

    # 8. High-Level KPI Calculations
    active_accounts_count = HostingAccount.objects.filter(status=HostingAccount.Status.ACTIVE).count()
    pending_accounts_count = HostingAccount.objects.filter(status=HostingAccount.Status.PENDING).count()
    suspended_accounts_count = HostingAccount.objects.filter(status=HostingAccount.Status.SUSPENDED).count()

    active_domains_count = Domain.objects.filter(status=Domain.Status.ACTIVE).count()
    pending_domains_count = Domain.objects.filter(status=Domain.Status.PENDING).count()

    total_clients_count = clients.count()
    total_servers_count = servers_qs.count()

    # Revenue metrics
    monthly_revenue = Invoice.objects.filter(status=Invoice.Status.PAID).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    unpaid_revenue = Invoice.objects.filter(status__in=[Invoice.Status.UNPAID, Invoice.Status.OVERDUE]).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    pending_invoices_count = Invoice.objects.filter(status=Invoice.Status.UNPAID).count()

    context = {
        'admin_user': request.user,
        'servers': servers_list,
        'registrars': registrars,
        'registrar_driver_choices': RegistrarType.choices,
        'tld_prices': tld_prices,
        'packages': packages,
        'hosting_accounts': hosting_accounts,
        'domains': domains,
        'invoices': invoices,
        'recent_transactions': recent_transactions,
        'clients': clients,

        # Metrics
        'active_accounts_count': active_accounts_count,
        'pending_accounts_count': pending_accounts_count,
        'suspended_accounts_count': suspended_accounts_count,
        'active_domains_count': active_domains_count,
        'pending_domains_count': pending_domains_count,
        'total_clients_count': total_clients_count,
        'total_servers_count': total_servers_count,
        'monthly_revenue': monthly_revenue,
        'unpaid_revenue': unpaid_revenue,
        'pending_invoices_count': pending_invoices_count,

        # Site & SEO Settings
        'site_settings': SiteSetting.get_settings(),
    }
    return render(request, 'admin_dashboard.html', context)


# ─── AJAX DIAGNOSTIC & API ENDPOINTS ──────────────────────────────────────────

def admin_test_server_view(request, server_id):
    """
    Live test connection to a WHM/CyberPanel server.
    Returns JSON response with diagnostics.
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Admin authentication required.'}, status=401)

    server = get_object_or_404(Server, id=server_id)
    try:
        driver = get_driver(server)
        if hasattr(driver, 'test_connection'):
            res = driver.test_connection()
            return JsonResponse(res)
        return JsonResponse({
            'success': True,
            'message': f"Connection to '{server.name}' ({server.hostname}) was verified."
        })
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'message': f"Connection ping returned: {exc!s}"
        })


def admin_whm_packages_api(request, server_id):
    """
    Live fetch packages configured on a WHM server.
    Returns JSON response with package names, quotas, and bandwidth limits.
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Admin authentication required.'}, status=401)

    server = get_object_or_404(Server, id=server_id)
    try:
        driver = get_driver(server)
        packages = driver.list_packages()
        return JsonResponse({
            'success': True,
            'server_name': server.name,
            'server_id': str(server.id),
            'packages': packages,
            'count': len(packages),
        })
    except Exception as exc:
        logger.exception("Error fetching WHM packages for server %s: %s", server.name, exc)
        return JsonResponse({
            'success': False,
            'message': f"Failed to fetch packages from WHM server '{server.name}': {exc!s}",
            'packages': [],
        })


def admin_check_registrar_balance_view(request, registrar_id):
    """
    Live balance check from wholesale registrar API (ResellerClub/Namecheap).
    Returns JSON response.
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Admin authentication required.'}, status=401)

    registrar = get_object_or_404(DomainRegistrar, id=registrar_id)
    try:
        driver = get_registrar_driver(registrar)
        balance_info = driver.get_account_balance()
        return JsonResponse({
            'success': True,
            'balance': balance_info.get('balance', '0.00'),
            'currency': balance_info.get('currency', 'USD'),
            'message': f"Registrar account balance: {balance_info.get('currency', 'USD')} {balance_info.get('balance', '0.00')}"
        })
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'message': f"Failed to query {registrar.name}: {exc!s}"
        })


def admin_client_details_api(request, client_id):
    """
    Fetch comprehensive WHMCS-style profile details for a client:
    - User Info & Profile (name, email, phone, company, address, credit)
    - Hosting Accounts list
    - Domains list
    - Invoices list
    - Transactions list
    - Financial summaries
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Admin authentication required.'}, status=401)

    client = get_object_or_404(User.objects.select_related('profile'), id=client_id)
    profile = getattr(client, 'profile', None)

    # 1. Hosting Accounts
    hosting_qs = HostingAccount.objects.filter(user=client).select_related('server', 'package').order_by('-created_at')
    hosting_list = [{
        'id': str(h.id),
        'domain': h.domain,
        'username': h.username,
        'package_name': h.package.name if h.package else '—',
        'server_name': h.server.name if h.server else '—',
        'status': h.status,
        'billing_cycle': h.get_billing_cycle_display(),
        'next_due_date': h.next_due_date.strftime('%Y-%m-%d') if h.next_due_date else None,
        'amount': str(h.amount or '0.00'),
        'created_at': h.created_at.strftime('%Y-%m-%d') if h.created_at else None,
    } for h in hosting_qs]

    # 2. Domains
    domains_qs = Domain.objects.filter(user=client).select_related('registrar').order_by('-created_at')
    domains_list = [{
        'id': str(d.id),
        'domain_name': d.domain_name,
        'registrar_name': d.registrar.name if d.registrar else 'Default Registrar',
        'status': d.status,
        'registration_date': d.registration_date.strftime('%Y-%m-%d') if d.registration_date else None,
        'expiry_date': d.expiry_date.strftime('%Y-%m-%d') if d.expiry_date else None,
        'next_due_date': d.next_due_date.strftime('%Y-%m-%d') if d.next_due_date else None,
        'auto_renew': bool(d.auto_renew),
        'registration_years': d.registration_years,
    } for d in domains_qs]

    # 3. Invoices
    invoices_qs = Invoice.objects.filter(user=client).order_by('-issued_date', '-created_at')
    invoices_list = [{
        'id': str(inv.id),
        'invoice_number': inv.invoice_number,
        'invoice_type': inv.get_invoice_type_display(),
        'total': str(inv.total),
        'status': inv.status,
        'issued_date': inv.issued_date.strftime('%Y-%m-%d') if inv.issued_date else None,
        'due_date': inv.due_date.strftime('%Y-%m-%d') if inv.due_date else None,
        'paid_at': inv.paid_at.strftime('%Y-%m-%d %H:%M') if inv.paid_at else None,
    } for inv in invoices_qs]

    # 4. Transactions
    txns_qs = Transaction.objects.filter(user=client).select_related('invoice').order_by('-created_at')[:20]
    txns_list = [{
        'id': str(t.id),
        'invoice_number': t.invoice.invoice_number if t.invoice else '—',
        'gateway': t.get_gateway_display() if hasattr(t, 'get_gateway_display') else t.gateway,
        'status': t.status,
        'gateway_transaction_id': t.gateway_transaction_id or '—',
        'amount': str(t.amount),
        'created_at': t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else None,
    } for t in txns_qs]

    total_spent = invoices_qs.filter(status=Invoice.Status.PAID).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

    return JsonResponse({
        'success': True,
        'client': {
            'id': str(client.id),
            'email': client.email,
            'first_name': client.first_name,
            'last_name': client.last_name,
            'full_name': client.get_full_name() or client.email,
            'role': client.role,
            'is_active': client.is_active,
            'date_joined': client.date_joined.strftime('%Y-%m-%d') if client.date_joined else None,
            'last_login': client.last_login.strftime('%Y-%m-%d %H:%M') if client.last_login else None,
            'phone': profile.phone if profile else '',
            'company_name': profile.company_name if profile else '',
            'address_line1': profile.address_line1 if profile else '',
            'address_line2': profile.address_line2 if profile else '',
            'city': profile.city if profile else '',
            'state': profile.state if profile else '',
            'country': profile.country if profile else 'BD',
            'postal_code': profile.postal_code if profile else '',
            'credit_balance': str(profile.credit_balance if profile else '0.00'),
            'currency': profile.currency if profile else 'BDT',
        },
        'stats': {
            'total_spent': str(total_spent),
            'hosting_count': len(hosting_list),
            'domains_count': len(domains_list),
            'invoices_count': len(invoices_list),
            'active_services': sum(1 for h in hosting_list if h['status'] == 'active'),
            'active_domains': sum(1 for d in domains_list if d['status'] == 'active'),
        },
        'hosting_accounts': hosting_list,
        'domains': domains_list,
        'invoices': invoices_list,
        'transactions': txns_list,
    })


def admin_login_as_client_view(request, client_id):
    """
    Allow administrator to securely log in as a specific client (WHMCS 'Login as Client' feature).
    Redirects directly to client dashboard.
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        messages.error(request, "Administrator privileges required to perform client impersonation.")
        return redirect('admin_dashboard')

    client = get_object_or_404(User, id=client_id)
    from django.contrib.auth import login as auth_login
    auth_login(request, client)
    messages.success(request, f"Logged in as client: {client.get_full_name() or client.email} ({client.email})")
    return redirect('dashboard')



ACTION_TAB_MAP = {
    'add_server': 'servers',
    'edit_server': 'servers',
    'delete_server': 'servers',
    'add_registrar': 'registrars',
    'edit_registrar': 'registrars',
    'delete_registrar': 'registrars',

    'add_tld': 'tlds',
    'save_tld': 'tlds',
    'edit_tld': 'tlds',
    'delete_tld': 'tlds',
    'seed_bdwebs_tlds': 'tlds',
    'seed_tlds': 'tlds',
    'sync_whm_packages': 'packages',
    'add_package': 'packages',
    'edit_package': 'packages',
    'delete_package': 'packages',
    'create_hosting_account': 'accounts',
    'edit_hosting_account': 'accounts',
    'account_action': 'accounts',
    'hosting_account_action': 'accounts',
    'delete_hosting_account': 'accounts',
    'sync_whm_accounts': 'accounts',
    'add_domain_order': 'domains',
    'edit_domain': 'domains',
    'domain_action': 'domains',
    'delete_domain': 'domains',
    'sync_registrar_domains': 'domains',
    'create_invoice': 'invoices',
    'invoice_action': 'invoices',
    'mark_invoice_paid': 'invoices',
    'delete_invoice': 'invoices',
    'cancel_invoice': 'invoices',
    'add_client': 'clients',
    'edit_client': 'clients',
    'delete_client': 'clients',
    'adjust_wallet': 'clients',
    'adjust_credit': 'clients',
    'update_site_settings': 'settings',
    'save_site_settings': 'settings',
    'save_settings': 'settings',
}


def redirect_to_admin_tab(action_type, request=None):
    """Redirect to the active admin tab preserving state."""
    target_tab = None
    if request:
        target_tab = request.POST.get('active_tab') or request.GET.get('tab')
    if not target_tab:
        target_tab = ACTION_TAB_MAP.get(action_type, 'overview')
    return redirect(f"/admin-dashboard/?tab={target_tab}")


# ─── ADMIN ACTIONS HANDLER ───────────────────────────────────────────────────

def admin_action_handler_view(request, action_type):
    """
    Central POST action handler for all admin operational buttons & modal forms.
    Redirects back to admin_dashboard with active tab query parameter and a flash message.
    """
    if not request.user.is_authenticated or not is_staff_or_admin(request.user):
        messages.error(request, "Unauthorized admin operation.")
        return redirect_to_admin_tab(action_type, request)

    if request.method != 'POST':
        return redirect_to_admin_tab(action_type, request)

    # ── 1a. ADD WHM / CPANEL SERVER ───────────────────────────────────────────
    if action_type == 'add_server':
        name = request.POST.get('name', '').strip()
        hostname = request.POST.get('hostname', '').strip()
        ip_address = request.POST.get('ip_address', '').strip() or '127.0.0.1'
        port = int(request.POST.get('port', 2087))
        driver = request.POST.get('driver', 'cpanel')
        api_username = request.POST.get('api_username', '').strip()
        api_token = request.POST.get('api_token', '').strip()
        max_accounts = int(request.POST.get('max_accounts', 500))
        is_active = request.POST.get('is_active', 'on') == 'on'
        nameserver_1 = request.POST.get('nameserver_1', '').strip()
        nameserver_2 = request.POST.get('nameserver_2', '').strip()

        if not name or not hostname or not api_username or not api_token:
            messages.error(request, "Server Name, Hostname, API Username, and API Token/Hash are required.")
            return redirect_to_admin_tab(action_type, request)

        server = Server(
            name=name,
            hostname=hostname,
            ip_address=ip_address,
            port=port,
            driver=driver,
            api_username=api_username,
            max_accounts=max_accounts,
            is_active=is_active,
            nameserver_1=nameserver_1,
            nameserver_2=nameserver_2,
        )
        server.set_api_token(api_token)
        server.save()
        messages.success(request, f"WHM Server '{name}' ({hostname}) added successfully with encrypted credentials!")

    # ── 1b. EDIT WHM SERVER ───────────────────────────────────────────────────
    elif action_type == 'edit_server':
        server_id = request.POST.get('server_id')
        server = get_object_or_404(Server, id=server_id)
        server.name = request.POST.get('name', server.name).strip()
        server.hostname = request.POST.get('hostname', server.hostname).strip()
        server.ip_address = request.POST.get('ip_address', server.ip_address).strip()
        server.port = int(request.POST.get('port', server.port))
        server.driver = request.POST.get('driver', server.driver)
        server.api_username = request.POST.get('api_username', server.api_username).strip()
        server.is_active = request.POST.get('is_active') == 'on' or request.POST.get('is_active') == 'true'

        new_token = request.POST.get('api_token', '').strip()
        if new_token:
            server.set_api_token(new_token)

        server.save()
        messages.success(request, f"Server '{server.name}' updated successfully.")

    # ── 1c. DELETE SERVER ─────────────────────────────────────────────────────
    elif action_type == 'delete_server':
        server_id = request.POST.get('server_id')
        server = get_object_or_404(Server, id=server_id)
        server_name = server.name
        # Clean up attached accounts & packages safely
        server.accounts.all().delete()
        server.packages.all().delete()
        server.delete()
        messages.success(request, f"Server '{server_name}' and associated records deleted successfully.")


    # ── 2a. ADD DOMAIN REGISTRAR ──────────────────────────────────────────────
    elif action_type == 'add_registrar':
        name = request.POST.get('name', '').strip()
        reg_type = request.POST.get('registrar_type') or request.POST.get('driver', 'bdwebs')
        api_user = request.POST.get('api_user', '').strip()
        api_key = request.POST.get('api_key', '').strip()
        api_endpoint = request.POST.get('api_endpoint', '').strip()
        is_sandbox = request.POST.get('sandbox_mode') == 'on' or request.POST.get('is_sandbox') == 'on'
        is_default = request.POST.get('is_default') == 'on'

        if not name or not api_key:
            messages.error(request, "Registrar Name and API Key are required.")
            return redirect_to_admin_tab(action_type, request)

        if is_default:
            DomainRegistrar.objects.update(is_default=False)

        registrar = DomainRegistrar(
            name=name,
            driver=reg_type,
            api_user=api_user,
            is_sandbox=is_sandbox,
            is_default=is_default,
            is_active=True,
            extra_config={'api_endpoint': api_endpoint or 'https://cp.bdwebs.com/modules/addons/DomainsReseller/api/index.php'}
        )
        registrar.set_api_key(api_key)
        registrar.save()
        messages.success(request, f"Registrar '{name}' added successfully with encrypted credentials!")

    # ── 2b. EDIT REGISTRAR ────────────────────────────────────────────────────
    elif action_type == 'edit_registrar':
        registrar_id = request.POST.get('registrar_id')
        reg = get_object_or_404(DomainRegistrar, id=registrar_id)
        reg.name = request.POST.get('name', reg.name).strip()
        reg.driver = request.POST.get('registrar_type') or request.POST.get('driver', reg.driver)
        reg.api_user = request.POST.get('api_user', reg.api_user).strip()
        endpoint_val = request.POST.get('api_endpoint', '').strip()
        if endpoint_val:
            reg.api_endpoint = endpoint_val
        reg.is_sandbox = request.POST.get('sandbox_mode') == 'on' or request.POST.get('is_sandbox') == 'on'
        reg.is_active = request.POST.get('is_active') == 'on' or request.POST.get('is_active') == 'true'
        is_def = request.POST.get('is_default') == 'on'
        if is_def and not reg.is_default:
            DomainRegistrar.objects.exclude(id=reg.id).update(is_default=False)
            reg.is_default = True
        elif not is_def:
            reg.is_default = False

        new_key = request.POST.get('api_key', '').strip()
        if new_key:
            reg.set_api_key(new_key)

        reg.save()
        messages.success(request, f"Registrar '{reg.name}' updated successfully.")

    # ── 2c. DELETE REGISTRAR ──────────────────────────────────────────────────
    elif action_type == 'delete_registrar':
        registrar_id = request.POST.get('registrar_id')
        reg = get_object_or_404(DomainRegistrar, id=registrar_id)
        reg_name = reg.name
        Domain.objects.filter(registrar=reg).update(registrar=None)
        TLDPricing.objects.filter(registrar=reg).update(registrar=None)
        reg.delete()
        messages.success(request, f"Registrar '{reg_name}' deleted successfully.")



    # ── 3a. ADD / SAVE TLD PRICING ────────────────────────────────────────────
    elif action_type in ('add_tld', 'save_tld'):
        tld = request.POST.get('tld', '').strip().lower()
        if not tld.startswith('.'):
            tld = '.' + tld
        register_price = Decimal(request.POST.get('register_price', '0.00'))
        renew_price = Decimal(request.POST.get('renew_price', '0.00'))
        transfer_price = Decimal(request.POST.get('transfer_price', str(register_price)))
        is_active = request.POST.get('is_active', 'on') == 'on'
        registrar_id = request.POST.get('registrar_id')

        reg_obj = None
        if registrar_id and registrar_id != 'none':
            reg_obj = DomainRegistrar.objects.filter(id=registrar_id).first()
        if not reg_obj:
            reg_obj = DomainRegistrar.objects.filter(is_default=True).first() or DomainRegistrar.objects.filter(is_active=True).first()

        TLDPricing.objects.update_or_create(
            tld=tld,
            defaults={
                'registrar': reg_obj,
                'register_price': register_price,
                'renew_price': renew_price,
                'transfer_price': transfer_price,
                'currency': 'BDT',
                'is_active': is_active,
            }
        )
        reg_name = reg_obj.name if reg_obj else "Default"
        messages.success(request, f"TLD Pricing for '{tld}' saved (Reg: ৳{register_price}, Renew: ৳{renew_price}, Provider: {reg_name}).")

    # ── 3b. EDIT TLD PRICING ──────────────────────────────────────────────────
    elif action_type == 'edit_tld':
        tld_id = request.POST.get('tld_id')
        tld_obj = get_object_or_404(TLDPricing, id=tld_id)
        tld_obj.register_price = Decimal(request.POST.get('register_price', str(tld_obj.register_price)))
        tld_obj.renew_price = Decimal(request.POST.get('renew_price', str(tld_obj.renew_price)))
        tld_obj.transfer_price = Decimal(request.POST.get('transfer_price', str(tld_obj.transfer_price)))
        tld_obj.is_active = request.POST.get('is_active') == 'on' or request.POST.get('is_active') == 'true'

        registrar_id = request.POST.get('registrar_id')
        if registrar_id:
            if registrar_id == 'none':
                tld_obj.registrar = None
            else:
                reg_obj = DomainRegistrar.objects.filter(id=registrar_id).first()
                if reg_obj:
                    tld_obj.registrar = reg_obj

        tld_obj.save()
        messages.success(request, f"TLD '{tld_obj.tld}' pricing updated (Provider: {tld_obj.registrar.name if tld_obj.registrar else 'Default'}).")

    # ── 3c. DELETE TLD PRICING ────────────────────────────────────────────────
    elif action_type == 'delete_tld':
        tld_id = request.POST.get('tld_id')
        tld_obj = get_object_or_404(TLDPricing, id=tld_id)
        name = tld_obj.tld
        tld_obj.delete()
        messages.success(request, f"TLD '{name}' deleted from catalogue.")

    # ── 3d. CLEAR / DELETE TLDs BY PROVIDER OR ALL ────────────────────────────
    elif action_type in ('clear_tlds', 'clear_all_tlds', 'delete_tlds_by_provider'):
        registrar_id = request.POST.get('registrar_id', 'all')
        if registrar_id == 'all' or not registrar_id:
            count = TLDPricing.objects.count()
            TLDPricing.objects.all().delete()
            messages.success(request, f"Successfully cleared all {count} TLD extensions from pricing catalogue.")
        else:
            reg_obj = DomainRegistrar.objects.filter(id=registrar_id).first()
            if reg_obj:
                count = TLDPricing.objects.filter(registrar=reg_obj).count()
                TLDPricing.objects.filter(registrar=reg_obj).delete()
                messages.success(request, f"Successfully deleted {count} TLD extensions assigned to '{reg_obj.name}'.")
            else:
                messages.error(request, "Selected registrar provider not found.")

    # ── 3e. SEED / IMPORT TLD CATALOGUE BY PROVIDER ───────────────────────────
    elif action_type in ('seed_bdwebs_tlds', 'seed_tlds', 'import_tlds'):
        registrar_id = request.POST.get('registrar_id')
        preset = request.POST.get('preset', 'all')
        clear_before = request.POST.get('clear_before') in ('on', '1', 'true')

        target_reg = None
        if registrar_id and registrar_id != 'default':
            target_reg = DomainRegistrar.objects.filter(id=registrar_id).first()
        if not target_reg:
            target_reg = DomainRegistrar.objects.filter(is_default=True).first() or DomainRegistrar.objects.filter(is_active=True).first()

        if clear_before:
            if target_reg:
                TLDPricing.objects.filter(registrar=target_reg).delete()
            else:
                TLDPricing.objects.all().delete()

        POPULAR_TLDS = [
            ('.com', '1350.00', '1350.00', '1350.00'),
            ('.net', '1450.00', '1450.00', '1450.00'),
            ('.org', '1500.00', '1500.00', '1500.00'),
            ('.info', '1650.00', '1650.00', '1650.00'),
            ('.biz', '1600.00', '1600.00', '1600.00'),
            ('.co', '2800.00', '2800.00', '2800.00'),
            ('.us', '1350.00', '1350.00', '1350.00'),
            ('.in', '1150.00', '1150.00', '1150.00'),
            ('.co.uk', '1250.00', '1250.00', '1250.00'),
        ]

        BD_CCTLD_TLDS = [
            ('.com.bd', '1800.00', '1800.00', '1800.00'),
            ('.org.bd', '1800.00', '1800.00', '1800.00'),
            ('.net.bd', '1800.00', '1800.00', '1800.00'),
            ('.edu.bd', '1800.00', '1800.00', '1800.00'),
            ('.ac.bd', '1800.00', '1800.00', '1800.00'),
            ('.gov.bd', '1800.00', '1800.00', '1800.00'),
            ('.bangla', '1800.00', '1800.00', '1800.00'),
            ('.bd', '2500.00', '2500.00', '2500.00'),
        ]

        BUDGET_PROMO_TLDS = [
            ('.xyz', '350.00', '1250.00', '1150.00'),
            ('.online', '450.00', '1550.00', '1450.00'),
            ('.site', '450.00', '1550.00', '1450.00'),
            ('.store', '450.00', '1850.00', '1750.00'),
            ('.shop', '550.00', '1950.00', '1850.00'),
            ('.top', '350.00', '850.00', '750.00'),
            ('.club', '650.00', '1500.00', '1400.00'),
        ]

        TECH_STARTUP_TLDS = [
            ('.tech', '650.00', '1950.00', '1850.00'),
            ('.app', '1950.00', '1950.00', '1950.00'),
            ('.dev', '1950.00', '1950.00', '1950.00'),
            ('.ai', '8500.00', '8500.00', '8500.00'),
            ('.io', '4800.00', '4800.00', '4800.00'),
            ('.agency', '1850.00', '2450.00', '2350.00'),
            ('.me', '1750.00', '1750.00', '1750.00'),
            ('.pro', '1650.00', '1650.00', '1650.00'),
        ]

        if preset == 'popular':
            target_list = POPULAR_TLDS
        elif preset == 'bd_cctld':
            target_list = BD_CCTLD_TLDS
        elif preset == 'budget_promo':
            target_list = BUDGET_PROMO_TLDS
        elif preset == 'tech_startup':
            target_list = TECH_STARTUP_TLDS
        else:
            target_list = POPULAR_TLDS + BUDGET_PROMO_TLDS + TECH_STARTUP_TLDS + BD_CCTLD_TLDS

        count = 0
        for ext, reg_p, ren_p, trans_p in target_list:
            TLDPricing.objects.update_or_create(
                tld=ext,
                defaults={
                    'registrar': target_reg,
                    'register_price': Decimal(reg_p),
                    'renew_price': Decimal(ren_p),
                    'transfer_price': Decimal(trans_p),
                    'currency': 'BDT',
                    'is_active': True,
                }
            )
            count += 1

        reg_display_name = target_reg.name if target_reg else "Default Provider"
        messages.success(request, f"Successfully imported {count} TLD extensions assigned to '{reg_display_name}' ({preset.upper()}) into pricing catalogue!")

    # ── 4a. SYNC PACKAGES FROM WHM (TWO-WAY INTEGRATION) ─────────────────────
    elif action_type == 'sync_whm_packages':
        server_id = request.POST.get('server_id')
        if server_id and server_id != 'all':
            servers = Server.objects.filter(id=server_id, is_active=True)
        else:
            servers = Server.objects.filter(is_active=True)

        if not servers.exists():
            messages.error(request, "No active WHM/cPanel servers configured to sync packages from.")
            return redirect_to_admin_tab(action_type, request)

        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        for srv in servers:
            try:
                driver = get_driver(srv)
                whm_packages = driver.list_packages()
                for p in whm_packages:
                    pkg_name = p.get('name', '').strip()
                    if not pkg_name:
                        continue

                    # Try to find existing HostingPackage for this server and plan
                    existing = HostingPackage.objects.filter(server=srv, panel_package_name=pkg_name).first()
                    if existing:
                        existing.disk_quota_mb = p.get('disk_quota_mb', existing.disk_quota_mb)
                        existing.bandwidth_mb = p.get('bandwidth_mb', existing.bandwidth_mb)
                        existing.is_active = True
                        existing.save(update_fields=['disk_quota_mb', 'bandwidth_mb', 'is_active', 'updated_at'])
                        total_updated += 1
                    else:
                        base_title = pkg_name.replace('_', ' ').replace('-', ' ').title()
                        candidate_name = base_title
                        if HostingPackage.objects.filter(name=candidate_name).exists():
                            candidate_name = f"{base_title} ({srv.name})"

                        HostingPackage.objects.create(
                            name=candidate_name,
                            server=srv,
                            panel_package_name=pkg_name,
                            monthly_price=Decimal('500.00'),
                            annual_price=Decimal('5000.00'),
                            disk_quota_mb=p.get('disk_quota_mb', 5120),
                            bandwidth_mb=p.get('bandwidth_mb', 51200),
                            is_featured=False,
                            is_active=True,
                        )
                        total_created += 1
                    total_synced += 1
            except Exception as exc:
                logger.exception("Error syncing packages for server %s: %s", srv.name, exc)
                errors.append(f"{srv.name}: {exc!s}")

        if total_synced > 0:
            msg = f"WHM Sync Complete: {total_synced} packages processed ({total_created} new imported, {total_updated} updated)!"
            if errors:
                msg += f" Note: {'; '.join(errors)}"
            messages.success(request, msg)
        else:
            if errors:
                messages.error(request, f"WHM package sync failed: {'; '.join(errors)}")
            else:
                messages.info(request, "No packages found on the WHM server to import.")

    # ── 4b. ADD HOSTING PACKAGE (HOSTPRO + OPTIONAL TWO-WAY WHM CREATE) ───────
    elif action_type == 'add_package':
        name = request.POST.get('name', '').strip()
        server_id = request.POST.get('server_id')
        panel_package_name = request.POST.get('package_name', '').strip() or request.POST.get('panel_package_name', '').strip() or request.POST.get('whm_package_name', '').strip()
        monthly_price = Decimal(request.POST.get('monthly_price', '0.00'))
        annual_price_val = request.POST.get('annual_price', '').strip()
        annual_price = Decimal(annual_price_val) if annual_price_val else monthly_price * 10
        disk_quota_mb = int(request.POST.get('disk_quota_mb', 5120))
        bandwidth_mb = int(request.POST.get('bandwidth_quota_mb', 0) or request.POST.get('bandwidth_mb', 0) or 51200)
        is_featured = request.POST.get('is_featured') == 'on'
        is_active = request.POST.get('is_active', 'on') == 'on'
        create_on_whm = request.POST.get('create_on_whm') in ('on', '1', 'true')

        if not name or not server_id or not panel_package_name:
            messages.error(request, "Package Name, WHM Server, and WHM Package Name are required.")
            return redirect_to_admin_tab(action_type, request)

        server = get_object_or_404(Server, id=server_id)

        # Two-way sync: Create package directly in WHM if requested
        if create_on_whm:
            try:
                driver = get_driver(server)
                driver.create_package(panel_package_name, disk_quota_mb=disk_quota_mb, bandwidth_mb=bandwidth_mb)
                messages.info(request, f"Two-way Sync: Package '{panel_package_name}' was created directly on WHM server '{server.name}'!")
            except Exception as exc:
                messages.warning(request, f"WHM panel notification: {exc!s}")

        HostingPackage.objects.create(
            name=name,
            server=server,
            panel_package_name=panel_package_name,
            monthly_price=monthly_price,
            annual_price=annual_price,
            disk_quota_mb=disk_quota_mb,
            bandwidth_mb=bandwidth_mb,
            is_featured=is_featured,
            is_active=is_active,
        )
        messages.success(request, f"Hosting Package '{name}' saved and linked to WHM plan '{panel_package_name}' on server '{server.name}'!")

    # ── 4c. EDIT HOSTING PACKAGE ──────────────────────────────────────────────
    elif action_type == 'edit_package':
        package_id = request.POST.get('package_id')
        pkg = get_object_or_404(HostingPackage, id=package_id)
        pkg.name = request.POST.get('name', pkg.name).strip()
        pkg.panel_package_name = request.POST.get('panel_package_name', pkg.panel_package_name).strip() or request.POST.get('package_name', pkg.panel_package_name).strip()
        pkg.monthly_price = Decimal(request.POST.get('monthly_price', str(pkg.monthly_price)))
        ann_val = request.POST.get('annual_price', '').strip()
        pkg.annual_price = Decimal(ann_val) if ann_val else pkg.monthly_price * 10
        pkg.disk_quota_mb = int(request.POST.get('disk_quota_mb', pkg.disk_quota_mb))
        pkg.bandwidth_mb = int(request.POST.get('bandwidth_mb', pkg.bandwidth_mb))
        pkg.is_featured = request.POST.get('is_featured') == 'on'
        pkg.is_active = request.POST.get('is_active') == 'on'
        pkg.save()
        messages.success(request, f"Hosting Package '{pkg.name}' updated successfully.")

    # ── 4d. DELETE HOSTING PACKAGE (OPTIONAL WHM REMOVAL) ─────────────────────
    elif action_type == 'delete_package':
        package_id = request.POST.get('package_id')
        pkg = get_object_or_404(HostingPackage, id=package_id)
        pkg_name = pkg.name
        delete_from_whm = request.POST.get('delete_from_whm') in ('on', '1', 'true')

        if pkg.accounts.filter(status=HostingAccount.Status.ACTIVE).exists():
            messages.error(request, f"Cannot delete package '{pkg_name}' because active client accounts are using it.")
        else:
            if delete_from_whm:
                try:
                    driver = get_driver(pkg.server)
                    driver.delete_package(pkg.panel_package_name)
                    messages.info(request, f"Removed plan '{pkg.panel_package_name}' from WHM server.")
                except Exception as exc:
                    messages.warning(request, f"WHM package removal note: {exc!s}")
            pkg.delete()
            messages.success(request, f"Hosting Package '{pkg_name}' deleted.")

    # ── 5a. CREATE / PROVISION MANUAL HOSTING ACCOUNT ─────────────────────────
    elif action_type == 'create_hosting_account':
        user_email = request.POST.get('user_email', '').strip()
        domain_name = request.POST.get('domain', '').strip().lower()
        server_id = request.POST.get('server_id')
        package_id = request.POST.get('package_id')
        custom_username = request.POST.get('username', '').strip().lower()
        custom_password = request.POST.get('password', '').strip()
        auto_provision_now = request.POST.get('auto_provision') in ('on', '1', 'true')

        if not user_email or not domain_name or not server_id or not package_id:
            messages.error(request, "Client Email, Domain Name, Server, and Package are required.")
            return redirect_to_admin_tab(action_type, request)

        # Find or create user
        target_user = User.objects.filter(email__iexact=user_email).first()
        if not target_user:
            target_user = User.objects.create_user(
                email=user_email,
                first_name=user_email.split('@')[0].capitalize(),
                last_name='Client',
                password=custom_password or 'ClientPass123!',
                role=User.Role.CLIENT,
            )
            ClientProfile.objects.create(user=target_user)

        server = get_object_or_404(Server, id=server_id)
        package = get_object_or_404(HostingPackage, id=package_id)

        billing_cycle = request.POST.get('billing_cycle', BillingCycle.MONTHLY)
        custom_next_due_str = request.POST.get('next_due_date', '').strip()
        custom_amount_str = request.POST.get('amount', '').strip()

        # Calculate next_due_date
        days_map = {
            'monthly': 30,
            'quarterly': 90,
            'semi_annual': 180,
            'annual': 365,
            'biennial': 730,
            'triennial': 1095,
        }
        today = timezone.now().date()
        if custom_next_due_str:
            from datetime import datetime
            try:
                due_date = datetime.strptime(custom_next_due_str, '%Y-%m-%d').date()
            except ValueError:
                due_date = today + timezone.timedelta(days=days_map.get(billing_cycle, 30))
        else:
            due_date = today + timezone.timedelta(days=days_map.get(billing_cycle, 30))

        # Determine price amount
        if custom_amount_str:
            try:
                price_amount = Decimal(custom_amount_str)
            except Exception:
                price_amount = package.monthly_price
        else:
            if billing_cycle == 'annual' and package.annual_price:
                price_amount = package.annual_price
            elif billing_cycle == 'biennial' and getattr(package, 'annual_price', None):
                price_amount = package.annual_price * 2
            elif billing_cycle == 'triennial' and getattr(package, 'annual_price', None):
                price_amount = package.annual_price * 3
            else:
                price_amount = package.monthly_price

        clean_user = custom_username or ProvisioningService.generate_cpanel_username(domain_name)
        plain_pass = custom_password or ProvisioningService.generate_secure_password()

        account = HostingAccount.objects.create(
            user=target_user,
            package=package,
            server=server,
            domain=domain_name,
            username=clean_user,
            status=HostingAccount.Status.ACTIVE if auto_provision_now else HostingAccount.Status.PENDING,
            billing_cycle=billing_cycle,
            amount=price_amount,
            next_due_date=due_date,
        )
        account.set_account_password(plain_pass)
        account.save()

        if auto_provision_now:
            try:
                driver = get_driver(server)
                driver.create_account(
                    domain=domain_name,
                    username=clean_user,
                    password=plain_pass,
                    package_name=package.panel_package_name,
                    email=target_user.email,
                )
                account.provisioned_at = timezone.now()
                account.save(update_fields=['provisioned_at'])
                messages.success(request, f"Hosting account '{domain_name}' created & provisioned on WHM! Expiry: {account.next_due_date} ({account.get_billing_cycle_display()})")
            except Exception as exc:
                account.status = HostingAccount.Status.PENDING
                account.save(update_fields=['status'])
                messages.warning(request, f"Account saved locally, but WHM provisioning returned: {exc!s}")
        else:
            messages.success(request, f"Hosting account for '{domain_name}' created in PENDING status. Expiry: {account.next_due_date}")

    # ── 5b. HOSTING ACCOUNT ACTIONS (SUSPEND / UNSUSPEND / TERMINATE / PROVISION / PASSWORD / EMAIL / EDIT)
    elif action_type in ('account_action', 'hosting_account_action', 'edit_hosting_account'):
        account_id = request.POST.get('account_id')
        sub_action = request.POST.get('sub_action') or request.POST.get('action') or ('edit' if action_type == 'edit_hosting_account' else None)
        account = get_object_or_404(HostingAccount, id=account_id)

        if sub_action == 'edit':
            package_id = request.POST.get('package_id')
            billing_cycle = request.POST.get('billing_cycle')
            next_due_str = request.POST.get('next_due_date', '').strip()
            status_val = request.POST.get('status')
            amount_str = request.POST.get('amount', '').strip()

            if package_id:
                new_pkg = HostingPackage.objects.filter(id=package_id).first()
                if new_pkg and new_pkg != account.package:
                    try:
                        driver = get_driver(account.server)
                        driver.change_package(account.username, new_pkg.panel_package_name)
                    except Exception as exc:
                        logger.warning("WHM changepackage: %s", exc)
                    account.package = new_pkg

            if billing_cycle in dict(BillingCycle.choices):
                account.billing_cycle = billing_cycle

            if next_due_str:
                from datetime import datetime
                try:
                    account.next_due_date = datetime.strptime(next_due_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            if status_val in dict(HostingAccount.Status.choices):
                account.status = status_val

            if amount_str:
                try:
                    account.amount = Decimal(amount_str)
                except Exception:
                    pass

            account.save()
            messages.success(request, f"Hosting account '{account.domain}' updated! Expiry: {account.next_due_date} ({account.get_billing_cycle_display()})")

        if sub_action == 'provision':
            account.status = HostingAccount.Status.ACTIVE
            account.provisioned_at = timezone.now()
            if not account.next_due_date:
                account.next_due_date = timezone.now().date() + timezone.timedelta(days=30)
            account.save(update_fields=['status', 'provisioned_at', 'next_due_date'])
            try:
                driver = get_driver(account.server)
                import secrets
                plain_pass = secrets.token_urlsafe(14)
                driver.create_account(
                    domain=account.domain,
                    username=account.username,
                    password=plain_pass,
                    package_name=account.package.panel_package_name,
                    email=account.user.email,
                )
                messages.success(request, f"Account '{account.domain}' provisioned successfully on WHM server '{account.server.name}'! (Password: {plain_pass})")
            except Exception as exc:
                messages.warning(request, f"Provisioning dispatched locally, WHM response: {exc!s}")

        elif sub_action == 'change_password':
            new_password = request.POST.get('new_password', '').strip() or request.POST.get('password', '').strip()
            if not new_password:
                messages.error(request, "New password cannot be empty.")
                return redirect_to_admin_tab(action_type, request)
            try:
                driver = get_driver(account.server)
                driver.change_password(account.username, new_password)
                messages.success(request, f"Password for cPanel account '{account.username}' ({account.domain}) updated on WHM!")
            except Exception as exc:
                messages.error(request, f"Failed to change password on WHM: {exc!s}")

        elif sub_action == 'change_email':
            new_email = request.POST.get('new_email', '').strip().lower() or request.POST.get('email', '').strip().lower()
            if not new_email:
                messages.error(request, "New contact email cannot be empty.")
                return redirect_to_admin_tab(action_type, request)
            try:
                driver = get_driver(account.server)
                driver.change_email(account.username, new_email)
                # Also update user email if requested
                if request.POST.get('update_user_email') in ('on', '1', 'true'):
                    account.user.email = new_email
                    account.user.save(update_fields=['email'])
                messages.success(request, f"Contact email for '{account.username}' ({account.domain}) updated to '{new_email}' on WHM!")
            except Exception as exc:
                messages.error(request, f"Failed to change email on WHM: {exc!s}")

        elif sub_action == 'suspend':
            reason = request.POST.get('reason', '').strip() or 'Suspended by Administrator for Non-Payment'
            try:
                driver = get_driver(account.server)
                driver.suspend_account(account.username, reason=reason)
                account.status = HostingAccount.Status.SUSPENDED
                account.save(update_fields=['status'])
                messages.warning(request, f"Hosting account '{account.domain}' has been SUSPENDED on WHM. Reason: {reason}")
            except Exception as exc:
                account.status = HostingAccount.Status.SUSPENDED
                account.save(update_fields=['status'])
                messages.warning(request, f"Account '{account.domain}' marked SUSPENDED locally: {exc}")

        elif sub_action == 'unsuspend':
            try:
                driver = get_driver(account.server)
                driver.unsuspend_account(account.username)
                account.status = HostingAccount.Status.ACTIVE
                account.save(update_fields=['status'])
                messages.success(request, f"Hosting account '{account.domain}' has been UNSUSPENDED on WHM.")
            except Exception as exc:
                account.status = HostingAccount.Status.ACTIVE
                account.save(update_fields=['status'])
                messages.warning(request, f"Account '{account.domain}' marked ACTIVE locally: {exc}")

        elif sub_action == 'terminate':
            try:
                driver = get_driver(account.server)
                driver.terminate_account(account.username)
                messages.warning(request, f"Hosting account '{account.domain}' ({account.username}) terminated from WHM server '{account.server.name}'.")
            except Exception as exc:
                logger.warning("WHM terminate call: %s", exc)
                messages.warning(request, f"WHM termination notice: {exc!s}")
            account.status = HostingAccount.Status.TERMINATED
            account.save(update_fields=['status'])
            messages.error(request, f"Hosting account '{account.domain}' status updated to TERMINATED.")

        elif sub_action == 'delete' or action_type == 'delete_hosting_account':
            delete_from_server = request.POST.get('delete_from_server') in ('on', '1', 'true')
            if delete_from_server:
                try:
                    driver = get_driver(account.server)
                    driver.terminate_account(account.username)
                    messages.info(request, f"Removed '{account.username}' from WHM server.")
                except Exception as exc:
                    messages.warning(request, f"WHM removal notice: {exc!s}")
            dom_title = account.domain
            Invoice.objects.filter(hosting_account=account).update(hosting_account=None)
            account.delete()
            messages.success(request, f"Hosting account '{dom_title}' deleted permanently from database.")

    # ── 5c. SYNC ACCOUNTS FROM WHM (TWO-WAY INTEGRATION) ─────────────────────

    elif action_type == 'sync_whm_accounts':
        server_id = request.POST.get('server_id')
        if server_id and server_id != 'all':
            servers = Server.objects.filter(id=server_id, is_active=True)
        else:
            servers = Server.objects.filter(is_active=True)

        if not servers.exists():
            messages.error(request, "No active WHM/cPanel servers configured to sync accounts from.")
            return redirect_to_admin_tab(action_type, request)

        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        for srv in servers:
            try:
                driver = get_driver(srv)
                whm_accounts = driver.list_accounts()
                for a in whm_accounts:
                    uname = a.get('username', '').strip()
                    dom = a.get('domain', '').strip().lower()
                    email = a.get('email', '').strip().lower()
                    plan = a.get('plan', '').strip()
                    is_suspended = a.get('is_suspended', False)

                    if not uname or not dom:
                        continue

                    # Find or create client user
                    clean_email = email if (email and email not in ('*unknown*', 'unknown', 'none', '')) else f"contact@{dom}"
                    client_user = User.objects.filter(email__iexact=clean_email).first()
                    if not client_user:
                        client_user = User.objects.create_user(
                            email=clean_email,
                            first_name=uname.capitalize(),
                            last_name='Client',
                            password='ClientPass123!',
                            role=User.Role.CLIENT,
                        )
                        ClientProfile.objects.create(user=client_user, company_name=dom)

                    # Find or link package
                    pkg = HostingPackage.objects.filter(server=srv, panel_package_name=plan).first()
                    if not pkg:
                        pkg = HostingPackage.objects.filter(server=srv).first()
                    if not pkg:
                        pkg = HostingPackage.objects.create(
                            name=f"{plan.title() or 'Default'} ({srv.name})",
                            server=srv,
                            panel_package_name=plan or 'default',
                            monthly_price=Decimal('500.00'),
                            annual_price=Decimal('5000.00'),
                            disk_quota_mb=5120,
                            bandwidth_mb=51200,
                            is_active=True,
                        )

                    today = timezone.now().date()
                    acct = HostingAccount.objects.filter(server=srv, username=uname).first()
                    if not acct:
                        acct = HostingAccount.objects.filter(domain=dom).first()

                    if acct:
                        acct.server = srv
                        acct.username = uname
                        acct.domain = dom
                        if not acct.user or acct.user.is_staff or acct.user.email in ('*unknown*', 'unknown'):
                            acct.user = client_user
                        if pkg:
                            acct.package = pkg
                        acct.status = HostingAccount.Status.SUSPENDED if is_suspended else HostingAccount.Status.ACTIVE
                        if not acct.next_due_date:
                            acct.next_due_date = today + timezone.timedelta(days=30)
                        acct.save()
                        total_updated += 1
                    else:
                        HostingAccount.objects.create(
                            user=client_user,
                            package=pkg,
                            server=srv,
                            domain=dom,
                            username=uname,
                            billing_cycle=BillingCycle.MONTHLY,
                            amount=pkg.monthly_price if pkg else Decimal('500.00'),
                            status=HostingAccount.Status.SUSPENDED if is_suspended else HostingAccount.Status.ACTIVE,
                            provisioned_at=timezone.now(),
                            next_due_date=today + timezone.timedelta(days=30),
                        )
                        total_created += 1
                    total_synced += 1

            except Exception as exc:
                logger.exception("Error syncing WHM accounts for server %s: %s", srv.name, exc)
                errors.append(f"{srv.name}: {exc!s}")

        if total_synced > 0:
            msg = f"WHM Accounts Sync Complete: {total_synced} accounts processed ({total_created} newly imported, {total_updated} synchronized)!"
            if errors:
                msg += f" Note: {'; '.join(errors)}"
            messages.success(request, msg)
        else:
            if errors:
                messages.error(request, f"WHM account sync failed: {'; '.join(errors)}")
            else:
                messages.info(request, "No accounts found on the WHM server to import.")

    # ── 6a. REGISTER / ADD DOMAIN RECORD ──────────────────────────────────────
    elif action_type == 'add_domain_order':
        user_email = request.POST.get('user_email', '').strip()
        domain_name = request.POST.get('domain_name', '').strip().lower()
        registrar_id = request.POST.get('registrar_id')
        years = int(request.POST.get('registration_years', 1))
        auto_provision = request.POST.get('auto_provision') in ('on', '1', 'true')

        target_user = User.objects.filter(email__iexact=user_email).first()
        if not target_user:
            target_user = User.objects.create_user(
                email=user_email,
                first_name=user_email.split('@')[0].capitalize(),
                last_name='Client',
                password='ClientPass123!',
                role=User.Role.CLIENT,
            )
            ClientProfile.objects.create(user=target_user)

        registrar = DomainRegistrar.objects.filter(id=registrar_id).first() if registrar_id else DomainRegistrar.objects.filter(is_default=True).first()

        dom = Domain.objects.create(
            user=target_user,
            registrar=registrar,
            domain_name=domain_name,
            registration_years=years,
            status=Domain.Status.ACTIVE if auto_provision else Domain.Status.PENDING,
            registration_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timezone.timedelta(days=365 * years),
            next_due_date=timezone.now().date() + timezone.timedelta(days=365 * years),
        )

        if auto_provision and registrar:
            try:
                DomainService.provision_domain(str(dom.id))
                messages.success(request, f"Domain '{domain_name}' registered via {registrar.name} API!")
            except Exception as exc:
                messages.warning(request, f"Domain created locally, but registrar returned: {exc!s}")
        else:
            messages.success(request, f"Domain record for '{domain_name}' saved.")

    # ── 6b. DOMAIN ACTION (REGISTER AT REGISTRAR NOW) ─────────────────────────
    elif action_type == 'domain_action':
        domain_id = request.POST.get('domain_id')
        domain = get_object_or_404(Domain, id=domain_id)
        try:
            DomainService.provision_domain(str(domain.id))
            messages.success(request, f"Domain '{domain.domain_name}' registered successfully via Registrar API!")
        except Exception as exc:
            messages.error(request, f"Failed to register '{domain.domain_name}': {exc!s}")

    # ── 6c. EDIT DOMAIN / EXTEND OR REDUCE VALIDITY (MEYAD) ───────────────────
    elif action_type == 'edit_domain':
        domain_id = request.POST.get('domain_id')
        dom = get_object_or_404(Domain, id=domain_id)

        reg_years_str = request.POST.get('registration_years', '').strip()
        reg_date_str = request.POST.get('registration_date', '').strip()
        exp_date_str = request.POST.get('expiry_date', '').strip()
        next_due_str = request.POST.get('next_due_date', '').strip()
        status_val = request.POST.get('status', '').strip()
        auto_renew = request.POST.get('auto_renew') in ('on', '1', 'true')
        registrar_id = request.POST.get('registrar_id')
        ns1 = request.POST.get('nameserver_1', '').strip()
        ns2 = request.POST.get('nameserver_2', '').strip()

        if reg_years_str:
            try:
                dom.registration_years = max(1, int(reg_years_str))
            except ValueError:
                pass

        from datetime import datetime
        if reg_date_str:
            try:
                dom.registration_date = datetime.strptime(reg_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if exp_date_str:
            try:
                dom.expiry_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date()
                if not next_due_str:
                    dom.next_due_date = dom.expiry_date
            except ValueError:
                pass

        if next_due_str:
            try:
                dom.next_due_date = datetime.strptime(next_due_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if status_val in dict(Domain.Status.choices):
            dom.status = status_val

        dom.auto_renew = auto_renew

        if registrar_id:
            reg_obj = DomainRegistrar.objects.filter(id=registrar_id).first()
            if reg_obj:
                dom.registrar = reg_obj

        if ns1:
            dom.nameserver_1 = ns1
        if ns2:
            dom.nameserver_2 = ns2

        dom.save()
        messages.success(request, f"Domain '{dom.domain_name}' updated! New Expiry Date (মেয়াদ): {dom.expiry_date} ({dom.registration_years} Yr(s)).")

    # ── 6d. DELETE DOMAIN RECORD ──────────────────────────────────────────────
    elif action_type == 'delete_domain':
        domain_id = request.POST.get('domain_id')
        domain = get_object_or_404(Domain, id=domain_id)
        d_name = domain.domain_name
        Invoice.objects.filter(domain=domain).update(domain=None)
        domain.delete()
        messages.success(request, f"Domain record for '{d_name}' deleted permanently.")


    # ── 6c. SYNC DOMAINS FROM REGISTRAR (TWO-WAY INTEGRATION) ─────────────────
    elif action_type == 'sync_registrar_domains':
        registrar_id = request.POST.get('registrar_id')
        if registrar_id and registrar_id != 'all':
            registrars = DomainRegistrar.objects.filter(id=registrar_id, is_active=True)
        else:
            registrars = DomainRegistrar.objects.filter(is_active=True)

        if not registrars.exists():
            messages.error(request, "No active domain registrars configured to sync domains from.")
            return redirect_to_admin_tab(action_type, request)

        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        default_client = User.objects.filter(role=User.Role.CLIENT).first() or request.user

        for reg in registrars:
            try:
                driver = get_registrar_driver(reg)
                if hasattr(driver, 'list_domains'):
                    domains_list = driver.list_domains()
                    for d in domains_list:
                        dname = (d.get('domain') or d.get('domainname') or d.get('name') or '').strip().lower()
                        if not dname:
                            continue

                        exp_str = d.get('expiry_date') or d.get('expirydate') or d.get('expires_at') or d.get('nextduedate')
                        status_str = (d.get('status') or 'active').lower()

                        from datetime import datetime
                        exp_date = None
                        if exp_str:
                            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y'):
                                try:
                                    exp_date = datetime.strptime(str(exp_str).strip()[:10], fmt).date()
                                    break
                                except Exception:
                                    pass

                        dom_obj = Domain.objects.filter(domain_name=dname).first()
                        if dom_obj:
                            dom_obj.registrar = reg
                            if exp_date:
                                dom_obj.expiry_date = exp_date
                                dom_obj.next_due_date = exp_date
                            dom_obj.status = Domain.Status.ACTIVE if status_str == 'active' else Domain.Status.SUSPENDED
                            dom_obj.save()
                            total_updated += 1
                        else:
                            Domain.objects.create(
                                user=default_client,
                                registrar=reg,
                                domain_name=dname,
                                registration_years=1,
                                status=Domain.Status.ACTIVE if status_str == 'active' else Domain.Status.PENDING,
                                registration_date=timezone.now().date(),
                                expiry_date=exp_date or (timezone.now().date() + timezone.timedelta(days=365)),
                                next_due_date=exp_date or (timezone.now().date() + timezone.timedelta(days=365)),
                                auto_renew=True,
                            )
                            total_created += 1
                        total_synced += 1
                else:
                    errors.append(f"{reg.name}: list_domains not supported by driver")
            except Exception as exc:
                logger.exception("Error syncing domains from %s: %s", reg.name, exc)
                errors.append(f"{reg.name}: {exc!s}")

        if total_synced > 0:
            msg = f"Domain Sync Complete: {total_synced} domains processed ({total_created} newly imported, {total_updated} synchronized)!"
            if errors:
                msg += f" Note: {'; '.join(errors)}"
            messages.success(request, msg)
        else:
            if errors:
                messages.error(request, f"Domain sync failed: {'; '.join(errors)}")
            else:
                messages.info(request, "No registered domains returned from the Registrar API.")

    # ── 7a. CREATE MANUAL INVOICE ─────────────────────────────────────────────
    elif action_type == 'create_invoice':
        user_email = request.POST.get('user_email', '').strip()
        description = request.POST.get('description', 'Hosting & Cloud Services').strip()
        amount = Decimal(request.POST.get('amount', '0.00'))
        invoice_type = request.POST.get('invoice_type', Invoice.InvoiceType.HOSTING)
        mark_as_paid = request.POST.get('mark_as_paid') in ('on', '1', 'true')

        target_user = User.objects.filter(email__iexact=user_email).first()
        if not target_user:
            messages.error(request, f"Client with email '{user_email}' not found.")
            return redirect_to_admin_tab(action_type, request)

        today = timezone.now().date()
        inv_number = f"INV-{uuid.uuid4().hex[:6].upper()}"
        inv = Invoice.objects.create(
            invoice_number=inv_number,
            user=target_user,
            invoice_type=invoice_type,
            status=Invoice.Status.PAID if mark_as_paid else Invoice.Status.UNPAID,
            subtotal=amount,
            total=amount,
            issued_date=today,
            due_date=today + timezone.timedelta(days=7),
            paid_at=timezone.now() if mark_as_paid else None,
        )
        InvoiceItem.objects.create(
            invoice=inv,
            description=description,
            quantity=Decimal('1.00'),
            unit_price=amount,
            line_total=amount,
        )
        if mark_as_paid:
            Transaction.objects.create(
                invoice=inv,
                user=target_user,
                gateway=Gateway.MANUAL,
                status=Transaction.Status.SUCCESS,
                gateway_transaction_id=f"MANUAL-{uuid.uuid4().hex[:8].upper()}",
                amount=amount,
                gateway_response={'operator': request.user.email, 'type': 'manual_admin_creation'}
            )
        messages.success(request, f"Invoice #{inv_number} created for '{target_user.email}' (৳{amount}).")

    # ── 7b. INVOICE / ORDER ACTION (APPROVE & AUTOMATICALLY PROVISION DOMAIN & HOSTING)
    elif action_type in ('approve_order', 'mark_invoice_paid', 'invoice_action'):
        invoice_id = request.POST.get('invoice_id')
        invoice = get_object_or_404(Invoice, id=invoice_id)

        if invoice.status != Invoice.Status.PAID:
            # Settle any pending manual payment transaction submitted by the client
            pending_txns = Transaction.objects.filter(invoice=invoice, status=Transaction.Status.PENDING)
            if pending_txns.exists():
                for p_txn in pending_txns:
                    p_txn.status = Transaction.Status.SUCCESS
                    resp = p_txn.gateway_response or {}
                    resp['approved_by'] = request.user.email
                    resp['approved_at'] = timezone.now().isoformat()
                    p_txn.gateway_response = resp
                    p_txn.save(update_fields=['status', 'gateway_response', 'updated_at'])
            else:
                Transaction.objects.create(
                    invoice=invoice,
                    user=invoice.user,
                    gateway=Gateway.MANUAL,
                    status=Transaction.Status.SUCCESS,
                    gateway_transaction_id=f"ADMIN-APPROVE-{uuid.uuid4().hex[:8].upper()}",
                    amount=invoice.total,
                    gateway_response={'channel': 'admin_custom_dashboard', 'operator': request.user.email, 'type': 'admin_order_approval'},
                )
            invoice.mark_paid()
            invoice.save(update_fields=['status', 'paid_at', 'updated_at'])

            provision_reports = []

            # 1. Automatic Hosting Account Provisioning on WHM / cPanel
            if invoice.hosting_account:
                acct = invoice.hosting_account
                cycle_days = {
                    'monthly': 30,
                    'quarterly': 90,
                    'semi_annual': 180,
                    'annual': 365,
                    'biennial': 730,
                    'triennial': 1095,
                }
                days = cycle_days.get(acct.billing_cycle, 30)
                try:
                    driver = get_driver(acct.server)
                    plain_pass = acct.get_account_password() or ProvisioningService.generate_secure_password()
                    driver.create_account(
                        domain=acct.domain,
                        username=acct.username,
                        password=plain_pass,
                        package_name=acct.package.panel_package_name,
                        email=acct.user.email,
                    )
                    acct.status = HostingAccount.Status.ACTIVE
                    acct.provisioned_at = timezone.now()
                    if not acct.next_due_date:
                        acct.next_due_date = timezone.now().date() + timezone.timedelta(days=days)
                    acct.save(update_fields=['status', 'provisioned_at', 'next_due_date'])
                    provision_reports.append(f"✓ Hosting '{acct.domain}' created on cPanel ({acct.server.name})")
                except Exception as exc:
                    logger.warning("Synchronous cPanel provisioning note for %s: %s", acct.domain, exc)
                    # Mark active and fallback to Celery async queue
                    acct.status = HostingAccount.Status.ACTIVE
                    acct.provisioned_at = timezone.now()
                    if not acct.next_due_date:
                        acct.next_due_date = timezone.now().date() + timezone.timedelta(days=days)
                    acct.save(update_fields=['status', 'provisioned_at', 'next_due_date'])
                    try:
                        provision_hosting_account.delay(str(acct.id))
                    except Exception:
                        pass
                    provision_reports.append(f"✓ Hosting '{acct.domain}' activated ({exc!s})")

            # 2. Automatic Domain Registration via Wholesale Registrar API
            if invoice.domain:
                dom = invoice.domain
                years = dom.registration_years or 1
                try:
                    DomainService.provision_domain(str(dom.id))
                    provision_reports.append(f"✓ Domain '{dom.domain_name}' registered via Wholesale Registrar API")
                except Exception as exc:
                    logger.error("Admin invoice domain auto-provision failed: %s", exc)
                    dom.status = Domain.Status.ACTIVE
                    dom.registration_date = timezone.now().date()
                    dom.expiry_date = timezone.now().date() + timezone.timedelta(days=365 * years)
                    dom.next_due_date = dom.expiry_date
                    dom.save(update_fields=['status', 'registration_date', 'expiry_date', 'next_due_date'])
                    provision_reports.append(f"✓ Domain '{dom.domain_name}' activated ({exc!s})")

            summary_text = " | ".join(provision_reports) if provision_reports else "Payment confirmed & activated"
            messages.success(request, f"Order #{invoice.invoice_number} APPROVED! {summary_text}")
        else:
            messages.info(request, f"Invoice #{invoice.invoice_number} was already settled.")


    # ── 7c. DELETE INVOICE / ORDER ───────────────────────────────────────────
    elif action_type == 'delete_invoice':
        invoice_id = request.POST.get('invoice_id')
        invoice = get_object_or_404(Invoice, id=invoice_id)
        inv_num = invoice.invoice_number
        invoice.items.all().delete()
        invoice.transactions.all().delete()
        invoice.delete()
        messages.success(request, f"Invoice #{inv_num} and associated records deleted permanently.")

    # ── 7d. CANCEL INVOICE ───────────────────────────────────────────────────
    elif action_type == 'cancel_invoice':
        invoice_id = request.POST.get('invoice_id')
        invoice = get_object_or_404(Invoice, id=invoice_id)
        invoice.status = Invoice.Status.CANCELLED
        invoice.save(update_fields=['status'])
        messages.warning(request, f"Invoice #{invoice.invoice_number} marked as CANCELLED.")

    # ── 8a. ADD NEW CLIENT ───────────────────────────────────────────────────
    elif action_type == 'add_client':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company_name', '').strip()
        password = request.POST.get('password', '').strip() or 'ClientPass123!'
        credit = Decimal(request.POST.get('credit_balance', '0.00'))

        if not email or not first_name:
            messages.error(request, "Email and First Name are required.")
            return redirect_to_admin_tab(action_type, request)

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, f"User with email '{email}' already exists.")
            return redirect_to_admin_tab(action_type, request)

        new_user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name or 'Client',
            password=password,
            role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(
            user=new_user,
            phone=phone,
            company_name=company,
            credit_balance=credit,
        )
        messages.success(request, f"Client '{new_user.get_full_name()}' ({email}) registered successfully!")

    # ── 8b. CLIENT WALLET CREDIT ADJUSTMENT ───────────────────────────────────
    elif action_type in ('adjust_wallet', 'adjust_credit'):
        user_id = request.POST.get('client_id') or request.POST.get('user_id')
        amount = Decimal(request.POST.get('amount', '0.00'))
        target_user = get_object_or_404(User, id=user_id)
        profile, _ = ClientProfile.objects.get_or_create(user=target_user)

        profile.credit_balance += amount
        profile.credit_balance = max(profile.credit_balance, Decimal('0.00'))
        profile.save(update_fields=['credit_balance'])

        messages.success(
            request,
            f"Wallet credit for '{target_user.email}' updated by ৳{amount}. New Balance: ৳{profile.credit_balance}"
        )

    # ── 8c. EDIT CLIENT & RESET PASSWORD ─────────────────────────────────────
    elif action_type == 'edit_client':
        client_id = request.POST.get('client_id')
        target_user = get_object_or_404(User, id=client_id)

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company_name', '').strip()
        role = request.POST.get('role', target_user.role)
        is_active = request.POST.get('is_active') in ('on', '1', 'true')
        new_password = request.POST.get('new_password', '').strip()

        if email and email != target_user.email:
            if User.objects.filter(email__iexact=email).exclude(id=target_user.id).exists():
                messages.error(request, f"Email address '{email}' is already taken by another user.")
                return redirect_to_admin_tab(action_type, request)
            target_user.email = email

        if first_name:
            target_user.first_name = first_name
        if last_name:
            target_user.last_name = last_name

        if role in dict(User.Role.choices):
            target_user.role = role
        target_user.is_active = is_active

        if new_password:
            target_user.set_password(new_password)

        target_user.save()

        profile, _ = ClientProfile.objects.get_or_create(user=target_user)
        profile.phone = phone
        profile.company_name = company
        profile.save()

        pass_note = " (Password reset successfully)" if new_password else ""
        messages.success(request, f"Client profile for '{target_user.email}' updated successfully!{pass_note}")

    # ── 8d. DELETE CLIENT ────────────────────────────────────────────────────
    elif action_type == 'delete_client':
        client_id = request.POST.get('client_id')
        target_user = get_object_or_404(User, id=client_id)
        if target_user == request.user or target_user.is_superuser:
            messages.error(request, "Cannot delete superadmin or your own account.")
            return redirect_to_admin_tab(action_type, request)

        email = target_user.email
        # Delete related transactions & invoices to prevent ProtectedError
        inv_ids = list(target_user.invoices.values_list('id', flat=True))
        Transaction.objects.filter(invoice_id__in=inv_ids).delete()
        Transaction.objects.filter(user=target_user).delete()
        InvoiceItem.objects.filter(invoice_id__in=inv_ids).delete()
        target_user.invoices.all().delete()
        target_user.hosting_accounts.all().delete()
        target_user.domains.all().delete()

        if hasattr(target_user, 'profile'):
            target_user.profile.delete()
        target_user.delete()
        messages.success(request, f"Client '{email}' and all associated records deleted permanently.")

    # ── 9. UPDATE SITE & SEO SETTINGS (BRANDING, LOGO, WHATSAPP, OG THUMBNAIL, SOCIAL) ───
    elif action_type in ('update_site_settings', 'save_site_settings', 'save_settings'):
        site = SiteSetting.get_settings()
        site.site_title = request.POST.get('site_title', site.site_title).strip()
        site.company_name = request.POST.get('company_name', site.company_name).strip()
        site.tagline = request.POST.get('tagline', site.tagline).strip()
        site.meta_description = request.POST.get('meta_description', site.meta_description).strip()
        site.meta_keywords = request.POST.get('meta_keywords', site.meta_keywords).strip()

        site.whatsapp_number = request.POST.get('whatsapp_number', site.whatsapp_number).strip()
        site.support_email = request.POST.get('support_email', site.support_email).strip()
        site.support_phone = request.POST.get('support_phone', site.support_phone).strip()
        site.office_address = request.POST.get('office_address', site.office_address).strip()

        site.facebook_url = request.POST.get('facebook_url', site.facebook_url).strip()
        site.youtube_url = request.POST.get('youtube_url', site.youtube_url).strip()
        site.linkedin_url = request.POST.get('linkedin_url', site.linkedin_url).strip()
        site.instagram_url = request.POST.get('instagram_url', site.instagram_url).strip()
        site.twitter_url = request.POST.get('twitter_url', site.twitter_url).strip()
        site.telegram_url = request.POST.get('telegram_url', site.telegram_url).strip()

        # Direct Image URL inputs
        logo_url_input = request.POST.get('logo_url', '').strip()
        favicon_url_input = request.POST.get('favicon_url', '').strip()
        thumbnail_url_input = request.POST.get('thumbnail_url', '').strip()
        if logo_url_input:
            site.logo_url = logo_url_input
        if favicon_url_input:
            site.favicon_url = favicon_url_input
        if thumbnail_url_input:
            site.thumbnail_url = thumbnail_url_input

        # Handle Direct Image File Uploads
        import os
        from django.conf import settings as dj_settings
        static_img_dir = os.path.join(dj_settings.BASE_DIR, 'static', 'img')
        staticfiles_img_dir = os.path.join(dj_settings.BASE_DIR, 'staticfiles', 'img')
        os.makedirs(static_img_dir, exist_ok=True)
        os.makedirs(staticfiles_img_dir, exist_ok=True)

        if request.FILES.get('logo_file'):
            f = request.FILES['logo_file']
            ext = os.path.splitext(f.name)[1] or '.png'
            filename = f"logo{ext}"
            for d in (static_img_dir, staticfiles_img_dir):
                file_path = os.path.join(d, filename)
                with open(file_path, 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)
            site.logo_url = f"/static/img/{filename}"

        if request.FILES.get('favicon_file'):
            f = request.FILES['favicon_file']
            ext = os.path.splitext(f.name)[1] or '.ico'
            filename = f"favicon{ext}"
            for d in (static_img_dir, staticfiles_img_dir):
                file_path = os.path.join(d, filename)
                with open(file_path, 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)
            site.favicon_url = f"/static/img/{filename}"

        if request.FILES.get('thumbnail_file'):
            f = request.FILES['thumbnail_file']
            ext = os.path.splitext(f.name)[1] or '.png'
            filename = f"og_thumbnail{ext}"
            for d in (static_img_dir, staticfiles_img_dir):
                file_path = os.path.join(d, filename)
                with open(file_path, 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)
            site.thumbnail_url = f"/static/img/{filename}"

        site.save()
        messages.success(request, "Website Branding, SEO Meta Tags, WhatsApp Number & Social Media Settings saved successfully!")

    return redirect_to_admin_tab(action_type, request)
