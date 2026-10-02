"""
Management command to seed initial demonstration data.
Creates admin, demo client, server, hosting packages, and sample services.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, ClientProfile
from hosting.models import Server, HostingPackage, HostingAccount, ServerDriver, BillingCycle
from billing.models import Invoice, InvoiceItem


class Command(BaseCommand):
    help = "Seed demo database with admin, client, server, packages, and sample hosting accounts"

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data for HostPro...")

        # 1. Admin User
        admin_user, created = User.objects.get_or_create(
            email="admin@hostpro.com",
            defaults={
                "first_name": "HostPro",
                "last_name": "Admin",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            }
        )
        admin_user.set_password("HostPro@123")
        admin_user.save()
        ClientProfile.objects.get_or_create(user=admin_user, defaults={"company_name": "HostPro Inc."})
        self.stdout.write(self.style.SUCCESS("[OK] Admin user: admin@hostpro.com / HostPro@123"))

        # 2. Client User
        client_user, created = User.objects.get_or_create(
            email="client@example.com",
            defaults={
                "first_name": "Tanvir",
                "last_name": "Ahmed",
                "role": User.Role.CLIENT,
            }
        )
        client_user.set_password("HostPro@123")
        client_user.save()
        profile, _ = ClientProfile.objects.get_or_create(
            user=client_user,
            defaults={
                "company_name": "Ahmed Tech Solutions",
                "phone": "+880 1711-223344",
                "address_line1": "Dhanmondi, Road 27",
                "city": "Dhaka",
                "country": "BD",
                "credit_balance": Decimal("500.00"),
                "currency": "BDT",
            }
        )
        self.stdout.write(self.style.SUCCESS("[OK] Client user: client@example.com / HostPro@123"))

        # 3. Server
        server, created = Server.objects.get_or_create(
            hostname="srv1.hostpro.bd",
            defaults={
                "name": "BDIX-Cloud-01 (Dhaka)",
                "ip_address": "103.20.10.5",
                "port": 2087,
                "driver": ServerDriver.CPANEL,
                "api_username": "root",
                "max_accounts": 250,
                "nameserver_1": "ns1.hostpro.bd",
                "nameserver_2": "ns2.hostpro.bd",
            }
        )
        server.set_api_token("whm-secret-token-sample")
        server.save()
        self.stdout.write(self.style.SUCCESS(f"[OK] Server: {server.name} ({server.hostname})"))

        # 4. Hosting Packages
        pkg1, _ = HostingPackage.objects.get_or_create(
            name="Starter Cloud",
            defaults={
                "server": server,
                "disk_quota_mb": 5120,      # 5 GB
                "bandwidth_mb": 102400,     # 100 GB
                "max_databases": 5,
                "max_email_accounts": 10,
                "max_subdomains": 5,
                "monthly_price": Decimal("250.00"),
                "annual_price": Decimal("2500.00"),
                "panel_package_name": "starter_5gb",
                "is_active": True,
                "is_featured": False,
                "description": "Ideal for personal portfolios, personal blogs and small starter projects.",
            }
        )

        pkg2, _ = HostingPackage.objects.get_or_create(
            name="Business Pro NVMe",
            defaults={
                "server": server,
                "disk_quota_mb": 25600,     # 25 GB
                "bandwidth_mb": 0,          # Unlimited
                "max_databases": 25,
                "max_email_accounts": 50,
                "max_subdomains": 25,
                "monthly_price": Decimal("650.00"),
                "annual_price": Decimal("6500.00"),
                "panel_package_name": "business_25gb",
                "is_active": True,
                "is_featured": True,
                "description": "Blazing fast NVMe SSD hosting with cPanel, unlimited bandwidth, and LiteSpeed cache.",
            }
        )

        pkg3, _ = HostingPackage.objects.get_or_create(
            name="Turbo Enterprise",
            defaults={
                "server": server,
                "disk_quota_mb": 102400,    # 100 GB
                "bandwidth_mb": 0,          # Unlimited
                "max_databases": 100,
                "max_email_accounts": 200,
                "max_subdomains": 100,
                "monthly_price": Decimal("1450.00"),
                "annual_price": Decimal("14500.00"),
                "panel_package_name": "turbo_100gb",
                "is_active": True,
                "is_featured": False,
                "description": "High-traffic e-commerce & corporate sites with dedicated RAM/CPU allocation and priority support.",
            }
        )
        self.stdout.write(self.style.SUCCESS("[OK] 3 Hosting packages created."))

        # 5. Sample Hosting Account for Demo Client
        today = timezone.now().date()
        account, created = HostingAccount.objects.get_or_create(
            domain="ahmedsolutions.com.bd",
            defaults={
                "user": client_user,
                "package": pkg2,
                "server": server,
                "username": "ahmedbiz",
                "status": HostingAccount.Status.ACTIVE,
                "billing_cycle": BillingCycle.MONTHLY,
                "amount": pkg2.monthly_price,
                "provisioned_at": timezone.now(),
                "next_due_date": today + timezone.timedelta(days=22),
            }
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Sample hosting account: {account.domain} (Status: ACTIVE)"))

        # 6. Sample Pending Invoice for Demo Client
        invoice, created = Invoice.objects.get_or_create(
            invoice_number="INV-00001",
            defaults={
                "user": client_user,
                "hosting_account": account,
                "invoice_type": Invoice.InvoiceType.HOSTING,
                "status": Invoice.Status.UNPAID,
                "subtotal": pkg2.monthly_price,
                "total": pkg2.monthly_price,
                "issued_date": today,
                "due_date": today + timezone.timedelta(days=7),
            }
        )
        if created:
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Business Pro NVMe - ahmedsolutions.com.bd (1 Month Renewal)",
                quantity=Decimal("1.00"),
                unit_price=pkg2.monthly_price,
                line_total=pkg2.monthly_price,
            )
        self.stdout.write(self.style.SUCCESS(f"[OK] Sample invoice: {invoice.invoice_number} (BDT {invoice.total})"))

        # 7. Domain Registrar & TLD Pricing
        from domains.models import DomainRegistrar, TLDPricing, Domain, RegistrarType
        registrar, _ = DomainRegistrar.objects.get_or_create(
            name="ResellerClub / Sandbox Registrar",
            defaults={
                "driver": RegistrarType.MOCK,
                "api_user": "demo_reseller_123",
                "is_sandbox": True,
                "is_active": True,
                "is_default": True,
            }
        )
        registrar.set_api_key("secret-registrar-api-key")
        registrar.save()

        tlds = [
            (".com", Decimal("1350.00"), Decimal("1350.00"), True),
            (".com.bd", Decimal("1800.00"), Decimal("1800.00"), True),
            (".net", Decimal("1450.00"), Decimal("1450.00"), False),
            (".org", Decimal("1500.00"), Decimal("1500.00"), False),
            (".xyz", Decimal("350.00"), Decimal("950.00"), True),
        ]
        for tld_str, reg_p, ren_p, is_feat in tlds:
            TLDPricing.objects.get_or_create(
                tld=tld_str,
                defaults={
                    "registrar": registrar,
                    "register_price": reg_p,
                    "renew_price": ren_p,
                    "is_active": True,
                    "is_featured": is_feat,
                }
            )
        self.stdout.write(self.style.SUCCESS("[OK] Domain registrar and 5 TLD prices configured."))

        # 8. Sample Client Domain
        client_domain, _ = Domain.objects.get_or_create(
            domain_name="ahmedsolutions.com.bd",
            defaults={
                "user": client_user,
                "registrar": registrar,
                "status": Domain.Status.ACTIVE,
                "registration_years": 1,
                "registration_date": today,
                "expiry_date": today + timezone.timedelta(days=365),
                "next_due_date": today + timezone.timedelta(days=358),
                "nameserver_1": "ns1.hostpro.bd",
                "nameserver_2": "ns2.hostpro.bd",
                "registrar_order_id": "REG-RC-98421",
            }
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Sample client domain: {client_domain.domain_name} (Status: ACTIVE)"))

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Demo seeding completed successfully!"))

