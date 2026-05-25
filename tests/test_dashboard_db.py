import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
from db import DB, VALID_STATUSES

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL, role TEXT NOT NULL,
    offer_url TEXT NOT NULL DEFAULT '',
    detection_date TEXT NOT NULL,
    score_grade TEXT NOT NULL DEFAULT '',
    score_value REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'À envoyer',
    send_date TEXT, contacts TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '', cv_path TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '', follow_up_date TEXT,
    description TEXT NOT NULL DEFAULT ''
)"""


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute(CREATE_SQL)
    conn.commit()
    return DB(conn)


def _insert(
    db,
    company="Acme",
    role="AI Engineer",
    status="À envoyer",
    score_grade="B",
    score_value=4.0,
    offer_url="https://x.com/1",
    detection_date="2026-05-25",
    send_date=None,
):
    db.conn.execute(
        "INSERT INTO applications (company, role, offer_url, detection_date, "
        "score_grade, score_value, status, send_date) VALUES (?,?,?,?,?,?,?,?)",
        (
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
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetAll:
    def test_returns_empty_list_when_no_rows(self, db):
        assert db.get_all({}) == []

    def test_returns_all_rows(self, db):
        _insert(db, company="Acme")
        _insert(db, company="Beta")
        rows = db.get_all({})
        assert len(rows) == 2

    def test_filters_by_status(self, db):
        _insert(db, company="Acme", status="À envoyer")
        _insert(db, company="Beta", status="Envoyée")
        rows = db.get_all({"status": "Envoyée"})
        assert len(rows) == 1
        assert rows[0]["company"] == "Beta"

    def test_filters_by_grade(self, db):
        _insert(db, company="Acme", score_grade="A")
        _insert(db, company="Beta", score_grade="F")
        rows = db.get_all({"grade": "A"})
        assert len(rows) == 1
        assert rows[0]["company"] == "Acme"

    def test_filters_by_search_company(self, db):
        _insert(db, company="Mistral AI")
        _insert(db, company="Doctrine")
        rows = db.get_all({"q": "mistral"})
        assert len(rows) == 1
        assert rows[0]["company"] == "Mistral AI"

    def test_filters_by_search_role(self, db):
        _insert(db, company="Acme", role="ML Engineer")
        _insert(db, company="Beta", role="Data Scientist")
        rows = db.get_all({"q": "data"})
        assert len(rows) == 1
        assert rows[0]["role"] == "Data Scientist"

    def test_ordered_by_detection_date_desc(self, db):
        _insert(db, company="Old", detection_date="2026-05-01")
        _insert(db, company="New", detection_date="2026-05-25")
        rows = db.get_all({})
        assert rows[0]["company"] == "New"


class TestGetById:
    def test_returns_row(self, db):
        rid = _insert(db, company="Acme")
        row = db.get_by_id(rid)
        assert row is not None
        assert row["company"] == "Acme"

    def test_returns_none_for_missing_id(self, db):
        assert db.get_by_id(999) is None


class TestUpdate:
    def test_updates_fields(self, db):
        rid = _insert(db, company="Acme", role="AI Engineer")
        db.update(rid, {"notes": "Great company", "status": "Envoyée"})
        row = db.get_by_id(rid)
        assert row["notes"] == "Great company"
        assert row["status"] == "Envoyée"

    def test_returns_updated_row(self, db):
        rid = _insert(db, company="Acme")
        result = db.update(rid, {"notes": "Updated"})
        assert result["notes"] == "Updated"

    def test_update_description(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute(CREATE_SQL)
        conn.commit()
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, detection_date) VALUES (?,?,?,?)",
            ("Acme", "Dev", "https://x.com/1", "2026-05-25"),
        )
        conn.commit()
        db = DB(conn)
        row = db.get_all({})[0]
        updated = db.update(row["id"], {"description": "Job description text here."})
        assert updated["description"] == "Job description text here."


class TestDelete:
    def test_removes_row(self, db):
        rid = _insert(db)
        db.delete(rid)
        assert db.get_by_id(rid) is None

    def test_no_error_on_missing_id(self, db):
        db.delete(999)  # should not raise


class TestUpdateStatus:
    def test_sets_status(self, db):
        rid = _insert(db, status="À envoyer")
        result = db.update_status(rid, "Envoyée")
        assert result["status"] == "Envoyée"


class TestGetStats:
    def test_total_count(self, db):
        _insert(db)
        _insert(db)
        stats = db.get_stats()
        assert stats["total"] == 2

    def test_stale_count(self, db):
        from datetime import date, timedelta

        old_date = (date.today() - timedelta(days=8)).isoformat()
        _insert(db, status="Envoyée", send_date=old_date)
        _insert(db, status="Envoyée", send_date=date.today().isoformat())
        stats = db.get_stats()
        assert stats["stale_count"] == 1

    def test_by_status_counts(self, db):
        _insert(db, status="À envoyer")
        _insert(db, status="Envoyée")
        stats = db.get_stats()
        assert stats["by_status"]["À envoyer"] == 1
        assert stats["by_status"]["Envoyée"] == 1

    def test_response_rate(self, db):
        _insert(db, status="Envoyée")  # sent, no response
        _insert(db, status="Entretien RH")  # sent + response
        stats = db.get_stats()
        assert "response_rate" in stats
        assert stats["response_rate"] == 50.0  # 1 response / 2 sent * 100

    def test_interview_count(self, db):
        _insert(db, status="À envoyer")
        _insert(db, status="Entretien tech")
        stats = db.get_stats()
        assert stats["interview_count"] == 1


class TestValidStatuses:
    def test_is_list_with_correct_values(self):
        assert isinstance(VALID_STATUSES, list)
        assert "À envoyer" in VALID_STATUSES
        assert "Acceptée" in VALID_STATUSES
        assert len(VALID_STATUSES) == 9
