"""The signed value carried in the session cookie.

The payload is signed, not encrypted: the account name and expiry are
readable in the cookie. That is deliberate -- neither is a secret, and
keeping them readable means a bad cookie can be diagnosed by looking at
it. What the signature buys is integrity: nobody can hand-write a cookie
naming an account they could not authenticate as, or extend their own
session by editing the expiry.
"""

import base64
import hmac
import secrets
import time

from app.config import settings

ONE_YEAR = 365 * 24 * 60 * 60
COOKIE_NAME = "drogo_session"

# Used only when SESSION_SECRET is unset. Regenerated every boot, so
# sessions survive until the next restart and never fall back to signing
# with an empty, guessable key.
_BOOT_SECRET = secrets.token_urlsafe(32)


def current_secret() -> str:
    return settings.session_secret or _BOOT_SECRET


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), "sha256").digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def issue(
    account: str, *, secret: str, now: float | None = None, max_age: int = ONE_YEAR
) -> str:
    expires_at = int((time.time() if now is None else now) + max_age)
    payload = f"{account}|{expires_at}"
    return f"{payload}.{_sign(payload, secret)}"


def verify(token: str, *, secret: str, now: float | None = None) -> str | None:
    """Return the account the token names, or None if it is not trustworthy."""
    payload, separator, signature = token.rpartition(".")
    if not separator:
        return None
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return None

    account, separator, expires_at = payload.rpartition("|")
    if not separator:
        return None
    try:
        if (time.time() if now is None else now) >= int(expires_at):
            return None
    except ValueError:
        return None
    return account
