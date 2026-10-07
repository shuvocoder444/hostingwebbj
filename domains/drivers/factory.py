"""
Domain Registrar Driver Factory
=================================
Selects and instantiates the correct registrar driver at runtime.
Decrypts API credentials just-in-time via Fernet.
"""
import logging
from typing import TYPE_CHECKING, Optional, Type

from core.exceptions import RegistrarDriverError
from .base import BaseRegistrarDriver
from .resellerclub import ResellerClubDriver
from .namecheap import NamecheapDriver
from .mock import MockRegistrarDriver
from .bdwebs import BDWebsDriver
from .spaceship import SpaceshipDriver

if TYPE_CHECKING:
    from domains.models import DomainRegistrar

logger = logging.getLogger('domains')

_REGISTRAR_REGISTRY: dict[str, Type[BaseRegistrarDriver]] = {
    'spaceship': SpaceshipDriver,
    'resellerclub': ResellerClubDriver,
    'namecheap': NamecheapDriver,
    'mock': MockRegistrarDriver,
    'bdwebs': BDWebsDriver,
    'domainsreseller': BDWebsDriver,
    'domainresellerlite': BDWebsDriver,
}


def get_registrar_driver(registrar: Optional['DomainRegistrar'] = None, driver_type: Optional[str] = None) -> BaseRegistrarDriver:
    """
    Factory to return an initialized registrar driver.
    
    If no registrar is passed, selects the default active registrar from DB,
    or falls back to MockRegistrarDriver if none configured.
    """
    if registrar is None:
        from domains.models import DomainRegistrar
        registrar = DomainRegistrar.objects.filter(is_active=True, is_default=True).first()
        if not registrar:
            registrar = DomainRegistrar.objects.filter(is_active=True).first()

    if registrar is None:
        logger.debug("No registrar configured in DB — using MockRegistrarDriver.")
        return MockRegistrarDriver(api_user="demo", api_key="demo", is_sandbox=True)

    driver_name = (driver_type or registrar.driver).lower()
    driver_class = _REGISTRAR_REGISTRY.get(driver_name)

    if driver_class is None:
        raise RegistrarDriverError(
            f"Unsupported domain registrar driver: '{driver_name}'. "
            f"Registered drivers: {list(_REGISTRAR_REGISTRY.keys())}"
        )

    # Decrypt API key just-in-time
    try:
        api_key = registrar.get_api_key()
    except Exception as exc:
        raise RegistrarDriverError(f"Failed to decrypt API key for registrar {registrar.name}: {exc}")

    return driver_class(
        api_user=registrar.api_user,
        api_key=api_key,
        is_sandbox=registrar.is_sandbox,
        extra_config=registrar.extra_config or {},
    )


def register_registrar_driver(name: str, driver_class: Type[BaseRegistrarDriver]) -> None:
    """Register custom registrar driver at runtime."""
    _REGISTRAR_REGISTRY[name.lower()] = driver_class
    logger.info("Registered domain registrar driver: '%s'", name)
