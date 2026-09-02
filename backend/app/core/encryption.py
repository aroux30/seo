import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()

import base64
import os
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from app.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()

def get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if key and isinstance(key, str) and len(key) == 44:
        try:
            return Fernet(key.encode("utf-8"))
        except Exception:
            pass
    # Secure PBKDF2 HMAC derivation with pinned salt when ENCRYPTION_KEY is derived
    secret_material = (str(settings.SECRET_KEY or "seoos-fallback-secret")).encode("utf-8")
    salt = b"ai_seo_os_kdf_salt_v1"  # Static salt to maintain deterministic decryption
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(secret_material))
    return Fernet(derived)

def encrypt_value(value: str) -> str:
    """Encrypt a sensitive string (e.g., OAuth token, API key)."""
    if not value:
        return value
    f = get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a previously encrypted string."""
    if not encrypted_value:
        return encrypted_value
    f = get_fernet()
    try:
        return f.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise AppException(status_code=500, detail="Failed to decrypt sensitive data", error_type="encryption_error")
