"""
Base Server Driver — Interface Definition
==========================================
All server drivers must implement this interface.
This enables the factory pattern and makes drivers swappable.

New panel support = new driver class, zero changes to provisioning logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AccountInfo:
    """Structured response from driver operations."""
    username: str
    domain: str
    ip: str
    package: str
    disk_used_mb: Optional[float] = None
    bandwidth_used_mb: Optional[float] = None
    email_count: Optional[int] = None
    subdomains: Optional[list] = None


class BaseServerDriver(ABC):
    """
    Abstract interface that all server panel drivers must implement.
    
    Usage:
        driver = get_driver(server)
        driver.create_account(domain='example.com', username='user123', ...)
    """

    def __init__(self, host: str, port: int, username: str, api_token: str, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.api_token = api_token
        self.use_ssl = use_ssl
        self._base_url = f"{'https' if use_ssl else 'http'}://{host}:{port}"

    @abstractmethod
    def create_account(
        self,
        domain: str,
        username: str,
        password: str,
        package_name: str,
        email: str,
    ) -> dict:
        """
        Create a new hosting account.
        
        Returns:
            dict with at least: {'success': bool, 'message': str}
        Raises:
            ProvisioningError on failure.
        """
        ...

    @abstractmethod
    def suspend_account(self, username: str, reason: str = '') -> dict:
        """Suspend an account. Raises SuspensionError on failure."""
        ...

    @abstractmethod
    def unsuspend_account(self, username: str) -> dict:
        """Unsuspend an account. Raises SuspensionError on failure."""
        ...

    @abstractmethod
    def terminate_account(self, username: str) -> dict:
        """Permanently delete an account. Raises TerminationError on failure."""
        ...

    @abstractmethod
    def get_account_info(self, username: str) -> AccountInfo:
        """Fetch live account stats. Raises ServerDriverError on failure."""
        ...

    @abstractmethod
    def change_package(self, username: str, new_package_name: str) -> dict:
        """Move account to a different resource package."""
        ...
