"""
Core DRF Exception Handler
============================
Maps HostPro's custom exception hierarchy to structured, consistent API responses.

Response format for ALL errors:
{
    "error_code": "PROVISIONING_FAILED",
    "message": "Human-readable description",
    "detail": {...}   # Optional structured context
}

Register in settings.py:
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'core.exceptions_handler.custom_exception_handler',
    }
"""

import logging
from typing import Optional

from rest_framework.views import exception_handler as drf_default_handler
from rest_framework.response import Response
from rest_framework import status

from .exceptions import HostProBaseException

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    """
    Intercept all exceptions and return a standardised JSON response.

    Processing order:
      1. Our custom HostProBaseException subclasses → structured response
      2. DRF's built-in exceptions (ValidationError, NotFound, etc.) → DRF handling
      3. Unexpected Python exceptions → 500 with generic message
    """

    # ── 1. HostPro custom exceptions ──────────────────────────────────────
    if isinstance(exc, HostProBaseException):
        logger.error(
            "HostPro exception: %s | %s | detail=%s",
            exc.error_code, exc.message, exc.detail,
            exc_info=True,
        )
        return Response(
            {
                "error_code": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
            },
            status=exc.http_status,
        )

    # ── 2. Standard DRF exceptions ────────────────────────────────────────
    response = drf_default_handler(exc, context)
    if response is not None:
        # Wrap DRF's response in our standard envelope
        response.data = {
            "error_code": "VALIDATION_ERROR" if response.status_code == 400 else "API_ERROR",
            "message": "Request failed.",
            "detail": response.data,
        }
        return response

    # ── 3. Unexpected Python exceptions ───────────────────────────────────
    logger.critical("Unhandled exception in view: %s", exc, exc_info=True)
    return Response(
        {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Our team has been notified.",
            "detail": None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
