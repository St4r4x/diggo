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
