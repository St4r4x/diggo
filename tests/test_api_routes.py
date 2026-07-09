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

FAKE_PROFILE = {
    "contact": {
        "name": "Test User",
        "title": "AI Engineer",
        "email": "test@example.com",
        "phone": "+33 6 00 00 00 00",
        "location": "Paris",
        "linkedin": "",
        "github": "github.com/testuser",
    },
    "profile_md": "An experienced engineer.",
    "summary": "",
    "experience": [],
    "skills": {},
    "education": [],
    "certifications": [],
    "projects": [],
}

FAKE_CV = {
    "meta": {"summary": "Résumé test."},
    "experience": [
        {
            "id": 1,
            "title": "ML Engineer",
            "company": "Acme",
            "type": "CDI",
            "period": "2022-2024",
            "sort_order": 0,
            "bullets": ["Built things", "Shipped things"],
        }
    ],
    "skills": [
        {"id": 1, "category": "Langages", "skill": "Python", "sort_order": 0},
        {"id": 2, "category": "Langages", "skill": "TypeScript", "sort_order": 1},
    ],
    "certifications": [{"id": 1, "name": "AWS SAA", "issuer": "AWS", "year": 2023}],
    "education": [{"id": 1, "degree": "MSc IA", "school": "Sorbonne", "year": 2021}],
}

FAKE_ONBOARDING = {
    "is_complete": True,
    "profile_complete": True,
    "search_complete": True,
    "hf_token_complete": True,
}

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
    import prepare_state
    from auth import require_onboarding_complete_api

    prepare_state._status.clear()
    prepare_state._stage.clear()
    prepare_state._error.clear()
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


@pytest.fixture
def client_scan():
    import app as dashboard_app
    import scan_state
    from auth import require_onboarding_complete_api

    scan_state._status.clear()
    scan_state._result.clear()
    dashboard_app.app.dependency_overrides[require_onboarding_complete_api] = lambda: (
        MOCK_USER
    )
    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.pop(require_onboarding_complete_api, None)
    scan_state._status.clear()
    scan_state._result.clear()


@pytest.fixture
def client_with_profile(monkeypatch):
    import app as dashboard_app
    import profile_parser
    import user_data
    from auth import get_current_user_api
    from unittest.mock import MagicMock

    monkeypatch.setattr(
        profile_parser, "load_profile", lambda conn, user_id: dict(FAKE_PROFILE)
    )
    monkeypatch.setattr(
        user_data, "get_cv", lambda conn, user_id, lang="fr": dict(FAKE_CV)
    )
    monkeypatch.setattr(
        user_data, "get_onboarding_state", lambda conn, user_id: dict(FAKE_ONBOARDING)
    )
    mock_conn = MagicMock()
    mock_db = MagicMock()
    mock_db.conn = mock_conn
    dashboard_app.app.state.db = mock_db
    dashboard_app.app.dependency_overrides[get_current_user_api] = lambda: MOCK_USER
    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.pop(get_current_user_api, None)


@pytest.fixture
def client_with_profile_mutations(monkeypatch):
    import app as dashboard_app
    import profile_parser
    import user_data
    from auth import get_current_user_api
    from unittest.mock import MagicMock

    mocks = {
        "load_profile": MagicMock(return_value=dict(FAKE_PROFILE)),
        "save_profile": MagicMock(),
        "save_cv_meta": MagicMock(),
        "save_experience": MagicMock(),
        "delete_experience": MagicMock(),
        "save_skills": MagicMock(),
        "save_certifications": MagicMock(),
        "save_education": MagicMock(),
    }
    monkeypatch.setattr(profile_parser, "load_profile", mocks["load_profile"])
    monkeypatch.setattr(profile_parser, "save_profile", mocks["save_profile"])
    monkeypatch.setattr(user_data, "save_cv_meta", mocks["save_cv_meta"])
    monkeypatch.setattr(user_data, "save_experience", mocks["save_experience"])
    monkeypatch.setattr(user_data, "delete_experience", mocks["delete_experience"])
    monkeypatch.setattr(user_data, "save_skills", mocks["save_skills"])
    monkeypatch.setattr(user_data, "save_certifications", mocks["save_certifications"])
    monkeypatch.setattr(user_data, "save_education", mocks["save_education"])

    mock_conn = MagicMock()
    mock_db = MagicMock()
    mock_db.conn = mock_conn
    dashboard_app.app.state.db = mock_db
    dashboard_app.app.dependency_overrides[get_current_user_api] = lambda: MOCK_USER

    yield TestClient(dashboard_app.app), mocks

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


