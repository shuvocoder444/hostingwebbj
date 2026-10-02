"""
Domains Celery Tasks
=====================
Background tasks for asynchronous domain registrations and renewals.
"""
import logging
from celery import shared_task
from core.exceptions import DomainRegistrationError, DomainRenewalError

logger = logging.getLogger('domains')


@shared_task(bind=True, max_retries=3)
def register_domain_task(self, domain_id: str):
    """
    Asynchronously register a domain at the wholesale registrar API.
    Triggered when the domain invoice is marked PAID.
    """
    from domains.services import DomainService
    logger.info("Executing register_domain_task for domain_id=%s (Attempt %d)", domain_id, self.request.retries + 1)
    try:
        domain = DomainService.provision_domain(domain_id)
        return {"status": "SUCCESS", "domain": domain.domain_name, "expiry": str(domain.expiry_date)}
    except DomainRegistrationError as exc:
        logger.error("Domain registration failed: %s", exc)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.critical("Unexpected error in register_domain_task: %s", exc, exc_info=True)
        raise


@shared_task(bind=True, max_retries=3)
def renew_domain_task(self, domain_id: str, years: int = 1):
    """
    Asynchronously renew an active domain.
    """
    from domains.models import Domain
    from domains.drivers.factory import get_registrar_driver
    logger.info("Executing renew_domain_task for domain_id=%s", domain_id)
    try:
        domain = Domain.objects.get(id=domain_id)
        driver = get_registrar_driver(domain.registrar)
        res = driver.renew_domain(domain.domain_name, years=years)
        return {"status": "SUCCESS", "domain": domain.domain_name}
    except Exception as exc:
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
