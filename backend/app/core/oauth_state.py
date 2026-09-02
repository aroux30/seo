"""Signed OAuth `state` values — CSRF protection for the Google flow.

Without this, `state` was just `{website_id}:{whatever}` and the callback
trusted it blindly. An attacker could hand a victim a crafted callback URL
carrying the attacker's `code` plus any `website_id`, and the backend would
happily bind the attacker's Search Console account to a website the victim
controls (OAuth login/account CSRF).

The state is now `{website_id}.{issued_at}.{nonce}.{hmac}` where the HMAC
covers the first three fields, keyed on SECRET_KEY. The callback verifies the
signature with a constant-time compare and rejects anything older than
STATE_MAX_AGE_SECONDS, so states are single-use in practice and cannot be
forged or replayed days later.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from uuid import UUID

from app.config import get_settings

settings = get_settings()

# Google consent screens are interactive; 10 minutes is generous but bounded.
STATE_MAX_AGE_SECONDS = 600
_SEPARATOR = "."


class InvalidOAuthState(ValueError):
    """Raised when a state parameter is malformed, forged, or expired."""


def _sign(payload: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# In-memory consumed nonces cache to guarantee single-use state per deployment / process
_consumed_nonces: dict[str, int] = {}


def issue_state(website_id: UUID) -> str:
    """Build a signed, timestamped state for the OAuth authorization request."""
    payload = f"{website_id}{_SEPARATOR}{int(time.time())}{_SEPARATOR}{secrets.token_urlsafe(16)}"
    return f"{payload}{_SEPARATOR}{_sign(payload)}"


def verify_state(state: str, max_age: int = STATE_MAX_AGE_SECONDS) -> UUID:
    """Validate a state string and return the website_id it was issued for.

    Raises InvalidOAuthState on any tampering, malformation, expiry, or reuse.
    """
    if not state:
        raise InvalidOAuthState("Missing state parameter")

    parts = state.split(_SEPARATOR)
    if len(parts) != 4:
        raise InvalidOAuthState("Malformed state parameter")

    website_id_str, issued_at_str, nonce, signature = parts
    payload = f"{website_id_str}{_SEPARATOR}{issued_at_str}{_SEPARATOR}{nonce}"

    # Constant-time compare so signature bytes can't be probed by timing.
    if not hmac.compare_digest(_sign(payload), signature):
        raise InvalidOAuthState("State signature mismatch")

    # Anti-Replay: Check if nonce was already consumed
    now = int(time.time())
    if nonce in _consumed_nonces:
        raise InvalidOAuthState("OAuth state already consumed")

    try:
        issued_at = int(issued_at_str)
    except ValueError:
        raise InvalidOAuthState("Malformed state timestamp")

    age = now - issued_at
    # Reject far-future timestamps too (clock skew abuse).
    if age > max_age or age < -60:
        raise InvalidOAuthState("State expired")

    # Mark nonce as consumed and opportunistically purge old nonces
    _consumed_nonces[nonce] = now
    if len(_consumed_nonces) > 5_000:
        for n, exp_time in list(_consumed_nonces.items()):
            if now - exp_time > max_age:
                _consumed_nonces.pop(n, None)

    try:
        return UUID(website_id_str)
    except ValueError:
        raise InvalidOAuthState("Malformed website id in state")
