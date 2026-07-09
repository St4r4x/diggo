import os
from datetime import date, timedelta
from pathlib import Path
import sys

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
TEST_USER_ID = "test-user-uuid-fixture"
MOCK_USER = {"sub": TEST_USER_ID, "email": "test@example.com"}

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
    user_id: str = TEST_USER_ID,
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
    from auth import get_current_user, require_onboarding_complete

    test_db = _make_pg_db()
    dashboard_app.app.state.db = test_db
    dashboard_app.app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    dashboard_app.app.dependency_overrides[require_onboarding_complete] = lambda: (
        MOCK_USER
    )
    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.clear()
    test_db.close()


@pytest.fixture
def client_with_data(client):
    import app as dashboard_app

    db = dashboard_app.app.state.db
    _insert_row(
        db,
        company="Mistral AI",
        offer_url="https://jobs.lever.co/mistral/1",
        score_grade="B",
        score_value=4.0,
        status="À envoyer",
    )
    _insert_row(
        db,
        company="Doctrine",
        offer_url="https://jobs.lever.co/doctrine/1",
        detection_date="2026-05-24",
        score_grade="A",
        score_value=4.5,
        status="Envoyée",
    )
    return client


@pytest.fixture
def client_with_interview_offer(client):
    import app as dashboard_app

    db = dashboard_app.app.state.db
    _insert_row(
        db,
        company="Hugging Face",
        offer_url="https://apply.workable.com/huggingface/1",
        detection_date="2026-06-01",
        score_grade="A",
        score_value=4.8,
        status="Entretien RH",
    )
    return client


class TestOnboardingGateOnSettingsAndProfileNeverBlocks:
    def test_settings_page_never_redirected_when_onboarding_incomplete(
        self, monkeypatch, client: TestClient
    ) -> None:
        import app as dashboard_app

        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_onboarding_state",
            lambda conn, user_id: {
                "is_complete": False,
                "profile_complete": False,
                "search_complete": False,
                "hf_token_complete": False,
            },
        )
        r = client.get("/settings")
        assert r.status_code == 200


