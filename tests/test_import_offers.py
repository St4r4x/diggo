"""Tests for import_offers: score_to_grade, existing_urls, insert_offer, import_offers."""

from __future__ import annotations

import sqlite3
from datetime import date


from scripts.import_offers import (
    existing_urls,
    import_offers,
    insert_offer,
    score_to_grade,
)
from scripts.models import RawOffer

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company            TEXT    NOT NULL,
    role               TEXT    NOT NULL,
    offer_url          TEXT    NOT NULL DEFAULT '',
    detection_date     TEXT    NOT NULL,
    score_grade        TEXT    NOT NULL DEFAULT '',
    score_value        REAL    NOT NULL DEFAULT 0.0,
    status             TEXT    NOT NULL DEFAULT 'À envoyer',
    send_date          TEXT,
    contacts           TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT '',
    cv_path            TEXT    NOT NULL DEFAULT '',
    cover_letter_path  TEXT    NOT NULL DEFAULT '',
    follow_up_date     TEXT,
    description        TEXT    NOT NULL DEFAULT ''
)
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(_CREATE_TABLE_SQL)
    return conn


class TestScoreToGrade:
    def test_a_at_4_0(self) -> None:
        assert score_to_grade(4.0) == "A"

    def test_a_at_5_0(self) -> None:
        assert score_to_grade(5.0) == "A"

    def test_b_at_3_0(self) -> None:
        assert score_to_grade(3.0) == "B"

    def test_b_at_3_9(self) -> None:
        assert score_to_grade(3.9) == "B"

    def test_c_at_2_0(self) -> None:
        assert score_to_grade(2.0) == "C"

    def test_d_at_1_0(self) -> None:
        assert score_to_grade(1.0) == "D"

    def test_f_below_1_0(self) -> None:
        assert score_to_grade(0.9) == "F"

    def test_f_at_zero(self) -> None:
        assert score_to_grade(0.0) == "F"


class TestExistingUrls:
    def test_empty_db_returns_empty_set(self) -> None:
        conn = _make_conn()
        assert existing_urls(conn) == set()

    def test_returns_url_from_row(self) -> None:
        conn = _make_conn()
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, detection_date) VALUES (?, ?, ?, ?)",
            ("Acme", "Dev", "https://example.com/1", "2026-05-25"),
        )
        assert "https://example.com/1" in existing_urls(conn)

    def test_ignores_empty_url_rows(self) -> None:
        conn = _make_conn()
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, detection_date) VALUES (?, ?, ?, ?)",
            ("Acme", "Dev", "", "2026-05-25"),
        )
        assert existing_urls(conn) == set()


class TestInsertOffer:
    def test_inserts_correct_fields(self) -> None:
        conn = _make_conn()
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/123",
            portal="wtfj",
            location="Paris",
            date_posted=date(2026, 5, 20),
            score=4.2,
        )
        insert_offer(conn, offer)
        row = conn.execute(
            "SELECT company, role, offer_url, detection_date, score_grade, score_value, status FROM applications"
        ).fetchone()
        assert row[0] == "Mistral AI"
        assert row[1] == "AI Engineer"
        assert row[2] == "https://wttj.co/jobs/123"
        assert row[3] == "2026-05-20"
        assert row[4] == "A"
        assert abs(row[5] - 4.2) < 0.001
        assert row[6] == "À envoyer"

    def test_uses_today_when_date_posted_is_none(self) -> None:
        conn = _make_conn()
        offer = RawOffer(title="Dev", company="Co", url="https://x.com/1", portal="p")
        insert_offer(conn, offer)
        row = conn.execute("SELECT detection_date FROM applications").fetchone()
        assert row[0] == date.today().isoformat()

    def test_inserts_description(self) -> None:
        conn = _make_conn()
        offer = RawOffer(
            title="AI Engineer",
            company="Acme",
            url="https://x.com/1",
            portal="p",
            description="We are looking for an AI Engineer with 3+ years experience.",
        )
        insert_offer(conn, offer)
        row = conn.execute("SELECT description FROM applications").fetchone()
        assert row[0] == "We are looking for an AI Engineer with 3+ years experience."

    def test_inserts_empty_description_by_default(self) -> None:
        conn = _make_conn()
        offer = RawOffer(title="Dev", company="Co", url="https://x.com/1", portal="p")
        insert_offer(conn, offer)
        row = conn.execute("SELECT description FROM applications").fetchone()
        assert row[0] == ""


class TestImportOffers:
    def test_inserts_new_offers(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offers = [
            RawOffer(
                title="AI Engineer",
                company="Acme",
                url="https://x.com/1",
                portal="p",
                score=4.0,
            ),
            RawOffer(
                title="ML Engineer",
                company="Beta",
                url="https://x.com/2",
                portal="p",
                score=3.5,
            ),
        ]
        inserted, skipped = import_offers(offers, db_path)
        assert inserted == 2
        assert skipped == 0

    def test_skips_duplicate_url_on_second_run(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offer = RawOffer(
            title="AI Engineer",
            company="Acme",
            url="https://x.com/1",
            portal="p",
            score=4.0,
        )
        import_offers([offer], db_path)
        inserted, skipped = import_offers([offer], db_path)
        assert inserted == 0
        assert skipped == 1

    def test_empty_url_offers_always_inserted(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offer = RawOffer(
            title="AI Engineer", company="Acme", url="", portal="p", score=4.0
        )
        import_offers([offer], db_path)
        inserted, skipped = import_offers([offer], db_path)
        assert inserted == 1
        assert skipped == 0

    def test_creates_db_file_if_missing(self, tmp_path) -> None:
        db_path = tmp_path / "subdir" / "new.db"
        assert not db_path.exists()
        import_offers([], db_path)
        assert db_path.exists()
