"""
Server Driver Factory
======================
Returns the correct driver instance for a given Server model instance.

This is the single point of driver selection — the rest of the codebase
calls get_driver(server) without knowing which panel type is in use.

Adding support for a new panel (e.g. DirectAdmin):
  1. Create drivers/directadmin.py implementing BaseServerDriver
  2. Call register_driver('directadmin', DirectAdminDriver)
  That's it — zero changes to provisioning logic.
"""
import logging
from typing import TYPE_CHECKING

from core.exceptions import ServerDriverError
from .base import BaseServerDriver
from .cpanel import CPanelDriver
from .cyberpanel import CyberPanelDriver

if TYPE_CHECKING:
    from hosting.models import Server

logger = logging.getLogger(__name__)

# Registry: ServerDriver choice value → driver class
_DRIVER_REGISTRY: dict[str, type[BaseServerDriver]] = {
    'cpanel': CPanelDriver,
    'cyberpanel': CyberPanelDriver,
}


def get_driver(server: 'Server') -> BaseServerDriver:
    """
    Instantiate and return the correct driver for the given server.

    Args:
        server: A Server model instance (encrypted token stored in DB).

    Returns:
        Initialised driver ready to call create_account(), suspend_account(), etc.

    Raises:
        ServerDriverError: If the server's driver type is not registered,
                           or if token decryption fails.
    """
    driver_class = _DRIVER_REGISTRY.get(server.driver)

    if driver_class is None:
        raise ServerDriverError(
            f"Unsupported server driver: '{server.driver}'. "
            f"Registered drivers: {list(_DRIVER_REGISTRY.keys())}"
        )

    # Decrypt the API token just-in-time — never hold plaintext longer than needed
    try:
        api_token = server.get_api_token()
    except ValueError as exc:
        raise ServerDriverError(
            f"Failed to decrypt API token for server '{server.name}': {exc}"
        )

    logger.debug("Using driver '%s' for server '%s'", server.driver, server.name)

    return driver_class(
        host=server.hostname,
        port=server.port,
        username=server.api_username,
        api_token=api_token,
        use_ssl=True,
    )


def register_driver(name: str, driver_class: type[BaseServerDriver]) -> None:
    """
    Register a custom driver class at runtime.
    Allows third-party apps to add new panel support without modifying core code.

    Usage (e.g. in AppConfig.ready()):
        from hosting.drivers.factory import register_driver
        from myplugin.directadmin import DirectAdminDriver
        register_driver('directadmin', DirectAdminDriver)
    """
    _DRIVER_REGISTRY[name] = driver_class
    logger.info("Registered server driver: '%s' → %s", name, driver_class.__name__)
