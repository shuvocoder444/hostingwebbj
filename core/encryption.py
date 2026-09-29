"""
HostPro Encryption Utilities
==============================
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) to encrypt
sensitive fields like WHM tokens, registrar API keys, payment gateway secrets.

The encryption key is stored in the environment (FIELD_ENCRYPTION_KEY) and
NEVER in the database. This means a compromised DB dump is useless without
the key.

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

# Load key once at module import — fail loudly if missing or invalid
_ENCRYPTION_KEY: bytes = config("FIELD_ENCRYPTION_KEY", default="", cast=lambda v: v.encode())

# Only initialise Fernet if a key is configured (allows test environments without key)
try:
    _fernet = Fernet(_ENCRYPTION_KEY) if _ENCRYPTION_KEY else None
except Exception:
    _fernet = None


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string and return a base64-encoded ciphertext string.

    Args:
        plaintext: The sensitive value to encrypt (e.g., API token).

    Returns:
        Base64-encoded encrypted string, safe to store in the database.

    Raises:
        ValueError: If the plaintext is empty or encryption key is not configured.
    """
    if not plaintext:
        raise ValueError("Cannot encrypt an empty value.")
    if _fernet is None:
        raise ValueError("FIELD_ENCRYPTION_KEY is not configured.")

    ciphertext_bytes: bytes = _fernet.encrypt(plaintext.encode("utf-8"))
    # Fernet output is URL-safe base64; decode to str for DB storage
    return ciphertext_bytes.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string previously encrypted with `encrypt()`.

    Args:
        ciphertext: The encrypted value from the database.

    Returns:
        The original plaintext string.

    Raises:
        ValueError: If decryption fails (wrong key, corrupted data, or key not configured).
    """
    if not ciphertext:
        raise ValueError("Cannot decrypt an empty value.")
    if _fernet is None:
        raise ValueError("FIELD_ENCRYPTION_KEY is not configured.")

    try:
        plaintext_bytes: bytes = _fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext_bytes.decode("utf-8")
    except InvalidToken as exc:
        # Log without revealing ciphertext content; raise sanitized error for callers
        logger.error("Decryption failed — possible key mismatch or data corruption.")
        raise ValueError("Decryption failed: invalid token or wrong key.") from exc
