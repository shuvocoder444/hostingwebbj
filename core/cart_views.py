"""
Cart & Multi-Step Ordering Views
=================================
Implements WHMCS-style unified ordering funnel:
  1. Choose a Domain (/cart/): Register New, Use Existing, or Transfer
  2. Configure Product (/cart/configure/): Specifications, Billing Cycle, Pricing breakdown
  3. View Cart & Checkout (/cart/checkout/): Order review, Guest auto-register / Login, Payment Gateway
  4. Complete Order (/cart/complete/): Atomic order creation (Pending accounts + Unpaid invoice)
"""
import logging
import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.models import ClientProfile
from billing.models import Gateway, Invoice, InvoiceItem, Transaction
from billing.services import InvoiceNumberGenerator
from domains.models import Domain, DomainRegistrar, TLDPricing
from domains.services import DomainService
from hosting.models import BillingCycle, HostingAccount, HostingPackage
from hosting.services import ProvisioningService

User = get_user_model()
logger = logging.getLogger('cart')


# ─── AJAX DOMAIN AVAILABILITY CHECK ───────────────────────────────────────────

def ajax_domain_check_view(request):
    """
    Fast live AJAX endpoint for domain search during checkout.
    Query params: ?domain=mybrand&tld=.com OR ?domain=mybrand.com
    """
    raw_domain = request.GET.get('domain', '').strip().lower()
    tld = request.GET.get('tld', '').strip().lower()

    if not raw_domain:
        return JsonResponse({'success': False, 'message': 'Please enter a domain name.'}, status=400)

    # Clean domain
    clean_domain = raw_domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

    if tld and not clean_domain.endswith(tld):
        if not tld.startswith('.'):
            tld = '.' + tld
        clean_domain = clean_domain.split('.')[0] + tld

    try:
        check = DomainService.check_availability(clean_domain)
        suggestions = []
        if not check.is_available:
            suggestions = DomainService.get_suggestions(clean_domain, max_results=5)

        return JsonResponse({
            'success': True,
            'domain': check.domain,
            'is_available': check.is_available,
            'price': str(check.price),
            'currency': check.currency or 'BDT',
            'status': check.status,
            'message': check.message or ('Available! You can register this domain.' if check.is_available else 'Domain is already taken.'),
            'suggestions': suggestions,
        })
    except Exception as exc:
        logger.exception("Domain check error: %s", exc)
        return JsonResponse({
            'success': False,
            'is_available': False,
            'domain': clean_domain,
            'message': f"Lookup note: {exc!s}",
            'suggestions': [],
        })



# ─── STEP 1: CHOOSE A DOMAIN ──────────────────────────────────────────────────

