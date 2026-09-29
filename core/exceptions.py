"""
HostPro - Core Exception Classes
==================================
Centralised exception hierarchy for the entire platform.
Using custom exceptions instead of bare Django exceptions lets us:
  - Attach structured metadata (error_code, http_status)
  - Translate them uniformly in DRF exception_handler
  - Make unit tests more meaningful with assertRaises(ProvisioningError)
"""
from typing import Any


class HostProBaseException(Exception):
    """Root exception for all HostPro errors."""

    #: Machine-readable error code surfaced in API responses
    error_code: str = "HOSTPRO_ERROR"
    #: Default HTTP status code for DRF handler
    http_status: int = 500

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail  # Extra structured context (dict, list, etc.)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.error_code!r}, {self.message!r})"


# ─── Server / Provisioning ────────────────────────────────────────────────────

class ServerDriverError(HostProBaseException):
    """Raised when a server panel driver (cPanel, CyberPanel) call fails."""
    error_code = "SERVER_DRIVER_ERROR"
    http_status = 502


class ProvisioningError(ServerDriverError):
    """Raised when account creation on a server fails."""
    error_code = "PROVISIONING_FAILED"


class SuspensionError(ServerDriverError):
    """Raised when suspending/unsuspending an account fails."""
    error_code = "SUSPENSION_FAILED"


class TerminationError(ServerDriverError):
    """Raised when terminating an account fails."""
    error_code = "TERMINATION_FAILED"


# ─── Domain Registrar ─────────────────────────────────────────────────────────

class RegistrarDriverError(HostProBaseException):
    """Raised when a domain registrar API call fails."""
    error_code = "REGISTRAR_DRIVER_ERROR"
    http_status = 502


class DomainRegistrationError(RegistrarDriverError):
    """Raised when domain registration fails."""
    error_code = "DOMAIN_REGISTRATION_FAILED"


class DomainTransferError(RegistrarDriverError):
    """Raised when domain transfer fails."""
    error_code = "DOMAIN_TRANSFER_FAILED"


class DomainRenewalError(RegistrarDriverError):
    """Raised when domain renewal fails."""
    error_code = "DOMAIN_RENEWAL_FAILED"


# ─── Billing / Payment ────────────────────────────────────────────────────────

class BillingError(HostProBaseException):
    """Base class for billing errors."""
    error_code = "BILLING_ERROR"
    http_status = 400


class PaymentGatewayError(BillingError):
    """Raised when a payment gateway (bKash, Nagad, SSL) call fails."""
    error_code = "PAYMENT_GATEWAY_ERROR"
    http_status = 502


class InvalidIPNSignature(BillingError):
    """Raised when IPN/webhook signature verification fails."""
    error_code = "INVALID_IPN_SIGNATURE"
    http_status = 400


class InvoiceAlreadyPaid(BillingError):
    """Raised when trying to pay an already-paid invoice."""
    error_code = "INVOICE_ALREADY_PAID"
    http_status = 409


# ─── Encryption ───────────────────────────────────────────────────────────────

class EncryptionError(HostProBaseException):
    """Raised when encryption/decryption fails."""
    error_code = "ENCRYPTION_ERROR"
    http_status = 500
