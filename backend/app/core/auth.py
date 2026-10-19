"""Verify the caller's Supabase session on API requests.

The frontend sends the user's Supabase access token as `Authorization: Bearer <token>`.
Supabase itself validates it (GET /auth/v1/user), so no JWT secret is needed here.
Valid tokens are cached briefly, keyed by a SHA-256 of the token, so only a user's
first request pays the ~0.5 s verification round trip.
"""
import hashlib
import time
from collections import OrderedDict

import httpx
from fastapi import Request

from app.core.config import SUPABASE_KEY, SUPABASE_URL

CACHE_TTL_S = 60
_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
_http: httpx.AsyncClient | None = None


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


async def start() -> None:
    global _http
    _http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0))


async def stop() -> None:
    if _http is not None:
        await _http.aclose()


async def require_user(request: Request) -> str:
    """Return the Supabase user id, or raise AuthError (401/503)."""
    if not configured():
        raise AuthError("auth_not_configured", "Server authentication is not configured (SUPABASE_URL / SUPABASE_KEY).", 503)
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthError("unauthorized", "Please sign in to use LawTalk.", 401)

    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        resp = await _http.get(f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
                               headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        raise AuthError("auth_unavailable", "Could not verify your session. Please try again.", 503)
    if resp.status_code in (401, 403):
        raise AuthError("unauthorized", "Your session has expired. Please sign in again.", 401)
    if resp.status_code != 200:
        raise AuthError("auth_unavailable", "Could not verify your session. Please try again.", 503)
    user_id = resp.json().get("id", "")
    _cache[key] = (now + CACHE_TTL_S, user_id)
    if len(_cache) > 1000:
        _cache.popitem(last=False)
    return user_id
