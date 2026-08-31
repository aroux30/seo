import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
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
    # Deterministic fallback derived from SECRET_KEY + ENCRYPTION_KEY
    seed = (str(key or "") + ":" + str(settings.SECRET_KEY or "seoos-fallback-secret")).encode("utf-8")
    derived = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
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
