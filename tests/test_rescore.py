"""Tests for scripts/rescore.py."""

from __future__ import annotations

import sqlite3


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    offer_url TEXT NOT NULL DEFAULT '',
    detection_date TEXT NOT NULL DEFAULT '2026-01-01',
    score_grade TEXT NOT NULL DEFAULT 'F',
    score_value REAL NOT NULL DEFAULT 1.0,
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


def _make_db(offers: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(_CREATE_SQL)
    for o in offers:
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, score_grade, score_value, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                o.get("company", "Corp"),
                o.get("role", "Dev"),
                o.get("offer_url", "https://example.com"),
                o.get("score_grade", "F"),
                o.get("score_value", 1.0),
                o.get("description", ""),
            ),
        )
    conn.commit()
    return conn


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
    def test_dry_run_no_db_changes(self) -> None:
        from scripts.rescore import rescore

        conn = _make_db(
            [
                {
                    "company": "Mistral AI",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python pytorch docker CDI 45k€ 2 ans d'expérience",
                },
            ]
        )
        row_before = conn.execute("SELECT score_grade FROM applications").fetchone()[0]
        rescore(conn, dry_run=True)
        row_after = conn.execute("SELECT score_grade FROM applications").fetchone()[0]
        assert row_before == row_after == "F"

    def test_rescore_updates_grades(self) -> None:
        from scripts.rescore import rescore

        conn = _make_db(
            [
                {
                    "company": "Mistral AI",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python pytorch docker mlops CDI 45k€ 2 ans d'expérience",
                },
            ]
        )
        stats = rescore(conn, dry_run=False)
        row = conn.execute(
            "SELECT score_grade, score_value FROM applications"
        ).fetchone()
        assert row[0] != "F"
        assert row[1] > 1.0

    def test_rescore_idempotent(self) -> None:
        from scripts.rescore import rescore

        conn = _make_db(
            [
                {
                    "company": "Corp",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python docker CDI",
                },
            ]
        )
        rescore(conn, dry_run=False)
        row_first = conn.execute(
            "SELECT score_grade, score_value FROM applications"
        ).fetchone()
        rescore(conn, dry_run=False)
        row_second = conn.execute(
            "SELECT score_grade, score_value FROM applications"
        ).fetchone()
        assert row_first == row_second

    def test_rescore_returns_summary(self) -> None:
        from scripts.rescore import rescore

        conn = _make_db(
            [
                {
                    "company": "Corp",
                    "role": "AI Engineer",
                    "score_grade": "F",
                    "score_value": 1.0,
                    "description": "python docker CDI 45k€",
                },
            ]
        )
        stats = rescore(conn, dry_run=False)
        assert "total" in stats
        assert "changed" in stats
        assert isinstance(stats["total"], int)
