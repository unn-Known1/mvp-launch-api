"""
Credential encryption utility for database connectors.
Encrypts credentials at rest using Fernet symmetric encryption.
"""

import base64
import os
import sys

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_encryption_key() -> bytes:
    """Get encryption key from environment or generate a deterministic one for development.

    SECURITY: In production, CREDENTIAL_ENCRYPTION_KEY must be set. The deterministic
    fallback is only available when ENVIRONMENT=development to avoid accidental exposure.
    """
    key_env = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if key_env:
        if len(key_env) == 44:
            return key_env.encode()
        raise ValueError(
            "CREDENTIAL_ENCRYPTION_KEY must be exactly 44 characters (Fernet key)"
        )

    # In non-development environments, do not allow fallback - require proper configuration
    environment = os.getenv("ENVIRONMENT", "development")
    if environment != "development":
        raise ValueError(
            "CREDENTIAL_ENCRYPTION_KEY environment variable is required in production. "
            "Generate a secure key using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    # Development-only fallback with explicit hardcoded salt and password
    # This is intentional for local dev only - not for any non-dev environment
    if environment == "development":
        import warnings
        warnings.warn(
            "SECURITY WARNING: Using deterministic encryption key in development mode. "
            "Do NOT use this in production! Set CREDENTIAL_ENCRYPTION_KEY environment variable instead.",
            RuntimeWarning,
            stacklevel=2
        )
        # Use fixed salt and password for development convenience
        salt = b"forge-intelligence-dev-salt"  # Hardcoded dev salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        password = b"development-key-derivation-password"  # Hardcoded dev password
        key_material = kdf.derive(password)
        return base64.urlsafe_b64encode(key_material)


_encryption_key = None


def get_fernet() -> Fernet:
    """Get or create Fernet instance for encryption/decryption."""
    global _encryption_key
    if _encryption_key is None:
        _encryption_key = _get_encryption_key()
    return Fernet(_encryption_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value and return base64-encoded ciphertext."""
    fernet = get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return the original string."""
    fernet = get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()
