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
    cover_letter_path TEXT NOT NULL DEFAULT '', follow_up_date TEXT,
    description TEXT NOT NULL DEFAULT ''
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
        assert f'href="{row["offer_url"]}"' in r.text

    def test_shows_grade_badge(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert row["score_grade"] in r.text

    def test_shows_description_excerpt(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        db.conn.execute(
            "UPDATE applications SET description = ? WHERE company = ?",
            (
                "This is a long job description with many details about requirements.",
                "Mistral AI",
            ),
        )
        db.conn.commit()
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert "This is a long job description" in r.text


class TestOfferEdit:
    def test_edit_returns_form(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}/edit")
        assert r.status_code == 200
        assert "form" in r.text.lower() or "input" in r.text.lower()

    def test_save_updates_notes(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.post(
            f"/offers/{row['id']}",
            data={
                "company": row["company"],
                "role": row["role"],
                "detection_date": row["detection_date"],
                "score_grade": row["score_grade"],
                "score_value": str(row["score_value"]),
                "status": row["status"],
                "notes": "Test note",
                "offer_url": row["offer_url"] or "",
                "send_date": "",
                "follow_up_date": "",
                "contacts": "",
                "cv_path": "",
                "cover_letter_path": "",
                "description": "",
            },
        )
        assert r.status_code == 200
        updated = db.get_by_id(row["id"])
        assert updated["notes"] == "Test note"

    def test_save_returns_404_for_missing(self, client):
        r = client.post(
            "/offers/999",
            data={
                "company": "X",
                "role": "Y",
                "detection_date": "2026-01-01",
                "score_grade": "A",
                "score_value": "4.0",
                "status": "À envoyer",
                "notes": "",
                "offer_url": "",
                "send_date": "",
                "follow_up_date": "",
                "contacts": "",
                "cv_path": "",
                "cover_letter_path": "",
            },
        )
        assert r.status_code == 404


class TestOfferDelete:
    def test_delete_removes_row(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        rid = row["id"]
        r = client_with_data.delete(f"/offers/{rid}")
        assert r.status_code == 200
        assert db.get_by_id(rid) is None


class TestOfferStatus:
    def test_status_change_returns_updated_detail(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.post(
            f"/offers/{row['id']}/status", data={"status": "Envoyée"}
        )
        assert r.status_code == 200
        updated = db.get_by_id(row["id"])
        assert updated["status"] == "Envoyée"

    def test_invalid_status_rejected(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.post(
            f"/offers/{row['id']}/status", data={"status": "InvalidStatus"}
        )
        assert r.status_code == 422


class TestStats:
    def test_stats_returns_200(self, client_with_data):
        r = client_with_data.get("/stats")
        assert r.status_code == 200

    def test_stats_shows_total_count(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        stats = db.get_stats()
        r = client_with_data.get("/stats")
        assert str(stats["total"]) in r.text

    def test_stats_empty_db_returns_200(self, client):
        r = client.get("/stats")
        assert r.status_code == 200
        assert "0" in r.text

    def test_stats_shows_all_statuses(self, client_with_data):
        from db import VALID_STATUSES

        r = client_with_data.get("/stats")
        for s in VALID_STATUSES:
            assert s in r.text
