"""Authentication and signed log-link helpers."""

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

from fastapi import HTTPException, Request


def require_notify_auth(request: Request, expected_token: str | None) -> None:
    """Require a Bearer token only when an operator configured one."""
    if expected_token is None:
        return

    scheme, _, supplied_token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def make_log_signature(secret: str, log_id: str, expires: int) -> str:
    message = f"{log_id}:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def signed_log_url(base_url: str, log_id: str, secret: str, ttl_hours: int) -> str:
    expires = int(time.time()) + ttl_hours * 3600
    signature = make_log_signature(secret, log_id, expires)
    return f"{base_url.rstrip('/')}?{urlencode({'expires': expires, 'sig': signature})}"


def verify_log_signature(
    log_id: str, expires: int | None, signature: str | None, secret: str
) -> None:
    if expires is None or signature is None or expires < int(time.time()):
        raise HTTPException(status_code=403, detail="Invalid or expired log link")

    expected = make_log_signature(secret, log_id, expires)
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid or expired log link")