def test_scan_status_idle_by_default(client_scan) -> None:
    response = client_scan.get("/api/scan/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["result"]["inserted"] == 0


def test_scan_start_returns_running(client_scan, monkeypatch) -> None:
    monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close())
    response = client_scan.post("/api/scan/start")
    assert response.status_code == 200
    assert response.json() == {"status": "running"}


def test_scan_start_when_already_running_is_noop(client_scan, monkeypatch) -> None:
    created = []
    monkeypatch.setattr(
        "asyncio.create_task",
        lambda coro: created.append(coro) or coro.close(),
    )
    r1 = client_scan.post("/api/scan/start")
    r2 = client_scan.post("/api/scan/start")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == {"status": "running"}
    assert r2.json() == {"status": "running"}
    assert len(created) == 1


def test_scan_status_after_start_returns_running(client_scan, monkeypatch) -> None:
    monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close())
    client_scan.post("/api/scan/start")
    response = client_scan.get("/api/scan/status")
    assert response.json()["status"] == "running"


def test_scan_status_requires_auth(client) -> None:
    response = client.get("/api/scan/status")
    assert response.status_code == 401


def test_scan_start_requires_auth(client) -> None:
    response = client.post("/api/scan/start")
    assert response.status_code == 401


def test_scan_state_isolated_per_user(client_scan, monkeypatch) -> None:
    import app as dashboard_app
    from auth import require_onboarding_complete_api

    monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close())

    dashboard_app.app.dependency_overrides[require_onboarding_complete_api] = lambda: {
        "sub": "user-a-route-test",
        "email": "a@test.com",
    }
    r1 = client_scan.post("/api/scan/start")
    assert r1.json()["status"] == "running"

    dashboard_app.app.dependency_overrides[require_onboarding_complete_api] = lambda: {
        "sub": "user-b-route-test",
        "email": "b@test.com",
    }
    r2 = client_scan.get("/api/scan/status")
    assert r2.json()["status"] == "idle"


_PREPARE_LONG_DESCRIPTION = (
    "We need an ML engineer with PyTorch and RAG experience. " * 10
)


def test_prepare_start_returns_404_for_missing(client_with_offers) -> None:
    response = client_with_offers.post("/api/offers/999/prepare")
    assert response.status_code == 404


def test_prepare_start_rejects_thin_description(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.post(f"/api/offers/{row['id']}/prepare")
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "description_too_short"


def test_prepare_start_rejects_missing_hf_token(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db, description=_PREPARE_LONG_DESCRIPTION)
    response = client_with_offers.post(f"/api/offers/{offer_id}/prepare")
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "hf_token_missing"


def test_prepare_start_succeeds_and_returns_running(
    client_with_offers, monkeypatch
) -> None:
    import app as dashboard_app
    import user_data

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db, description=_PREPARE_LONG_DESCRIPTION)
    monkeypatch.setattr(user_data, "get_hf_token", lambda conn, uid: "test-hf-token")
    monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close())

    response = client_with_offers.post(f"/api/offers/{offer_id}/prepare")

    assert response.status_code == 200
    assert response.json() == {"status": "running"}


