"""
Mock Domain Registrar Driver
=============================
Provides simulated domain availability checks and registrations
for local development, automated testing, and sandbox environments.
"""
import uuid
from typing import List, Optional
from decimal import Decimal

from .base import BaseRegistrarDriver, DomainCheckResult, DomainRegistrationResult


class MockRegistrarDriver(BaseRegistrarDriver):
    """
    Mock driver that always succeeds for local development and demos.
    """

    TAKEN_DOMAINS = {"google.com", "facebook.com", "microsoft.com", "hostpro.bd", "bdix.net"}

    def check_availability(self, domain: str) -> DomainCheckResult:
        domain_clean = domain.lower().strip()
        is_avail = domain_clean not in self.TAKEN_DOMAINS
        return DomainCheckResult(
            domain=domain_clean,
            is_available=is_avail,
            status="available" if is_avail else "taken",
            price=Decimal("1350.00"),
            currency="BDT",
            message="Available for registration!" if is_avail else "Already registered",
        )

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        contact_info: dict = None,
        nameservers: Optional[List[str]] = None
    ) -> DomainRegistrationResult:
        order_id = f"MOCK-REG-{uuid.uuid4().hex[:8].upper()}"
        return DomainRegistrationResult(
            success=True,
            domain=domain,
            order_id=order_id,
            message="Domain successfully registered via Mock Registrar!",
            raw_response={"status": "success", "order_id": order_id, "mock": True}
        )

    def renew_domain(self, domain: str, years: int = 1) -> DomainRegistrationResult:
        return DomainRegistrationResult(
            success=True,
            domain=domain,
            order_id=f"MOCK-REN-{uuid.uuid4().hex[:8].upper()}",
            message="Domain renewed successfully.",
        )

    def update_nameservers(self, domain: str, nameservers: List[str]) -> bool:
        return True

    def get_domain_info(self, domain: str) -> dict:
        return {
            "domain": domain,
            "status": "ACTIVE",
            "nameservers": ["ns1.hostpro.bd", "ns2.hostpro.bd"],
            "mock": True
        }

    def get_account_balance(self) -> dict:
        return {"balance": "1000.00", "currency": "USD", "status": "active (mock)"}
