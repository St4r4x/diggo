import os
import sys
import time
from pathlib import Path

import jwt
import pytest

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

from fastapi import Request


def _make_token(secret: str, sub: str = "user-uuid-123", exp_offset: int = 3600) -> str:
    payload = {
        "sub": sub,
        "email": "test@example.com",
        "exp": int(time.time()) + exp_offset,
        "aud": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _request_with_auth(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


def _request_no_auth() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    return Request(scope)


def _request_with_cookie(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", f"session={token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


def test_get_current_user_valid_token() -> None:
    from auth import get_current_user

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    user = get_current_user(_request_with_cookie(token))
    assert user["sub"] == "user-uuid-123"
    assert user["email"] == "test@example.com"


def test_get_current_user_missing_token() -> None:
    from fastapi import HTTPException

    from auth import get_current_user

    with pytest.raises(HTTPException) as exc:
        get_current_user(_request_no_auth())
    assert exc.value.status_code == 302
    assert exc.value.headers["location"] == "/login"


def test_get_current_user_expired_token() -> None:
    from fastapi import HTTPException

    from auth import get_current_user

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret, exp_offset=-10)
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request_with_cookie(token))
    assert exc.value.status_code == 302


def test_get_current_user_wrong_secret() -> None:
    from fastapi import HTTPException

    from auth import get_current_user

    token = _make_token("wrong-secret-32-chars-minimum-paddd")
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request_with_cookie(token))
    assert exc.value.status_code == 302


def test_get_current_user_expired_cookie_redirects() -> None:
    from fastapi import HTTPException

    from auth import get_current_user

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret, exp_offset=-10)
    with pytest.raises(HTTPException) as exc:
        get_current_user(_request_with_cookie(token))
    assert exc.value.status_code == 302
    assert exc.value.headers["location"] == "/login"
