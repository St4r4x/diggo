import os
from datetime import date, timedelta
from pathlib import Path
import sys

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
from db import DB, VALID_STATUSES

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
TEST_USER = "test-user"
OTHER_USER = "other-user"

_CREATE_TEMP = """
CREATE TEMP TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL DEFAULT 'test-user',
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


@pytest.fixture
def db() -> DB:
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_TEMP)
    conn.commit()
    yield DB(conn)
    conn.close()


def _insert(
    db: DB,
    company: str = "Acme",
    role: str = "AI Engineer",
    status: str = "À envoyer",
    score_grade: str = "B",
    score_value: float = 4.0,
    offer_url: str = "https://x.com/1",
    detection_date: str = "2026-05-25",
    send_date: str | None = None,
    user_id: str = TEST_USER,
) -> int:
    with db.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applications (user_id, company, role, offer_url, detection_date,"
            " score_grade, score_value, status, send_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " RETURNING id",
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
            ),
        )
        row_id = cur.fetchone()[0]
    db.conn.commit()
    return row_id


class TestGetAll:
    def test_returns_empty_list_when_no_rows(self, db: DB) -> None:
        assert db.get_all({}, user_id=TEST_USER) == []

    def test_returns_all_rows(self, db: DB) -> None:
        _insert(db, company="Acme")
        _insert(db, company="Beta")
        rows = db.get_all({}, user_id=TEST_USER)
        assert len(rows) == 2

    def test_filters_by_status(self, db: DB) -> None:
        _insert(db, company="Acme", status="À envoyer")
        _insert(db, company="Beta", status="Envoyée")
        rows = db.get_all({"status": "Envoyée"}, user_id=TEST_USER)
        assert len(rows) == 1
        assert rows[0]["company"] == "Beta"

    def test_filters_by_grade(self, db: DB) -> None:
        _insert(db, company="Acme", score_grade="A")
        _insert(db, company="Beta", score_grade="F")
        rows = db.get_all({"grade": "A"}, user_id=TEST_USER)
        assert len(rows) == 1
        assert rows[0]["company"] == "Acme"

    def test_filters_by_search_company(self, db: DB) -> None:
        _insert(db, company="Mistral AI")
        _insert(db, company="Doctrine")
        rows = db.get_all({"q": "mistral"}, user_id=TEST_USER)
        assert len(rows) == 1
        assert rows[0]["company"] == "Mistral AI"

    def test_filters_by_search_role(self, db: DB) -> None:
        _insert(db, company="Acme", role="ML Engineer")
        _insert(db, company="Beta", role="Data Scientist")
        rows = db.get_all({"q": "data"}, user_id=TEST_USER)
        assert len(rows) == 1
        assert rows[0]["role"] == "Data Scientist"

    def test_ordered_by_detection_date_desc(self, db: DB) -> None:
        _insert(db, company="Old", detection_date="2026-05-01")
        _insert(db, company="New", detection_date="2026-05-25")
        rows = db.get_all({}, user_id=TEST_USER)
        assert rows[0]["company"] == "New"

    def test_scoped_to_user(self, db: DB) -> None:
        _insert(db, company="Mine", user_id=TEST_USER)
        _insert(db, company="Theirs", user_id=OTHER_USER)
        rows = db.get_all({}, user_id=TEST_USER)
        assert len(rows) == 1
        assert rows[0]["company"] == "Mine"


class TestGetById:
    def test_returns_row(self, db: DB) -> None:
        rid = _insert(db, company="Acme")
        row = db.get_by_id(rid, user_id=TEST_USER)
        assert row is not None
        assert row["company"] == "Acme"

    def test_returns_none_for_missing_id(self, db: DB) -> None:
        assert db.get_by_id(999, user_id=TEST_USER) is None

    def test_returns_none_wrong_user(self, db: DB) -> None:
        rid = _insert(db, user_id=TEST_USER)
        assert db.get_by_id(rid, user_id=OTHER_USER) is None


class TestUpdate:
    def test_updates_fields(self, db: DB) -> None:
        rid = _insert(db, company="Acme", role="AI Engineer")
        db.update(
            rid, {"notes": "Great company", "status": "Envoyée"}, user_id=TEST_USER
        )
        row = db.get_by_id(rid, user_id=TEST_USER)
        assert row["notes"] == "Great company"
        assert row["status"] == "Envoyée"

    def test_returns_updated_row(self, db: DB) -> None:
        rid = _insert(db, company="Acme")
        result = db.update(rid, {"notes": "Updated"}, user_id=TEST_USER)
        assert result["notes"] == "Updated"

    def test_update_description(self, db: DB) -> None:
        rid = _insert(db)
        updated = db.update(
            rid, {"description": "Job description text here."}, user_id=TEST_USER
        )
        assert updated["description"] == "Job description text here."


class TestDelete:
    def test_removes_row(self, db: DB) -> None:
        rid = _insert(db)
        db.delete(rid, user_id=TEST_USER)
        assert db.get_by_id(rid, user_id=TEST_USER) is None

    def test_no_error_on_missing_id(self, db: DB) -> None:
        db.delete(999, user_id=TEST_USER)  # should not raise

    def test_delete_only_own_rows(self, db: DB) -> None:
        rid = _insert(db, user_id=TEST_USER)
        db.delete(rid, user_id=OTHER_USER)  # no-op
        assert db.get_by_id(rid, user_id=TEST_USER) is not None


class TestUpdateStatus:
    def test_sets_status(self, db: DB) -> None:
        rid = _insert(db, status="À envoyer")
        result = db.update_status(rid, "Envoyée", user_id=TEST_USER)
        assert result["status"] == "Envoyée"


class TestGetStats:
    def test_total_count(self, db: DB) -> None:
        _insert(db)
        _insert(db)
        stats = db.get_stats(user_id=TEST_USER)
        assert stats["total"] == 2

    def test_stale_count(self, db: DB) -> None:
        old_date = (date.today() - timedelta(days=8)).isoformat()
        _insert(db, status="Envoyée", send_date=old_date)
        _insert(db, status="Envoyée", send_date=date.today().isoformat())
        stats = db.get_stats(user_id=TEST_USER)
        assert stats["stale_count"] == 1

    def test_by_status_counts(self, db: DB) -> None:
        _insert(db, status="À envoyer")
        _insert(db, status="Envoyée")
        stats = db.get_stats(user_id=TEST_USER)
        assert stats["by_status"]["À envoyer"] == 1
        assert stats["by_status"]["Envoyée"] == 1

    def test_response_rate(self, db: DB) -> None:
        _insert(db, status="Envoyée")
        _insert(db, status="Entretien RH")
        stats = db.get_stats(user_id=TEST_USER)
        assert "response_rate" in stats
        assert stats["response_rate"] == 50.0

    def test_interview_count(self, db: DB) -> None:
        _insert(db, status="À envoyer")
        _insert(db, status="Entretien tech")
        stats = db.get_stats(user_id=TEST_USER)
        assert stats["interview_count"] == 1

    def test_scoped_to_user(self, db: DB) -> None:
        _insert(db, user_id=TEST_USER, status="Envoyée")
        _insert(db, user_id=OTHER_USER, status="Envoyée")
        stats = db.get_stats(user_id=TEST_USER)
        assert stats["total"] == 1


class TestBuildFunnel:
    def test_computes_conversion_rate(self) -> None:
        from db import build_funnel

        by_status = {
            "À envoyer": 10,
            "Envoyée": 5,
            "Relance": 0,
            "Entretien RH": 2,
            "Entretien tech": 1,
            "Offre": 0,
            "Acceptée": 0,
            "Refusée": 1,
            "Abandonnée": 2,
        }
        funnel, exits, max_count = build_funnel(by_status)
        envoyee_step = next(s for s in funnel if s["status"] == "Envoyée")
        assert envoyee_step["rate"] == 50.0
        entretien_step = next(s for s in funnel if s["status"] == "Entretien RH")
        assert entretien_step["rate"] is None
        assert len(funnel) == 7
        assert len(exits) == 2
        assert exits[0]["status"] == "Refusée"
        assert max_count == 10

    def test_defaults_missing_statuses_to_zero(self) -> None:
        from db import build_funnel

        funnel, exits, max_count = build_funnel({})
        assert all(s["count"] == 0 for s in funnel)
        assert all(s["count"] == 0 for s in exits)
        assert max_count == 1


class TestValidStatuses:
    def test_is_list_with_correct_values(self) -> None:
        assert isinstance(VALID_STATUSES, list)
        assert "À envoyer" in VALID_STATUSES
        assert "Acceptée" in VALID_STATUSES
        assert len(VALID_STATUSES) == 9
