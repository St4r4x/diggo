import os
import sys
from pathlib import Path

import psycopg2
import pytest

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

from fastapi.testclient import TestClient

MOCK_USER = {"sub": "test-user-uuid-fixture", "email": "test@example.com"}

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)

_CREATE_TEMP = """
CREATE TEMP TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL DEFAULT 'test-user-uuid-fixture',
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    offer_url TEXT NOT NULL DEFAULT '',
    detection_date TEXT NOT NULL,
    score_grade TEXT NOT NULL DEFAULT '',
    score_value FLOAT NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'À envoyer',
    send_date TEXT,
    contacts TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    cv_path TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '',
    prep_sheet_path TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT,
    description TEXT NOT NULL DEFAULT '',
    portal TEXT NOT NULL DEFAULT ''
)
"""


def _make_pg_db():
    from db import DB

    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_TEMP)
    conn.commit()
    return DB(conn)


def _insert_row(
    db,
    company: str = "Acme",
    role: str = "ML Engineer",
    offer_url: str = "https://example.com/1",
    detection_date: str = "2026-05-25",
    score_grade: str = "B",
    score_value: float = 4.0,
    status: str = "À envoyer",
    send_date: str | None = None,
    user_id: str = MOCK_USER["sub"],
    description: str = "",
) -> int:
    with db.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applications (user_id, company, role, offer_url, detection_date,"
            " score_grade, score_value, status, send_date, description) VALUES"
            " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                user_id,
                company,
                role,
                offer_url,
                detection_date,
                score_grade,
                score_value,
                status,
                send_date,
                description,
            ),
        )
        row_id = cur.fetchone()[0]
    db.conn.commit()
    return row_id


@pytest.fixture
def client():
    import app as dashboard_app
    from auth import get_current_user_api

    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.pop(get_current_user_api, None)


@pytest.fixture
def client_with_offers():
    import app as dashboard_app
    from auth import require_onboarding_complete_api

    test_db = _make_pg_db()
    dashboard_app.app.state.db = test_db
    dashboard_app.app.dependency_overrides[require_onboarding_complete_api] = lambda: (
        MOCK_USER
    )
    _insert_row(
        test_db,
        company="Mistral AI",
        offer_url="https://jobs.lever.co/mistral/1",
        score_grade="B",
        score_value=4.0,
        status="À envoyer",
        description="Ingénieur ML pour l'équipe recherche.",
    )
    _insert_row(
        test_db,
        company="Doctrine",
        offer_url="https://jobs.lever.co/doctrine/1",
        detection_date="2026-05-24",
        score_grade="A",
        score_value=4.5,
        status="Envoyée",
    )
    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.pop(require_onboarding_complete_api, None)
    test_db.close()


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


def test_session_post_sets_cookies(client) -> None:
    import time

    import jwt

    secret = os.environ["SUPABASE_JWT_SECRET"]
    access_token = jwt.encode(
        {
            "sub": "u1",
            "email": "t@t.com",
            "exp": int(time.time()) + 3600,
            "aud": "authenticated",
        },
        secret,
        algorithm="HS256",
    )
    response = client.post(
        "/api/auth/session",
        json={"access_token": access_token, "refresh_token": "dummy-refresh"},
    )
    assert response.status_code == 200
    assert "session" in response.cookies
    assert "refresh" in response.cookies


def test_session_delete_clears_cookies(client) -> None:
    response = client.delete("/api/auth/session", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_offers_returns_200_with_offers(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers")
    assert response.status_code == 200
    body = response.json()
    companies = {o["company"] for o in body["offers"]}
    assert companies == {"Mistral AI", "Doctrine"}


def test_list_offers_filters_by_status(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers?status=Envoyée")
    companies = {o["company"] for o in response.json()["offers"]}
    assert companies == {"Doctrine"}


def test_list_offers_filters_by_grade(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers?grade=A")
    companies = {o["company"] for o in response.json()["offers"]}
    assert companies == {"Doctrine"}


def test_list_offers_filters_by_search(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers?q=mistral")
    companies = {o["company"] for o in response.json()["offers"]}
    assert companies == {"Mistral AI"}


def test_list_offers_includes_statuses_and_followup_ids(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers")
    body = response.json()
    assert "À envoyer" in body["statuses"]
    assert body["followup_ids"] == []


def test_list_offers_requires_auth(client) -> None:
    response = client.get("/api/offers")
    assert response.status_code == 401


def test_get_offer_returns_200_for_existing(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.get(f"/api/offers/{row['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["offer"]["company"] == row["company"]
    assert "mission" in body["description"]


def test_get_offer_returns_404_for_missing(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers/999")
    assert response.status_code == 404


def test_patch_offer_updates_status(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.patch(
        f"/api/offers/{row['id']}", json={"status": "Envoyée"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["offer"]["status"] == "Envoyée"
    assert "mission" in body["description"]
    updated = db.get_by_id(row["id"], user_id=MOCK_USER["sub"])
    assert updated["status"] == "Envoyée"


def test_patch_offer_rejects_invalid_status(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.patch(
        f"/api/offers/{row['id']}", json={"status": "NotAStatus"}
    )
    assert response.status_code == 422
    updated = db.get_by_id(row["id"], user_id=MOCK_USER["sub"])
    assert updated["status"] == row["status"]


def test_patch_offer_updates_notes(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.patch(
        f"/api/offers/{row['id']}", json={"notes": "Relancer jeudi"}
    )
    assert response.status_code == 200
    updated = db.get_by_id(row["id"], user_id=MOCK_USER["sub"])
    assert updated["notes"] == "Relancer jeudi"


def test_patch_offer_updates_edit_fields(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.patch(
        f"/api/offers/{row['id']}",
        json={
            "company": "Renamed Co",
            "role": "Staff ML Engineer",
            "offer_url": "https://example.com/renamed",
            "send_date": "2026-07-01",
            "follow_up_date": "2026-07-08",
            "contacts": "jane@renamed.co",
        },
    )
    assert response.status_code == 200
    updated = db.get_by_id(row["id"], user_id=MOCK_USER["sub"])
    assert updated["company"] == "Renamed Co"
    assert updated["role"] == "Staff ML Engineer"
    assert updated["send_date"] == "2026-07-01"
    assert updated["follow_up_date"] == "2026-07-08"
    assert updated["contacts"] == "jane@renamed.co"


def test_patch_offer_returns_404_for_missing(client_with_offers) -> None:
    response = client_with_offers.patch("/api/offers/999", json={"notes": "x"})
    assert response.status_code == 404


def test_patch_offer_requires_auth(client) -> None:
    response = client.patch("/api/offers/1", json={"notes": "x"})
    assert response.status_code == 401


def test_delete_offer_removes_row(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.delete(f"/api/offers/{row['id']}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert db.get_by_id(row["id"], user_id=MOCK_USER["sub"]) is None


def test_delete_offer_returns_404_for_missing(client_with_offers) -> None:
    response = client_with_offers.delete("/api/offers/999")
    assert response.status_code == 404


def test_delete_offer_requires_auth(client) -> None:
    response = client.delete("/api/offers/1")
    assert response.status_code == 401