def cart_domain_view(request):
    """
    Step 1: Choose a Domain for the hosting package.
    Options:
      1. Register a new domain (Live WHOIS lookup)
      2. Use existing domain & update nameservers
      3. Transfer existing domain
    """
    package_id = request.GET.get('package') or request.GET.get('package_id')
    if not package_id:
        # Default to first featured or available package
        pkg = HostingPackage.objects.filter(is_active=True).order_by('-is_featured', 'monthly_price').first()
        if not pkg:
            messages.error(request, "No active hosting packages available right now.")
            return redirect('landing')
        package_id = str(pkg.id)

    package = get_object_or_404(HostingPackage, id=package_id, is_active=True)
    tld_prices = TLDPricing.objects.filter(is_active=True).order_by('tld')

    # Handle incoming query parameters from home search or direct buy links
    initial_domain = request.GET.get('domain', '').strip().lower()
    initial_option = request.GET.get('domain_option') or request.GET.get('domain_action') or 'register'
    initial_tld = request.GET.get('tld', '').strip().lower()
    direct = request.GET.get('direct', '').strip()

    initial_sld = ''
    if initial_domain:
        initial_domain = initial_domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        sld, ext = DomainService.extract_tld(initial_domain)
        initial_sld = sld
        if not initial_tld:
            initial_tld = ext

        # If user clicked Buy from landing page with direct=1, skip Step 1 and proceed straight to Configure!
        if direct == '1':
            return redirect(f"/cart/configure/?package={package.id}&domain={initial_domain}&domain_option={initial_option}&tld={initial_tld}")

    if request.method == 'POST':
        domain_option = request.POST.get('domain_option', 'register')
        
        if domain_option == 'register':
            reg_domain = request.POST.get('register_domain', '').strip().lower()
            reg_tld = request.POST.get('register_tld', '.com').strip().lower()
            if not reg_tld.startswith('.'):
                reg_tld = '.' + reg_tld
            clean = reg_domain.split('.')[0] + reg_tld
            if not reg_domain:
                messages.error(request, "Please enter a domain name to register.")
                return redirect(f"/cart/?package={package.id}")
            return redirect(f"/cart/configure/?package={package.id}&domain={clean}&domain_option=register&tld={reg_tld}")

        elif domain_option == 'existing':
            existing_domain = request.POST.get('existing_domain', '').strip().lower()
            existing_domain = existing_domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            if not existing_domain or '.' not in existing_domain:
                messages.error(request, "Please enter a valid existing domain name (e.g. mycompany.com).")
                return redirect(f"/cart/?package={package.id}")
            return redirect(f"/cart/configure/?package={package.id}&domain={existing_domain}&domain_option=existing")

        elif domain_option == 'transfer':
            transfer_domain = request.POST.get('transfer_domain', '').strip().lower()
            epp_code = request.POST.get('epp_code', '').strip()
            transfer_domain = transfer_domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            if not transfer_domain or '.' not in transfer_domain:
                messages.error(request, "Please enter a valid domain name to transfer.")
                return redirect(f"/cart/?package={package.id}")
            return redirect(f"/cart/configure/?package={package.id}&domain={transfer_domain}&domain_option=transfer&epp={epp_code}")

    context = {
        'package': package,
        'tld_prices': tld_prices,
        'step': 1,
        'initial_domain': initial_domain,
        'initial_sld': initial_sld,
        'initial_tld': initial_tld,
        'initial_option': initial_option,
    }
    return render(request, 'cart_domain.html', context)



# ─── STEP 2: CONFIGURE HOSTING & BILLING CYCLE ────────────────────────────────

def cart_configure_view(request):
    """
    Step 2: Configure Product & Billing Cycle.
    Matches the WHMCS configuration layout from bestwebhostbd.com.
    """
    package_id = request.GET.get('package') or request.GET.get('package_id')
    domain = request.GET.get('domain', '').strip().lower()
    domain_option = request.GET.get('domain_option', 'existing')
    tld = request.GET.get('tld', '.com').strip().lower()
    epp = request.GET.get('epp', '').strip()

    if not package_id or not domain:
        messages.warning(request, "Please choose a package and domain first.")
        return redirect('cart_domain')

    package = get_object_or_404(HostingPackage, id=package_id, is_active=True)

    # Compute cycle pricing
    monthly_price = package.monthly_price
    annual_price = package.annual_price or (monthly_price * 10) # 2 months free discount
    biennial_price = getattr(package, 'biennial_price', None) or (annual_price * Decimal('1.80'))
    triennial_price = getattr(package, 'triennial_price', None) or (annual_price * Decimal('2.50'))

    # Determine domain registration fee if option is register
    domain_price = Decimal('0.00')
    if domain_option == 'register':
        tld_obj = TLDPricing.objects.filter(tld__iexact=tld, is_active=True).first()
        if not tld_obj:
            _, ext = DomainService.extract_tld(domain)
            tld_obj = TLDPricing.objects.filter(tld__iexact=ext, is_active=True).first()
        domain_price = tld_obj.register_price if tld_obj else Decimal('1350.00')

    context = {
        'package': package,
        'domain': domain,
        'domain_option': domain_option,
        'tld': tld,
        'epp': epp,
        'monthly_price': monthly_price,
        'annual_price': annual_price,
        'biennial_price': biennial_price,
        'triennial_price': triennial_price,
        'domain_price': domain_price,
        'step': 2,
    }
    return render(request, 'cart_configure.html', context)


# ─── STEP 3: VIEW CART & CHECKOUT ─────────────────────────────────────────────

