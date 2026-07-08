"""Tests for scripts/rescore.py."""

from __future__ import annotations

import os

import psycopg2
import pytest

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
TEST_USER_ID = "test-rescore-user"

_CREATE_TEMP = """
CREATE TEMP TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL DEFAULT 'test-user',
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    offer_url TEXT NOT NULL DEFAULT '',
    detection_date TEXT NOT NULL DEFAULT '2026-01-01',
    score_grade TEXT NOT NULL DEFAULT 'F',
    score_value FLOAT NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL DEFAULT 'À envoyer',
    send_date TEXT,
    contacts TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    cv_path TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT,
    description TEXT NOT NULL DEFAULT ''
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


def _fetchone(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


def _seed(conn, offers: list[dict]) -> None:
    with conn.cursor() as cur:
        for o in offers:
            cur.execute(
                "INSERT INTO applications (user_id, company, role, offer_url, score_grade, score_value, description) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    TEST_USER_ID,
                    o.get("company", "Corp"),
                    o.get("role", "Dev"),
                    o.get("offer_url", "https://example.com"),
                    o.get("score_grade", "F"),
                    o.get("score_value", 1.0),
                    o.get("description", ""),
                ),
            )
    conn.commit()


class TestInferPortal:
    def test_lever_url(self) -> None:
        from scripts.rescore import _infer_portal

        assert _infer_portal("https://jobs.lever.co/acme/123") == "lever"

    def test_greenhouse_url(self) -> None:
        from scripts.rescore import _infer_portal

        assert (
            _infer_portal("https://boards.greenhouse.io/acme/jobs/456") == "greenhouse"
        )

    def test_ashby_url(self) -> None:
        from scripts.rescore import _infer_portal

        assert _infer_portal("https://jobs.ashby.com/acme/role/789") == "ashby"

    def test_unknown_url(self) -> None:
        from scripts.rescore import _infer_portal

        assert (
            _infer_portal(
                "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/123"
            )
            == "unknown"
        )


class TestRescore:
    def test_dry_run_no_db_changes(self, pg_conn) -> None:
        from scripts.rescore import rescore

        _seed(
            pg_conn,
            [
                {
                    "company": "Mistral AI",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python pytorch docker CDI 45k€ 2 ans d'expérience",
                },
            ],
        )
        row_before = _fetchone(pg_conn, "SELECT score_grade FROM applications")[0]
        rescore(pg_conn, TEST_USER_ID, dry_run=True)
        row_after = _fetchone(pg_conn, "SELECT score_grade FROM applications")[0]
        assert row_before == row_after == "F"

    def test_rescore_updates_grades(self, pg_conn) -> None:
        from scripts.rescore import rescore

        _seed(
            pg_conn,
            [
                {
                    "company": "Mistral AI",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python pytorch docker mlops CDI 45k€ 2 ans d'expérience",
                },
            ],
        )
        rescore(pg_conn, TEST_USER_ID, dry_run=False)
        row = _fetchone(pg_conn, "SELECT score_grade, score_value FROM applications")
        assert row[0] != "F"
        assert row[1] > 1.0

    def test_rescore_idempotent(self, pg_conn) -> None:
        from scripts.rescore import rescore

        _seed(
            pg_conn,
            [
                {
                    "company": "Corp",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python docker CDI",
                },
            ],
        )
        rescore(pg_conn, TEST_USER_ID, dry_run=False)
        row_first = _fetchone(
            pg_conn, "SELECT score_grade, score_value FROM applications"
        )
        rescore(pg_conn, TEST_USER_ID, dry_run=False)
        row_second = _fetchone(
            pg_conn, "SELECT score_grade, score_value FROM applications"
        )
        assert row_first == row_second

    def test_rescore_returns_summary(self, pg_conn) -> None:
        from scripts.rescore import rescore

        _seed(
            pg_conn,
            [
                {
                    "company": "Corp",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python docker CDI 45k€",
                },
            ],
        )
        stats = rescore(pg_conn, TEST_USER_ID, dry_run=False)
        assert "total" in stats
        assert "changed" in stats
        assert isinstance(stats["total"], int)
