from __future__ import annotations

import os

import jwt
import user_data
from fastapi import HTTPException, Request, Response

_COOKIE_SESSION = "session"
_COOKIE_REFRESH = "refresh"
_COOKIE_MAX_AGE_SESSION = 3600
_COOKIE_MAX_AGE_REFRESH = 604800

CurrentUser = dict

_DEV_USER: CurrentUser = {"sub": "dev-user-local", "email": "arnaud@local"}
_DEV_AUTO_LOGIN: bool = os.getenv("DEV_AUTO_LOGIN") == "true"

# Cached JWKS client — created lazily so tests can set env vars first.
_jwks_client: jwt.PyJWKClient | None = None
_jwks_unavailable: bool = False


def _get_jwks_client() -> jwt.PyJWKClient | None:
    global _jwks_client, _jwks_unavailable
    if _jwks_unavailable:
        return None
    if _jwks_client is not None:
        return _jwks_client
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url:
        return None
    _jwks_client = jwt.PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _decode_token(token: str) -> dict:
    """Decode a Supabase JWT using JWKS (ES256) with HS256 fallback for tests."""
    client = _get_jwks_client()
    if client is not None:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256", "HS256"],
                audience="authenticated",
            )
        except jwt.PyJWKClientError:
            _jwks_unavailable = True  # skip future JWKS attempts until restart

    # HS256 fallback (used in tests where SUPABASE_URL is not set)
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise jwt.InvalidTokenError("No JWT secret configured")
    return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")


def validate_access_token(token: str) -> CurrentUser:
    """Verify token signature and expiry. Raises HTTPException(401) if invalid."""
    try:
        payload = _decode_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return {"sub": payload["sub"], "email": payload.get("email", "")}


def get_current_user(request: Request) -> CurrentUser:
    if _DEV_AUTO_LOGIN:
        return _DEV_USER
    token = request.cookies.get(_COOKIE_SESSION)
    if not token:
        raise HTTPException(status_code=302, headers={"location": "/login"})
    try:
        payload = _decode_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=302, headers={"location": "/login"})
    return {"sub": payload["sub"], "email": payload.get("email", "")}


def get_current_user_api(request: Request) -> CurrentUser:
    """Like get_current_user, but raises a 401 instead of redirecting —
    for /api/* JSON routes consumed by the Next.js frontend."""
    if _DEV_AUTO_LOGIN:
        return _DEV_USER
    token = request.cookies.get(_COOKIE_SESSION)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = _decode_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"sub": payload["sub"], "email": payload.get("email", "")}


def require_onboarding_complete(request: Request) -> CurrentUser:
    current_user = get_current_user(request)
    conn = request.app.state.db.conn
    state = user_data.get_onboarding_state(conn, current_user["sub"])
    if state["is_complete"]:
        return current_user
    if not state["profile_complete"]:
        raise HTTPException(status_code=302, headers={"location": "/profile"})
    raise HTTPException(status_code=302, headers={"location": "/settings"})


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        _COOKIE_SESSION,
        access_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=_COOKIE_MAX_AGE_SESSION,
        secure=secure,
    )
    response.set_cookie(
        _COOKIE_REFRESH,
        refresh_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=_COOKIE_MAX_AGE_REFRESH,
        secure=secure,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(_COOKIE_SESSION, path="/")
    response.delete_cookie(_COOKIE_REFRESH, path="/")
