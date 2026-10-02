"""
Base Domain Registrar Driver — Interface Definition
=====================================================
All domain registrar drivers (ResellerClub, Namecheap, OpenSRS, Mock)
must implement this abstract base class.
Follows the Repository / Driver pattern for swappable registrars.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass 
class DomainCheckResult:
    """Standardized response from registrar domain search."""
    domain: str
    is_available: bool
    status: str = "available"  # 'available', 'taken', 'error'
    price: Decimal | None = None
    currency: str = "BDT"
    is_premium: bool = False
    message: str = ""


@dataclass
class DomainRegistrationResult:
    """Standardized response from registrar domain registration/renewal."""
    success: bool
    domain: str
    order_id: str | None = None
    message: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseRegistrarDriver(ABC):
    """
    Abstract interface for Domain Registrar APIs.
    """

    def __init__(self, api_user: str, api_key: str, is_sandbox: bool = True, extra_config: dict = None):
        self.api_user = api_user
        self.api_key = api_key
        self.is_sandbox = is_sandbox
        self.extra_config = extra_config or {}

    @abstractmethod
    def check_availability(self, domain: str) -> DomainCheckResult:
        """
        Check if a single domain is available for registration.
        """
        ...

    @abstractmethod
    def register_domain(
        self,
        domain: str,
        years: int,
        contact_info: dict,
        nameservers: list[str] | None = None
    ) -> DomainRegistrationResult:
        """
        Register a new domain name through the registrar API.
        """
        ...

    @abstractmethod
    def renew_domain(self, domain: str, years: int) -> DomainRegistrationResult:
        """
        Renew an existing domain name.
        """
        ...

    @abstractmethod
    def update_nameservers(self, domain: str, nameservers: list[str]) -> bool:
        """
        Update the DNS nameservers for a domain.
        """
        ...

    @abstractmethod
    def get_domain_info(self, domain: str) -> dict:
        """
        Retrieve live domain information (expiry date, status, nameservers).
        """
        ...

    @abstractmethod
    def get_account_balance(self) -> dict:
        """
        Check wholesale credit balance remaining in the registrar account.
        """
        ...
