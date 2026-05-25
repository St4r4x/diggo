import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

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
    cover_letter_path TEXT NOT NULL DEFAULT '', follow_up_date TEXT
)"""


@pytest.fixture
def client():
    from db import DB
    import app as dashboard_app

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(CREATE_SQL)
    conn.commit()
    test_db = DB(conn)
    dashboard_app.app.state.db = test_db
    return TestClient(dashboard_app.app)


@pytest.fixture
def client_with_data(client):
    import app as dashboard_app

    db = dashboard_app.app.state.db
    db.conn.execute(
        "INSERT INTO applications (company, role, offer_url, detection_date, "
        "score_grade, score_value, status) VALUES (?,?,?,?,?,?,?)",
        (
            "Mistral AI",
            "ML Engineer",
            "https://jobs.lever.co/mistral/1",
            "2026-05-25",
            "B",
            4.0,
            "À envoyer",
        ),
    )
    db.conn.execute(
        "INSERT INTO applications (company, role, offer_url, detection_date, "
        "score_grade, score_value, status) VALUES (?,?,?,?,?,?,?)",
        (
            "Doctrine",
            "ML Engineer",
            "https://jobs.lever.co/doctrine/1",
            "2026-05-24",
            "A",
            4.5,
            "Envoyée",
        ),
    )
    db.conn.commit()
    return client


class TestRoot:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_contains_app_title(self, client):
        r = client.get("/")
        assert "career-ops-fr" in r.text.lower()


class TestOfferList:
    def test_returns_200(self, client_with_data):
        r = client_with_data.get("/offers")
        assert r.status_code == 200

    def test_shows_company_names(self, client_with_data):
        r = client_with_data.get("/offers")
        assert "Mistral AI" in r.text
        assert "Doctrine" in r.text

    def test_filters_by_status(self, client_with_data):
        r = client_with_data.get("/offers?status=Envoyée")
        assert "Doctrine" in r.text
        assert "Mistral AI" not in r.text

    def test_filters_by_grade(self, client_with_data):
        r = client_with_data.get("/offers?grade=A")
        assert "Doctrine" in r.text
        assert "Mistral AI" not in r.text

    def test_filters_by_search(self, client_with_data):
        r = client_with_data.get("/offers?q=mistral")
        assert "Mistral AI" in r.text
        assert "Doctrine" not in r.text


class TestOfferDetail:
    def test_returns_200_for_existing(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200

    def test_shows_company_and_role(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert row["company"] in r.text
        assert row["role"] in r.text

    def test_returns_404_for_missing(self, client):
        r = client.get("/offers/999")
        assert r.status_code == 404

    def test_shows_offer_url_as_link(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert row["offer_url"] in r.text
