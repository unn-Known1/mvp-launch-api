"""
Credential encryption utility for database connectors.
Encrypts credentials at rest using Fernet symmetric encryption.
"""

import os

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_encryption_key() -> bytes:
    """Get encryption key from environment or generate a deterministic one for development."""
    key_env = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if key_env:
        if len(key_env) == 44:
            return key_env.encode()
        raise ValueError(
            "CREDENTIAL_ENCRYPTION_KEY must be exactly 44 characters (Fernet key)"
        )

    # Use PBKDF2 for deterministic key generation in development
    salt = os.environ.get(
        "CREDENTIAL_ENCRYPTION_SALT", "forge-intelligence-dev-salt"
    ).encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend(),
    )
    # Derive key from password - use a consistent password for dev
    password = os.environ.get(
        "CREDENTIAL_KEY_PASSWORD", "development-key-derivation-password"
    ).encode()
    key_material = kdf.derive(password)
    # Convert to Fernet-compatible format (base64-encoded 32-byte key)
    return Fernet.generate_key_from_password(key_material, hashes.SHA256())


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
