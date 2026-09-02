import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid4
import secrets

from jose import jwt, JWTError
import bcrypt

from app.config import get_settings

settings = get_settings()

ROLE_HIERARCHY = {
    "owner": 60,
    "admin": 50,
    "seo_manager": 40,
    "editor": 30,
    "reviewer": 20,
    "viewer": 10,
}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)


def create_access_token(user_id: UUID, org_id: UUID | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    if org_id:
        payload["org"] = str(org_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def create_reset_token(email: str, nonce: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {
        "sub": email,
        "exp": expire,
        "type": "reset",
        "jti": str(uuid4()),
    }
    if nonce:
        payload["nonce"] = nonce
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_reset_token(token: str) -> dict:
    """Decode and validate a reset token, returning the payload. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "reset":
        raise JWTError("Invalid token type")
    return payload


def role_has_permission(user_role: str, required_role: str) -> bool:
    """Check if user_role is at or above required_role in hierarchy."""
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 100)