def cart_checkout_view(request):
    """
    Step 3: Review Cart Items, Authentication / Guest Registration, & Payment.
    """
    package_id = request.GET.get('package') or request.GET.get('package_id')
    domain = request.GET.get('domain', '').strip().lower()
    domain_option = request.GET.get('domain_option', 'existing')
    billing_cycle = request.GET.get('billing_cycle', 'annual').lower()
    tld = request.GET.get('tld', '.com').strip().lower()
    epp = request.GET.get('epp', '').strip()

    if not package_id or not domain:
        messages.warning(request, "Your cart is empty. Please select a hosting package.")
        return redirect('cart_domain')

    package = get_object_or_404(HostingPackage, id=package_id, is_active=True)

    # Calculate hosting price according to chosen billing cycle
    if billing_cycle == 'monthly':
        hosting_price = package.monthly_price
        cycle_label = 'Monthly (1 Month)'
    elif billing_cycle == 'quarterly' and package.quarterly_price:
        hosting_price = package.quarterly_price
        cycle_label = 'Quarterly (3 Months)'
    elif billing_cycle == 'semi_annual' and package.semi_annual_price:
        hosting_price = package.semi_annual_price
        cycle_label = 'Semi-Annual (6 Months)'
    elif billing_cycle == 'biennial':
        hosting_price = getattr(package, 'biennial_price', None) or ((package.annual_price or package.monthly_price * 10) * Decimal('1.80'))
        cycle_label = 'Biennially (2 Years)'
    elif billing_cycle == 'triennial':
        hosting_price = getattr(package, 'triennial_price', None) or ((package.annual_price or package.monthly_price * 10) * Decimal('2.50'))
        cycle_label = 'Triennially (3 Years)'
    else:
        billing_cycle = 'annual'
        hosting_price = package.annual_price or (package.monthly_price * 10)
        cycle_label = 'Annually (1 Year)'

    # Calculate domain price
    domain_price = Decimal('0.00')
    if domain_option == 'register':
        tld_obj = TLDPricing.objects.filter(tld__iexact=tld, is_active=True).first()
        if not tld_obj:
            _, ext = DomainService.extract_tld(domain)
            tld_obj = TLDPricing.objects.filter(tld__iexact=ext, is_active=True).first()
        domain_price = tld_obj.register_price if tld_obj else Decimal('1350.00')

    server_location = request.GET.get('server_location', 'germany').lower()
    location_names = {
        'germany': '🇩🇪 Germany (AMD EPYC)',
        'finland': '🇫🇮 Finland (Helsinki)',
        'bdix': '🇧🇩 Bangladesh (BDIX <5ms)',
    }
    location_label = location_names.get(server_location, '🇩🇪 Germany (AMD EPYC)')

    subtotal = hosting_price + domain_price
    tax_amount = Decimal('0.00')
    total = subtotal + tax_amount

    context = {
        'package': package,
        'domain': domain,
        'domain_option': domain_option,
        'billing_cycle': billing_cycle,
        'cycle_label': cycle_label,
        'hosting_price': hosting_price,
        'domain_price': domain_price,
        'server_location': server_location,
        'location_label': location_label,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'total': total,
        'tld': tld,
        'epp': epp,
        'step': 3,
    }
    return render(request, 'cart_checkout.html', context)


# ─── STEP 4: ORDER COMPLETION & ATOMIC PROVISIONING TRIGGER ───────────────────

