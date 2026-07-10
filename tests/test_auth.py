import os
import sys
import time
from pathlib import Path

import jwt
import pytest

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")

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


class _FakeDB:
    def __init__(self, conn):
        self.conn = conn


class _FakeAppState:
    def __init__(self, conn):
        self.db = _FakeDB(conn)


class _FakeApp:
    def __init__(self, conn):
        self.state = _FakeAppState(conn)


def _request_with_cookie_and_app(token: str, conn: object) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", f"session={token}".encode())],
        "query_string": b"",
        "app": _FakeApp(conn),
    }
    return Request(scope)


def test_require_onboarding_complete_passes_through_when_complete(monkeypatch) -> None:
    import auth
    from auth import require_onboarding_complete

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": True,
            "profile_complete": True,
            "search_complete": True,
            "llm_provider_complete": True,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    result = require_onboarding_complete(request)
    assert result["sub"] == "user-uuid-123"


def test_require_onboarding_complete_redirects_to_profile_when_profile_incomplete(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete
    from fastapi import HTTPException

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": False,
            "search_complete": False,
            "llm_provider_complete": False,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    with pytest.raises(HTTPException) as exc:
        require_onboarding_complete(request)
    assert exc.value.status_code == 302
    assert exc.value.headers["location"] == "/profile"


def test_require_onboarding_complete_redirects_to_settings_when_only_search_incomplete(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete
    from fastapi import HTTPException

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": True,
            "search_complete": False,
            "llm_provider_complete": False,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    with pytest.raises(HTTPException) as exc:
        require_onboarding_complete(request)
    assert exc.value.status_code == 302
    assert exc.value.headers["location"] == "/settings"


def test_require_onboarding_complete_redirects_to_settings_when_only_hf_token_incomplete(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete
    from fastapi import HTTPException

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": True,
            "search_complete": True,
            "llm_provider_complete": False,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    with pytest.raises(HTTPException) as exc:
        require_onboarding_complete(request)
    assert exc.value.status_code == 302
    assert exc.value.headers["location"] == "/settings"


def test_require_onboarding_complete_api_passes_through_when_complete(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete_api

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": True,
            "profile_complete": True,
            "search_complete": True,
            "llm_provider_complete": True,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    result = require_onboarding_complete_api(request)
    assert result["sub"] == "user-uuid-123"


def test_require_onboarding_complete_api_raises_403_with_profile_redirect(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete_api
    from fastapi import HTTPException

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": False,
            "search_complete": False,
            "llm_provider_complete": False,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    with pytest.raises(HTTPException) as exc:
        require_onboarding_complete_api(request)
    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "error": "onboarding_incomplete",
        "redirect": "/profile",
    }


def test_require_onboarding_complete_api_raises_403_with_settings_redirect(
    monkeypatch,
) -> None:
    import auth
    from auth import require_onboarding_complete_api
    from fastapi import HTTPException

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    monkeypatch.setattr(
        auth.user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": True,
            "search_complete": False,
            "llm_provider_complete": False,
        },
    )
    request = _request_with_cookie_and_app(token, conn=object())
    with pytest.raises(HTTPException) as exc:
        require_onboarding_complete_api(request)
    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "error": "onboarding_incomplete",
        "redirect": "/settings",
    }


def test_get_current_user_api_valid_token() -> None:
    from auth import get_current_user_api

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret)
    user = get_current_user_api(_request_with_cookie(token))
    assert user["sub"] == "user-uuid-123"
    assert user["email"] == "test@example.com"


def test_get_current_user_api_missing_token_raises_401() -> None:
    from fastapi import HTTPException

    from auth import get_current_user_api

    with pytest.raises(HTTPException) as exc:
        get_current_user_api(_request_no_auth())
    assert exc.value.status_code == 401


def test_get_current_user_api_expired_token_raises_401() -> None:
    from fastapi import HTTPException

    from auth import get_current_user_api

    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = _make_token(secret, exp_offset=-10)
    with pytest.raises(HTTPException) as exc:
        get_current_user_api(_request_with_cookie(token))
    assert exc.value.status_code == 401
