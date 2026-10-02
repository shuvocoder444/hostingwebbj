"""
Domains Service Layer
======================
Handles business logic for domain availability search, orders,
automated provisioning via registrar drivers, and DNS management.
"""
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction as db_transaction
from django.utils import timezone

from core.exceptions import DomainRegistrationError, DomainRenewalError
from .models import Domain, DomainRegistrar, TLDPricing
from .drivers.factory import get_registrar_driver
from .drivers.base import DomainCheckResult, DomainRegistrationResult

logger = logging.getLogger('domains')


class DomainService:
    """
    Orchestrates all domain registration, renewal, and DNS operations.
    """

    @staticmethod
    def extract_tld(domain_name: str) -> Tuple[str, str]:
        """
        Splits 'mycompany.com.bd' -> ('mycompany', '.com.bd')
        Splits 'mycompany.com' -> ('mycompany', '.com')
        """
        parts = domain_name.lower().strip().split('.')
        if len(parts) >= 3 and parts[-2] in ('com', 'org', 'net', 'edu', 'gov'):
            sld = '.'.join(parts[:-2])
            tld = '.' + '.'.join(parts[-2:])
        elif len(parts) >= 2:
            sld = parts[0]
            tld = '.' + '.'.join(parts[1:])
        else:
            sld = domain_name
            tld = '.com'
        return sld, tld

    @classmethod
    def check_availability(cls, domain_name: str) -> DomainCheckResult:
        """
        Check if a domain is available and fetch retail price from TLDPricing.
        """
        clean_name = domain_name.lower().strip().replace('https://', '').replace('http://', '').split('/')[0]
        sld, tld = cls.extract_tld(clean_name)

        # Lookup price from our catalogue
        tld_pricing = TLDPricing.objects.filter(tld__iexact=tld, is_active=True).first()
        price = tld_pricing.register_price if tld_pricing else Decimal('1350.00')

        # Check if already registered on our local platform
        if Domain.objects.filter(domain_name=clean_name, status=Domain.Status.ACTIVE).exists():
            return DomainCheckResult(
                domain=clean_name,
                is_available=False,
                status="taken",
                price=price,
                message="Domain already registered on HostPro",
            )

        # Query live Registrar API
        registrar = tld_pricing.registrar if (tld_pricing and tld_pricing.registrar) else None
        driver = get_registrar_driver(registrar)

        result = driver.check_availability(clean_name)
        result.price = price
        result.currency = "BDT"
        return result

    @classmethod
    @db_transaction.atomic
    def create_pending_domain(
        cls,
        user,
        domain_name: str,
        years: int = 1,
        nameservers: Optional[list] = None,
    ) -> Domain:
        """
        Create a PENDING domain record before payment.
        Actual registration at the registrar happens after payment confirmation.
        """
        clean_name = domain_name.lower().strip().replace('https://', '').replace('http://', '').split('/')[0]
        sld, tld = cls.extract_tld(clean_name)

        tld_pricing = TLDPricing.objects.filter(tld__iexact=tld, is_active=True).first()
        registrar = tld_pricing.registrar if (tld_pricing and tld_pricing.registrar) else DomainRegistrar.objects.filter(is_default=True).first()

        ns = nameservers or ['ns1.hostpro.bd', 'ns2.hostpro.bd']

        domain, created = Domain.objects.get_or_create(
            domain_name=clean_name,
            defaults={
                'user': user,
                'registrar': registrar,
                'status': Domain.Status.PENDING,
                'registration_years': years,
                'nameserver_1': ns[0] if len(ns) > 0 else 'ns1.hostpro.bd',
                'nameserver_2': ns[1] if len(ns) > 1 else 'ns2.hostpro.bd',
            }
        )
        return domain

    @classmethod
    @db_transaction.atomic
    def provision_domain(cls, domain_id: str) -> Domain:
        """
        Register the domain with the wholesale registrar API.
        Triggered automatically upon payment confirmation.
        """
        domain = Domain.objects.select_for_update().get(id=domain_id)

        if domain.status == Domain.Status.ACTIVE:
            logger.info("Domain %s is already active.", domain.domain_name)
            return domain

        registrar = domain.registrar or DomainRegistrar.objects.filter(is_default=True).first()
        driver = get_registrar_driver(registrar)

        user = domain.user
        profile = getattr(user, 'profile', None)

        contact = {
            'first_name': user.first_name or 'Client',
            'last_name': user.last_name or 'Owner',
            'email': user.email,
            'phone': getattr(profile, 'phone', '+880.1700000000') or '+880.1700000000',
            'address': getattr(profile, 'address_line1', 'Dhaka') or 'Dhaka',
            'city': getattr(profile, 'city', 'Dhaka') or 'Dhaka',
            'country': getattr(profile, 'country', 'BD') or 'BD',
            'postal_code': getattr(profile, 'postal_code', '1205') or '1205',
        }

        ns_list = [domain.nameserver_1, domain.nameserver_2]
        if domain.nameserver_3:
            ns_list.append(domain.nameserver_3)
        if domain.nameserver_4:
            ns_list.append(domain.nameserver_4)

        logger.info("Provisioning domain '%s' at registrar '%s'...", domain.domain_name, driver.__class__.__name__)

        reg_result = driver.register_domain(
            domain=domain.domain_name,
            years=domain.registration_years,
            contact_info=contact,
            nameservers=ns_list,
        )

        today = timezone.now().date()
        expiry = today + timedelta(days=365 * domain.registration_years)

        domain.status = Domain.Status.ACTIVE
        domain.registration_date = today
        domain.expiry_date = expiry
        domain.next_due_date = expiry - timedelta(days=7)  # Invoice 7 days before expiry
        domain.registrar_order_id = reg_result.order_id or ''
        domain.save()

        logger.info("✓ Domain '%s' successfully provisioned and active until %s!", domain.domain_name, expiry)
        return domain