@require_http_methods(['POST'])
def cart_complete_order_view(request):
    """
    Final Order Execution:
      1. Validates / Creates user account if guest or authenticates existing.
      2. Creates HostingAccount (status = PENDING).
      3. If domain registration, creates Domain (status = PENDING).
      4. Creates Invoice (status = UNPAID) with line items.
      5. Automatically logs user in and redirects to invoice payment.
    """
    package_id = request.POST.get('package_id')
    domain = request.POST.get('domain', '').strip().lower()
    domain_option = request.POST.get('domain_option', 'existing')
    billing_cycle = request.POST.get('billing_cycle', 'annual').lower()
    gateway_choice = request.POST.get('payment_gateway', 'bkash').lower()
    sender_number = request.POST.get('sender_number', '').strip()
    trx_id = request.POST.get('trx_id', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not package_id or not domain:
        messages.error(request, "Invalid order session. Please configure your order again.")
        return redirect('cart_domain')

    package = get_object_or_404(HostingPackage, id=package_id, is_active=True)

    try:
        # 1. Resolve User
        current_user = None
        if request.user.is_authenticated:
            current_user = request.user
        else:
            auth_mode = request.POST.get('auth_mode', 'register')  # 'register' or 'login'

            if auth_mode == 'login':
                email = request.POST.get('login_email', '').strip().lower()
                password = request.POST.get('login_password', '').strip()
                user = authenticate(request, username=email, password=password)
                if not user:
                    # Try finding by email
                    u = User.objects.filter(email__iexact=email).first()
                    if u and u.check_password(password):
                        user = u
                        user.backend = 'django.contrib.auth.backends.ModelBackend'
                if not user:
                    messages.error(request, "Invalid login credentials. Please check your email & password.")
                    return redirect(f"/cart/checkout/?package={package.id}&domain={domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                current_user = user

            else:
                # Register new customer
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                email = request.POST.get('email', '').strip().lower()
                phone = request.POST.get('phone', '').strip()
                company = request.POST.get('company_name', '').strip()
                password = request.POST.get('password', '').strip()
                password_confirm = request.POST.get('password_confirm', '').strip()

                if not email or not first_name or not password:
                    messages.error(request, "First Name, Email Address, and Password are required.")
                    return redirect(f"/cart/checkout/?package={package.id}&domain={domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")

                if password != password_confirm:
                    messages.error(request, "Passwords do not match.")
                    return redirect(f"/cart/checkout/?package={package.id}&domain={domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")

                if User.objects.filter(email__iexact=email).exists():
                    messages.error(request, f"An account with email '{email}' already exists. Please log in.")
                    return redirect(f"/cart/checkout/?package={package.id}&domain={domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")

                with db_transaction.atomic():
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
                        country='BD',
                    )
                    login(request, new_user, backend='django.contrib.auth.backends.ModelBackend')
                    current_user = new_user

        # 2. Compute Prices
        if billing_cycle == 'monthly':
            hosting_amount = package.monthly_price
        elif billing_cycle == 'quarterly' and package.quarterly_price:
            hosting_amount = package.quarterly_price
        elif billing_cycle == 'semi_annual' and package.semi_annual_price:
            hosting_amount = package.semi_annual_price
        elif billing_cycle == 'biennial':
            hosting_amount = getattr(package, 'biennial_price', None) or ((package.annual_price or package.monthly_price * 10) * Decimal('1.80'))
        elif billing_cycle == 'triennial':
            hosting_amount = getattr(package, 'triennial_price', None) or ((package.annual_price or package.monthly_price * 10) * Decimal('2.50'))
        else:
            billing_cycle = 'annual'
            hosting_amount = package.annual_price or (package.monthly_price * 10)

        domain_amount = Decimal('0.00')
        if domain_option == 'register':
            _, ext = DomainService.extract_tld(domain)
            tld_obj = TLDPricing.objects.filter(tld__iexact=ext, is_active=True).first()
            domain_amount = tld_obj.register_price if tld_obj else Decimal('1350.00')

        total_amount = hosting_amount + domain_amount

        # 3. Create Pending Hosting Account & Domain Records in Atomic Transaction
        with db_transaction.atomic():
            # Clean domain and generate cPanel username
            clean_domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            cpanel_user = ProvisioningService.generate_cpanel_username(clean_domain)
            cpanel_pass = ProvisioningService.generate_secure_password()

            days_map = {
                'monthly': 30,
                'quarterly': 90,
                'semi_annual': 180,
                'annual': 365,
                'biennial': 730,
                'triennial': 1095,
            }
            next_due = timezone.now().date() + timezone.timedelta(days=days_map.get(billing_cycle, 365))

            # Re-use or create HostingAccount safely
            account = HostingAccount.objects.filter(domain=clean_domain).first()
            if account:
                if account.status == HostingAccount.Status.ACTIVE:
                    messages.error(request, f"A hosting account for domain '{clean_domain}' is already active.")
                    return redirect(f"/cart/checkout/?package={package.id}&domain={clean_domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")
                account.user = current_user
                account.package = package
                account.server = package.server
                account.status = HostingAccount.Status.PENDING
                account.billing_cycle = billing_cycle
                account.amount = hosting_amount
                account.next_due_date = next_due
                account.set_account_password(cpanel_pass)
                account.save()
            else:
                account = HostingAccount.objects.create(
                    user=current_user,
                    package=package,
                    server=package.server,
                    domain=clean_domain,
                    username=cpanel_user,
                    status=HostingAccount.Status.PENDING,
                    billing_cycle=billing_cycle,
                    amount=hosting_amount,
                    next_due_date=next_due,
                )
                account.set_account_password(cpanel_pass)
                account.save()

            # Domain record if new registration
            domain_record = None
            if domain_option == 'register':
                _, ext = DomainService.extract_tld(clean_domain)
                tld_obj = TLDPricing.objects.filter(tld__iexact=ext, is_active=True).first()
                registrar = tld_obj.registrar if (tld_obj and tld_obj.registrar) else DomainRegistrar.objects.filter(is_default=True).first()

                domain_record = Domain.objects.filter(domain_name=clean_domain).first()
                if domain_record:
                    domain_record.user = current_user
                    domain_record.registrar = registrar
                    domain_record.status = Domain.Status.PENDING
                    domain_record.save()
                else:
                    domain_record = Domain.objects.create(
                        user=current_user,
                        registrar=registrar,
                        domain_name=clean_domain,
                        registration_years=1,
                        status=Domain.Status.PENDING,
                        registration_date=timezone.now().date(),
                        expiry_date=timezone.now().date() + timezone.timedelta(days=365),
                        next_due_date=timezone.now().date() + timezone.timedelta(days=365),
                        auto_renew=True,
                    )

            # 4. Create Unpaid Invoice with line items
            inv_number = InvoiceNumberGenerator.generate()
            invoice = Invoice.objects.create(
                invoice_number=inv_number,
                user=current_user,
                invoice_type=Invoice.InvoiceType.HOSTING,
                hosting_account=account,
                domain=domain_record,
                status=Invoice.Status.UNPAID,
                subtotal=total_amount,
                total=total_amount,
                issued_date=timezone.now().date(),
                due_date=timezone.now().date() + timezone.timedelta(days=7),
            )

            # Hosting Line Item
            loc_label = {'germany': 'Germany 🇩🇪', 'finland': 'Finland 🇫🇮', 'bdix': 'BDIX BD 🇧🇩'}.get(request.POST.get('server_location', 'germany').lower(), 'Germany 🇩🇪')
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Web Hosting - {package.name} ({clean_domain}) [{billing_cycle.title()}] - Server: {loc_label}",
                quantity=Decimal('1.00'),
                unit_price=hosting_amount,
                line_total=hosting_amount,
            )

            # Domain Line Item (if applicable)
            if domain_option == 'register' and domain_amount > 0:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=f"Domain Registration - {clean_domain} (1 Year)",
                    quantity=Decimal('1.00'),
                    unit_price=domain_amount,
                    line_total=domain_amount,
                )

            # Record manual payment transaction if submitted on checkout
            if trx_id:
                Transaction.objects.create(
                    invoice=invoice,
                    user=current_user,
                    gateway=gateway_choice if gateway_choice in dict(Gateway.choices) else Gateway.BKASH,
                    status=Transaction.Status.PENDING,
                    gateway_transaction_id=trx_id,
                    amount=invoice.total,
                    gateway_response={
                        'sender_number': sender_number,
                        'notes': notes,
                        'submitted_at': timezone.now().isoformat(),
                        'channel': 'cart_checkout_direct',
                    }
                )

        if trx_id:
            messages.success(
                request,
                f"Order placed successfully! Invoice #{invoice.invoice_number} (৳{invoice.total} BDT) recorded with Payment TrxID: '{trx_id}'. "
                f"Your hosting and domain will be automatically activated as soon as the payment is verified by our team."
            )
            return redirect('/dashboard/?tab=invoices')
        else:
            messages.success(
                request,
                f"Order placed successfully! Invoice #{invoice.invoice_number} (৳{invoice.total} BDT) has been created. "
                f"Please submit your payment details to activate your hosting & domain."
            )
            return redirect(f"/dashboard/?tab=invoices&pay_invoice={invoice.id}")

    except Exception as exc:
        logger.exception("Error processing cart complete order: %s", exc)
        messages.error(request, f"Error processing order: {exc!s}")
        return redirect(f"/cart/checkout/?package={package.id}&domain={domain}&domain_option={domain_option}&billing_cycle={billing_cycle}")