def test_prepare_status_defaults_to_idle(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.get(f"/api/offers/{row['id']}/prepare/status")
    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_prepare_status_returns_404_for_missing(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers/999/prepare/status")
    assert response.status_code == 404


def test_prepare_requires_auth(client) -> None:
    response = client.post("/api/offers/1/prepare")
    assert response.status_code == 401
    response = client.get("/api/offers/1/prepare/status")
    assert response.status_code == 401


def test_prepare_state_isolated_per_offer_via_route(
    client_with_offers, monkeypatch
) -> None:
    import app as dashboard_app
    import user_data

    db = dashboard_app.app.state.db
    offer_a = _insert_row(db, description=_PREPARE_LONG_DESCRIPTION)
    offer_b = _insert_row(db, description=_PREPARE_LONG_DESCRIPTION)
    monkeypatch.setattr(user_data, "get_hf_token", lambda conn, uid: "test-hf-token")
    monkeypatch.setattr("asyncio.create_task", lambda coro: coro.close())

    client_with_offers.post(f"/api/offers/{offer_a}/prepare")

    r_a = client_with_offers.get(f"/api/offers/{offer_a}/prepare/status")
    r_b = client_with_offers.get(f"/api/offers/{offer_b}/prepare/status")
    assert r_a.json()["status"] == "running"
    assert r_b.json()["status"] == "idle"


def test_download_cv_returns_404_when_not_generated(client_with_offers) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    row = db.get_all({}, user_id=MOCK_USER["sub"])[0]
    response = client_with_offers.get(f"/api/offers/{row['id']}/cv")
    assert response.status_code == 404


def test_download_cv_returns_404_for_missing_offer(client_with_offers) -> None:
    response = client_with_offers.get("/api/offers/999/cv")
    assert response.status_code == 404


def test_download_cv_serves_file_when_present(client_with_offers, tmp_path) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db)
    pdf_path = tmp_path / "cv-acme-2026-07-09.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake cv content")
    db.update(offer_id, {"cv_path": str(pdf_path)}, user_id=MOCK_USER["sub"])

    response = client_with_offers.get(f"/api/offers/{offer_id}/cv")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake cv content"
    assert "attachment" in response.headers["content-disposition"]
    assert "cv-acme-2026-07-09.pdf" in response.headers["content-disposition"]


def test_download_cover_letter_serves_file_when_present(
    client_with_offers, tmp_path
) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db)
    pdf_path = tmp_path / "cl-acme-2026-07-09.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake cl content")
    db.update(offer_id, {"cover_letter_path": str(pdf_path)}, user_id=MOCK_USER["sub"])

    response = client_with_offers.get(f"/api/offers/{offer_id}/cover-letter")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake cl content"


def test_download_prep_sheet_serves_file_when_present(
    client_with_offers, tmp_path
) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db)
    pdf_path = tmp_path / "prep-acme-2026-07-09.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake prep content")
    db.update(offer_id, {"prep_sheet_path": str(pdf_path)}, user_id=MOCK_USER["sub"])

    response = client_with_offers.get(f"/api/offers/{offer_id}/prep-sheet")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake prep content"


def test_download_cv_returns_404_when_file_deleted_from_disk(
    client_with_offers, tmp_path
) -> None:
    import app as dashboard_app

    db = dashboard_app.app.state.db
    offer_id = _insert_row(db)
    pdf_path = tmp_path / "gone.pdf"
    db.update(offer_id, {"cv_path": str(pdf_path)}, user_id=MOCK_USER["sub"])

    response = client_with_offers.get(f"/api/offers/{offer_id}/cv")

    assert response.status_code == 404


def test_download_requires_auth(client) -> None:
    response = client.get("/api/offers/1/cv")
    assert response.status_code == 401


def test_get_stats_returns_200_with_computed_data(client_with_offers) -> None:
    response = client_with_offers.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["total"] == 2
    assert body["stats"]["by_status"]["À envoyer"] == 1
    assert body["stats"]["by_status"]["Envoyée"] == 1
    assert len(body["funnel"]) == 7
    assert len(body["exits"]) == 2
    assert body["max_count"] >= 1


def test_get_stats_requires_auth(client) -> None:
    response = client.get("/api/stats")
    assert response.status_code == 401


def test_get_stats_report_fields_null_when_no_reports(
    client_with_offers, tmp_path, monkeypatch
) -> None:
    import api as api_module

    monkeypatch.setattr(api_module, "REPORTS_DIR", tmp_path)
    response = client_with_offers.get("/api/stats")
    body = response.json()
    assert body["latest_report_html"] is None
    assert body["latest_report_date"] is None


