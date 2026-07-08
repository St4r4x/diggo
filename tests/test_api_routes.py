import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

from fastapi.testclient import TestClient

MOCK_USER = {"sub": "test-user-uuid-fixture", "email": "test@example.com"}


@pytest.fixture
def client():
    import app as dashboard_app
    from auth import get_current_user_api

    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.pop(get_current_user_api, None)


def test_health_returns_ok_without_auth(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_returns_401_without_auth(client) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401


def test_me_returns_current_user_when_authenticated(client) -> None:
    import app as dashboard_app
    from auth import get_current_user_api

    dashboard_app.app.dependency_overrides[get_current_user_api] = lambda: MOCK_USER
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == MOCK_USER
