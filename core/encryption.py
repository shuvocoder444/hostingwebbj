"""
HostPro Encryption Utilities
==============================
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) to encrypt
sensitive fields like WHM tokens, registrar API keys, payment gateway secrets.

The encryption key is stored in the environment (FIELD_ENCRYPTION_KEY) or settings.
Never stores plaintext API tokens in the database.

Usage:
    from core.encryption import encrypt, decrypt

    # Encrypting before saving
    server.set_api_token(raw_token)   # Use the model method
    server.save()

    # Decrypting at runtime for API calls
    raw_token = server.get_api_token()
"""

import logging
from cryptography.fernet import Fernet, InvalidToken
from decouple import config

logger = logging.getLogger(__name__)

def _get_encryption_key() -> bytes:
    """
    Retrieves the 32-byte URL-safe base64 Fernet key.
    Requires the configured FIELD_ENCRYPTION_KEY. Never substitute a known key.
    """
    key = config("FIELD_ENCRYPTION_KEY", default="").strip()
    if key:
        return key.encode("utf-8")

    try:
        from django.conf import settings
        key = getattr(settings, "FIELD_ENCRYPTION_KEY", "").strip()
        if key:
            return key.encode("utf-8")

    except Exception as exc:
        raise RuntimeError("FIELD_ENCRYPTION_KEY is not configured.") from exc

    raise RuntimeError("FIELD_ENCRYPTION_KEY is not configured.")


def _get_fernet() -> Fernet:
    key_bytes = _get_encryption_key()
    try:
        return Fernet(key_bytes)
    except Exception as exc:
        logger.exception("FIELD_ENCRYPTION_KEY is invalid.")
        raise RuntimeError("FIELD_ENCRYPTION_KEY must be a valid Fernet key.") from exc


# Fernet instance
_fernet = None


def get_fernet_instance() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _get_fernet()
    return _fernet


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string and return a base64-encoded ciphertext string.

    Args:
        plaintext: The sensitive value to encrypt (e.g., API token).

    Returns:
        Base64-encoded encrypted string, safe to store in the database.

    Raises:
        ValueError: If the plaintext is empty.
    """
    if not plaintext:
        raise ValueError("Cannot encrypt an empty value.")

    fernet = get_fernet_instance()
    ciphertext_bytes: bytes = fernet.encrypt(plaintext.encode("utf-8"))
    return ciphertext_bytes.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string previously encrypted with `encrypt()`.

    Args:
        ciphertext: The encrypted value from the database.

    Returns:
        The original plaintext string.

    Raises:
        ValueError: If decryption fails (corrupted data or wrong key).
    """
    if not ciphertext:
        raise ValueError("Cannot decrypt an empty value.")

    fernet = get_fernet_instance()
    try:
        plaintext_bytes: bytes = fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext_bytes.decode("utf-8")
    except InvalidToken as exc:
        logger.error("Decryption failed — possible key mismatch or data corruption.")
        raise ValueError("Decryption failed: invalid token or wrong key.") from exc
