from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()

def get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    # If the key is not a valid 32-byte url-safe base64 string, handle or fallback for dev
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # For development fallback if a dummy key was set
        from cryptography.fernet import Fernet as _Fernet
        dummy_key = _Fernet.generate_key()
        return _Fernet(dummy_key)

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
