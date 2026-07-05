"""Tests for import_offers: score_to_grade, existing_urls, insert_offer, import_offers."""

from __future__ import annotations

import json
import os
from datetime import date

import psycopg2
import pytest

from scripts.import_offers import (
    existing_urls,
    import_offers,
    insert_offer,
    score_to_grade,
)
from scripts.models import RawOffer

PG_URL = os.getenv("DATABASE_URL", "postgresql://career:career@localhost:5432/career")
TEST_USER = "test-import-user"

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
    follow_up_date TEXT,
    description TEXT NOT NULL DEFAULT '',
    portal TEXT NOT NULL DEFAULT ''
)
"""


@pytest.fixture
def pg_conn():
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_TEMP)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_pg_connect(pg_conn, monkeypatch):
    """Redirect psycopg2.connect in import_offers to return our temp-table connection."""

    class _NoClose:
        def __init__(self) -> None:
            self._c = pg_conn

        def cursor(self):
            return self._c.cursor()

        def commit(self) -> None:
            self._c.commit()

        def close(self) -> None:
            pass  # keep the fixture connection alive

        @property
        def autocommit(self) -> bool:
            return self._c.autocommit

        @autocommit.setter
        def autocommit(self, val: bool) -> None:
            self._c.autocommit = val

    monkeypatch.setattr(
        "scripts.import_offers.psycopg2.connect", lambda _url: _NoClose()
    )
    return pg_conn


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
    def test_empty_db_returns_empty_set(self, pg_conn) -> None:
        assert existing_urls(pg_conn, TEST_USER) == set()

    def test_returns_url_from_row(self, pg_conn) -> None:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO applications (user_id, company, role, offer_url, detection_date)"
                " VALUES (%s, %s, %s, %s, %s)",
                (TEST_USER, "Acme", "Dev", "https://example.com/1", "2026-05-25"),
            )
        pg_conn.commit()
        assert "https://example.com/1" in existing_urls(pg_conn, TEST_USER)

    def test_ignores_empty_url_rows(self, pg_conn) -> None:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO applications (user_id, company, role, offer_url, detection_date)"
                " VALUES (%s, %s, %s, %s, %s)",
                (TEST_USER, "Acme", "Dev", "", "2026-05-25"),
            )
        pg_conn.commit()
        assert existing_urls(pg_conn, TEST_USER) == set()

    def test_scoped_to_user(self, pg_conn) -> None:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO applications (user_id, company, role, offer_url, detection_date)"
                " VALUES (%s, %s, %s, %s, %s)",
                ("other-user", "Acme", "Dev", "https://example.com/2", "2026-05-25"),
            )
        pg_conn.commit()
        assert existing_urls(pg_conn, TEST_USER) == set()


class TestInsertOffer:
    def test_inserts_correct_fields(self, pg_conn) -> None:
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/123",
            portal="wtfj",
            location="Paris",
            date_posted=date(2026, 5, 20),
            score=4.2,
        )
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT company, role, offer_url, detection_date, score_grade, score_value, status"
                " FROM applications"
            )
            row = cur.fetchone()
        assert row[0] == "Mistral AI"
        assert row[1] == "AI Engineer"
        assert row[2] == "https://wttj.co/jobs/123"
        assert row[3] == "2026-05-20"
        assert row[4] == "A"
        assert abs(row[5] - 4.2) < 0.001
        assert row[6] == "À envoyer"

    def test_uses_today_when_date_posted_is_none(self, pg_conn) -> None:
        offer = RawOffer(title="Dev", company="Co", url="https://x.com/1", portal="p")
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT detection_date FROM applications")
            row = cur.fetchone()
        assert row[0] == date.today().isoformat()

    def test_inserts_description(self, pg_conn) -> None:
        offer = RawOffer(
            title="AI Engineer",
            company="Acme",
            url="https://x.com/1",
            portal="p",
            description="We are looking for an AI Engineer with 3+ years experience.",
        )
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT description FROM applications")
            row = cur.fetchone()
        data = json.loads(row[0])
        assert isinstance(data, dict)
        assert "mission" in data

    def test_inserts_empty_description_by_default(self, pg_conn) -> None:
        offer = RawOffer(title="Dev", company="Co", url="https://x.com/1", portal="p")
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT description FROM applications")
            row = cur.fetchone()
        data = json.loads(row[0])
        assert isinstance(data, dict)
        assert data["mission"] == ""

    def test_description_is_valid_json(self, pg_conn) -> None:
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/999",
            portal="wttj",
            description="Missions : Développer des modèles ML. Profil : Python 3 ans.",
        )
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT description FROM applications")
            row = cur.fetchone()
        data = json.loads(row[0])
        assert "mission" in data
        assert "profil" in data
        assert "stack" in data
        assert "avantages" in data
        assert "contrat" in data
        assert "salaire" in data

    def test_portal_column_populated(self, pg_conn) -> None:
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/999",
            portal="wttj",
        )
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT portal FROM applications")
            row = cur.fetchone()
        assert row[0] == "wttj"

    def test_prepopulated_parsed_description_used_directly(self, pg_conn) -> None:
        from scripts.models import ParsedDescription

        pd = ParsedDescription(mission="custom mission", stack="PyTorch")
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/999",
            portal="wttj",
            parsed_description=pd,
        )
        insert_offer(pg_conn, offer, TEST_USER)
        pg_conn.commit()
        with pg_conn.cursor() as cur:
            cur.execute("SELECT description FROM applications")
            row = cur.fetchone()
        data = json.loads(row[0])
        assert data["mission"] == "custom mission"
        assert data["stack"] == "PyTorch"


class TestImportOffers:
    def test_inserts_new_offers(self, mock_pg_connect) -> None:
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
        inserted, skipped = import_offers(offers, TEST_USER)
        assert inserted == 2
        assert skipped == 0

    def test_skips_duplicate_url_on_second_run(self, mock_pg_connect) -> None:
        offer = RawOffer(
            title="AI Engineer",
            company="Acme",
            url="https://x.com/1",
            portal="p",
            score=4.0,
        )
        import_offers([offer], TEST_USER)
        inserted, skipped = import_offers([offer], TEST_USER)
        assert inserted == 0
        assert skipped == 1

    def test_empty_url_offers_always_inserted(self, mock_pg_connect) -> None:
        offer = RawOffer(
            title="AI Engineer", company="Acme", url="", portal="p", score=4.0
        )
        import_offers([offer], TEST_USER)
        inserted, skipped = import_offers([offer], TEST_USER)
        assert inserted == 1
        assert skipped == 0

    def test_empty_list_returns_zero(self, mock_pg_connect) -> None:
        inserted, skipped = import_offers([], TEST_USER)
        assert inserted == 0
        assert skipped == 0


class TestLivenessIntegration:
    def test_expired_offer_skipped_with_liveness(
        self, mock_pg_connect, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.import_offers as io

        monkeypatch.setattr(
            "scripts.import_offers.check_liveness",
            lambda url, **kw: ("expired", "http_404"),
        )
        offer = RawOffer(
            title="ML Engineer",
            company="Acme",
            url="https://jobs.example.com/1",
            portal="apec",
        )
        inserted, skipped, expired = io.import_offers_with_liveness([offer], TEST_USER)
        assert inserted == 0
        assert expired == 1

    def test_uncertain_offer_imported_normally(
        self, mock_pg_connect, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.import_offers as io

        monkeypatch.setattr(
            "scripts.import_offers.check_liveness",
            lambda url, **kw: ("uncertain", "timeout"),
        )
        offer = RawOffer(
            title="ML Engineer",
            company="Acme",
            url="https://jobs.example.com/2",
            portal="apec",
        )
        inserted, skipped, expired = io.import_offers_with_liveness([offer], TEST_USER)
        assert inserted == 1
        assert expired == 0


class TestExpireStaleOffers:
    def _seed(self, conn, url: str, status: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO applications (user_id, company, role, offer_url, detection_date, status)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (TEST_USER, "Acme", "ML Engineer", url, "2026-01-01", status),
            )
        conn.commit()

    def test_expired_offer_marked_abandoned(
        self, mock_pg_connect, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.import_offers as io

        monkeypatch.setattr(
            "scripts.import_offers.check_liveness",
            lambda url, **kw: ("expired", "http_404"),
        )
        self._seed(mock_pg_connect, "https://jobs.example.com/1", "À envoyer")
        abandoned = io.expire_stale_offers(TEST_USER)
        assert abandoned == 1
        with mock_pg_connect.cursor() as cur:
            cur.execute(
                "SELECT status FROM applications WHERE offer_url = %s",
                ("https://jobs.example.com/1",),
            )
            row = cur.fetchone()
        assert row[0] == "Abandonnée"

    def test_active_offer_unchanged(
        self, mock_pg_connect, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.import_offers as io

        monkeypatch.setattr(
            "scripts.import_offers.check_liveness",
            lambda url, **kw: ("active", "ok"),
        )
        self._seed(mock_pg_connect, "https://jobs.example.com/2", "À envoyer")
        abandoned = io.expire_stale_offers(TEST_USER)
        assert abandoned == 0
        with mock_pg_connect.cursor() as cur:
            cur.execute(
                "SELECT status FROM applications WHERE offer_url = %s",
                ("https://jobs.example.com/2",),
            )
            row = cur.fetchone()
        assert row[0] == "À envoyer"

    def test_non_a_envoyer_status_not_checked(
        self, mock_pg_connect, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.import_offers as io

        checked: list[str] = []
        monkeypatch.setattr(
            "scripts.import_offers.check_liveness",
            lambda url, **kw: checked.append(url) or ("expired", "http_404"),
        )
        self._seed(mock_pg_connect, "https://jobs.example.com/3", "Envoyée")
        io.expire_stale_offers(TEST_USER)
        assert len(checked) == 0