class TestGetFollowups:
    def test_returns_overdue_envoyee(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        _insert_row(
            db,
            company="Braze",
            offer_url="https://example.com/1",
            detection_date="2026-06-01",
            score_grade="B",
            score_value=3.5,
            status="Envoyée",
            send_date="2026-06-01",
        )
        result = db.get_followups(user_id=TEST_USER_ID)
        assert any(r["company"] == "Braze" for r in result)

    def test_excludes_recent_envoyee(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        recent = (date.today() - timedelta(days=2)).isoformat()
        _insert_row(
            db,
            company="Recent Co",
            offer_url="https://example.com/2",
            detection_date="2026-06-01",
            score_grade="B",
            score_value=3.5,
            status="Envoyée",
            send_date=recent,
        )
        result = db.get_followups(user_id=TEST_USER_ID)
        assert not any(r["company"] == "Recent Co" for r in result)

    def test_returns_overdue_entretien_rh(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        _insert_row(
            db,
            company="Hugging Face",
            offer_url="https://example.com/3",
            detection_date="2026-06-01",
            score_grade="A",
            score_value=4.5,
            status="Entretien RH",
            send_date="2026-06-01",
        )
        result = db.get_followups(user_id=TEST_USER_ID)
        assert any(r["company"] == "Hugging Face" for r in result)

    def test_excludes_null_send_date(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        _insert_row(
            db,
            company="No Date Co",
            offer_url="https://example.com/4",
            detection_date="2026-06-01",
            score_grade="B",
            score_value=3.0,
            status="Envoyée",
        )
        result = db.get_followups(user_id=TEST_USER_ID)
        assert not any(r["company"] == "No Date Co" for r in result)


class TestSettingsHfTokenValidation:
    def test_save_valid_token_succeeds(self, client: TestClient, monkeypatch) -> None:
        import app as dashboard_app

        monkeypatch.setattr(dashboard_app.llm, "validate_hf_token", lambda token: None)
        r = client.post("/settings/hf-token", data={"hf_token": "hf_valid_token_123"})
        assert r.status_code == 200
        assert "Configuré" in r.text

    def test_save_invalid_token_shows_error_and_does_not_save(
        self, client: TestClient, monkeypatch
    ) -> None:
        import app as dashboard_app

        conn = dashboard_app.app.state.db.conn
        dashboard_app.user_data.delete_hf_token(conn, MOCK_USER["sub"])
        conn.commit()

        def _fail(token):
            raise dashboard_app.llm.LLMError(
                "Token invalide — vérifie que le copier-coller est complet."
            )

        monkeypatch.setattr(dashboard_app.llm, "validate_hf_token", _fail)
        r = client.post("/settings/hf-token", data={"hf_token": "hf_bad_token"})
        assert r.status_code == 200
        assert "Token invalide" in r.text

        conn = dashboard_app.app.state.db.conn
        assert dashboard_app.user_data.get_hf_token(conn, MOCK_USER["sub"]) is None


_DEFAULT_SETTINGS = {
    "keywords": [],
    "portal_queries": [],
    "location": "Paris",
    "contract": "CDI",
    "experience_max_years": 3,
    "salary_min": 0,
    "salary_max": 0,
    "target_companies": [],
    "follow_up_days": 7,
}

_ATS_STORE: list[dict] = []
_HF_TOKEN_STORE: dict[str, str] = {}


@pytest.fixture
def authed_client(client: TestClient, monkeypatch) -> TestClient:
    import llm
    import user_data

    monkeypatch.setattr(llm, "validate_hf_token", lambda token: None)
    monkeypatch.setattr(
        user_data, "get_settings", lambda conn, uid: dict(_DEFAULT_SETTINGS)
    )
    monkeypatch.setattr(user_data, "save_settings", lambda conn, uid, data: None)

    def _get_ats(conn, uid):
        return list(_ATS_STORE)

    def _add_ats(conn, uid, name, careers_url):
        new_id = len(_ATS_STORE) + 1
        _ATS_STORE.append({"id": new_id, "name": name, "careers_url": careers_url})
        return new_id

    def _del_ats(conn, uid, target_id):
        _ATS_STORE[:] = [t for t in _ATS_STORE if t["id"] != target_id]

    monkeypatch.setattr(user_data, "get_ats_targets", _get_ats)
    monkeypatch.setattr(user_data, "add_ats_target", _add_ats)
    monkeypatch.setattr(user_data, "delete_ats_target", _del_ats)
    _ATS_STORE.clear()

    def _get_hf_token(conn, uid):
        return _HF_TOKEN_STORE.get(uid)

    def _save_hf_token(conn, uid, token):
        _HF_TOKEN_STORE[uid] = token

    def _delete_hf_token(conn, uid):
        _HF_TOKEN_STORE.pop(uid, None)

    monkeypatch.setattr(user_data, "get_hf_token", _get_hf_token)
    monkeypatch.setattr(user_data, "save_hf_token", _save_hf_token)
    monkeypatch.setattr(user_data, "delete_hf_token", _delete_hf_token)
    _HF_TOKEN_STORE.clear()
    return client


class TestSettings:
    def test_settings_page_requires_auth(self) -> None:
        import app as dashboard_app
        from auth import get_current_user

        dashboard_app.app.dependency_overrides.pop(get_current_user, None)
        c = TestClient(
            dashboard_app.app, raise_server_exceptions=False, follow_redirects=False
        )
        r = c.get("/settings")
        assert r.status_code == 302

    def test_settings_page_ok(self, authed_client: TestClient) -> None:
        r = authed_client.get("/settings")
        assert r.status_code == 200
        assert "Recherche" in r.text

    def test_settings_search_post(self, authed_client: TestClient) -> None:
        r = authed_client.post(
            "/settings/search",
            data={
                "keywords": "AI Engineer\nML Engineer",
                "portal_queries": "AI Engineer",
                "location": "Paris",
                "contract": "CDI",
                "experience_max_years": "3",
                "salary_min": "40000",
                "salary_max": "60000",
                "target_companies": "Mistral AI\nHugging Face",
                "follow_up_days": "7",
            },
        )
        assert r.status_code == 200

    def test_settings_ats_add(self, authed_client: TestClient) -> None:
        r = authed_client.post(
            "/settings/ats",
            data={
                "name": "Mistral AI",
                "careers_url": "https://jobs.lever.co/mistral",
            },
        )
        assert r.status_code == 200
        assert "Mistral AI" in r.text

    def test_settings_ats_delete(self, authed_client: TestClient) -> None:
        import re

        add_resp = authed_client.post(
            "/settings/ats",
            data={
                "name": "Mistral AI",
                "careers_url": "https://jobs.lever.co/mistral",
            },
        )
        assert add_resp.status_code == 200
        m = re.search(r"/settings/ats/(\d+)", add_resp.text)
        assert m, "No ATS target id found in response"
        target_id = m.group(1)
        del_resp = authed_client.delete(f"/settings/ats/{target_id}")
        assert del_resp.status_code == 200
        assert "Mistral AI" not in del_resp.text

    def test_settings_hf_token_save(self, authed_client: TestClient) -> None:
        r = authed_client.post("/settings/hf-token", data={"hf_token": "hf_secret123"})
        assert r.status_code == 200
        assert "Configuré" in r.text

    def test_settings_hf_token_empty_value_clears_it(
        self, authed_client: TestClient
    ) -> None:
        authed_client.post("/settings/hf-token", data={"hf_token": "hf_secret123"})
        r = authed_client.post("/settings/hf-token", data={"hf_token": ""})
        assert r.status_code == 200
        assert "Non configuré" in r.text

    def test_settings_hf_token_delete(self, authed_client: TestClient) -> None:
        authed_client.post("/settings/hf-token", data={"hf_token": "hf_secret123"})
        r = authed_client.delete("/settings/hf-token")
        assert r.status_code == 200
        assert "Non configuré" in r.text