def test_get_stats_report_fields_populated_from_latest_file(
    client_with_offers, tmp_path, monkeypatch
) -> None:
    import api as api_module

    (tmp_path / "daily-2026-07-01.md").write_text("Old report", encoding="utf-8")
    (tmp_path / "daily-2026-07-03.md").write_text(
        "# New report\n\n**Total:** 2", encoding="utf-8"
    )
    monkeypatch.setattr(api_module, "REPORTS_DIR", tmp_path)
    response = client_with_offers.get("/api/stats")
    body = response.json()
    assert body["latest_report_date"] == "2026-07-03"
    assert "New report" in body["latest_report_html"]
    assert "Old report" not in body["latest_report_html"]


def test_get_profile_returns_200_with_data(client_with_profile) -> None:
    response = client_with_profile.get("/api/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["contact"]["name"] == "Test User"
    assert body["profile"]["profile_md"] == "An experienced engineer."
    assert body["cv"] == FAKE_CV
    assert body["cv_en"] == FAKE_CV
    assert body["onboarding"] == FAKE_ONBOARDING


def test_get_profile_strips_dead_compat_keys(client_with_profile) -> None:
    response = client_with_profile.get("/api/profile")
    body = response.json()
    assert set(body["profile"].keys()) == {"contact", "profile_md"}


def test_get_profile_requires_auth(client) -> None:
    response = client.get("/api/profile")
    assert response.status_code == 401


def test_get_profile_succeeds_without_completed_onboarding(
    client_with_profile, monkeypatch
) -> None:
    import user_data

    monkeypatch.setattr(
        user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": False,
            "profile_complete": False,
            "search_complete": False,
            "hf_token_complete": False,
        },
    )
    response = client_with_profile.get("/api/profile")
    assert response.status_code == 200
    assert response.json()["onboarding"]["is_complete"] is False


def test_patch_profile_contact_saves_and_returns_ok(client_with_profile_mutations) -> None:
    client, mocks = client_with_profile_mutations
    response = client.patch(
        "/api/profile/contact",
        json={
            "name": "New Name",
            "title": "ML Eng",
            "email": "new@test.com",
            "phone": "",
            "location": "Lyon",
            "linkedin": "",
            "github": "",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mocks["load_profile"].assert_called_once()
    saved_data = mocks["save_profile"].call_args[0][2]
    assert saved_data["contact"]["name"] == "New Name"
    assert saved_data["contact"]["location"] == "Lyon"


def test_patch_profile_contact_requires_auth(client) -> None:
    response = client.patch("/api/profile/contact", json={})
    assert response.status_code == 401


def test_patch_profile_text_saves_profile_md(client_with_profile_mutations) -> None:
    client, mocks = client_with_profile_mutations
    response = client.patch(
        "/api/profile/text", json={"profile_md": "Updated résumé text."}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    saved_data = mocks["save_profile"].call_args[0][2]
    assert saved_data["profile_md"] == "Updated résumé text."


def test_patch_profile_text_requires_auth(client) -> None:
    response = client.patch("/api/profile/text", json={"profile_md": "x"})
    assert response.status_code == 401


def test_put_profile_cv_meta_saves_summary(client_with_profile_mutations) -> None:
    client, mocks = client_with_profile_mutations
    response = client.put(
        "/api/profile/cv/meta?lang=en", json={"summary": "New summary."}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    call_args = mocks["save_cv_meta"].call_args[0]
    assert call_args[2] == "en"
    assert call_args[3] == "New summary."


def test_put_profile_cv_meta_invalid_lang_falls_back_to_fr(
    client_with_profile_mutations,
) -> None:
    client, mocks = client_with_profile_mutations
    response = client.put("/api/profile/cv/meta?lang=de", json={"summary": "x"})
    assert response.status_code == 200
    call_args = mocks["save_cv_meta"].call_args[0]
    assert call_args[2] == "fr"


def test_put_profile_cv_meta_requires_auth(client) -> None:
    response = client.put("/api/profile/cv/meta", json={"summary": "x"})
    assert response.status_code == 401
