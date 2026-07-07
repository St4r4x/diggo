import asyncio
import os
from datetime import date, timedelta
from pathlib import Path
import sys

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

PG_URL = os.getenv("DATABASE_URL", "postgresql://career:career@localhost:5432/career")
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
    from auth import get_current_user

    test_db = _make_pg_db()
    dashboard_app.app.state.db = test_db
    dashboard_app.app.state.scan_status = "idle"
    dashboard_app.app.state.scan_result = {
        "inserted": 0,
        "skipped": 0,
        "found": 0,
        "scored": 0,
        "abandoned": 0,
        "error": "",
    }
    dashboard_app.app.dependency_overrides[get_current_user] = lambda: MOCK_USER
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


class TestRoot:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200

    def test_contains_app_title(self, client: TestClient) -> None:
        r = client.get("/")
        assert "career-ops-fr" in r.text.lower()

    def test_requires_auth(self) -> None:
        import app as dashboard_app
        from auth import get_current_user

        dashboard_app.app.dependency_overrides.pop(get_current_user, None)
        c = TestClient(
            dashboard_app.app, raise_server_exceptions=False, follow_redirects=False
        )
        r = c.get("/")
        assert r.status_code == 302


class TestOfferList:
    def test_returns_200(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/offers")
        assert r.status_code == 200

    def test_shows_company_names(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/offers")
        assert "Mistral AI" in r.text
        assert "Doctrine" in r.text

    def test_filters_by_status(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/offers?status=Envoyée")
        assert "Doctrine" in r.text
        assert "Mistral AI" not in r.text

    def test_filters_by_grade(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/offers?grade=A")
        assert "Doctrine" in r.text
        assert "Mistral AI" not in r.text

    def test_filters_by_search(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/offers?q=mistral")
        assert "Mistral AI" in r.text
        assert "Doctrine" not in r.text


class TestOfferDetail:
    def test_returns_200_for_existing(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200

    def test_shows_company_and_role(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert row["company"] in r.text
        assert row["role"] in r.text

    def test_returns_404_for_missing(self, client: TestClient) -> None:
        r = client.get("/offers/999")
        assert r.status_code == 404

    def test_shows_offer_url_as_link(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert f'href="{row["offer_url"]}"' in r.text

    def test_shows_grade_badge(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert row["score_grade"] in r.text

    def test_shows_description_excerpt(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        with db.conn.cursor() as cur:
            cur.execute(
                "UPDATE applications SET description = %s WHERE company = %s AND user_id = %s",
                (
                    "This is a long job description with many details about requirements.",
                    "Mistral AI",
                    TEST_USER_ID,
                ),
            )
        db.conn.commit()
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert "This is a long job description" in r.text

    def test_offer_detail_includes_prep_sheet_path(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        db.update(
            1,
            {"prep_sheet_path": "output/acme-2026-07-06/prep-sheet.pdf"},
            user_id=TEST_USER_ID,
        )
        r = client_with_data.get("/offers/1")
        assert r.status_code == 200
        offer = db.get_by_id(1, user_id=TEST_USER_ID)
        assert offer["prep_sheet_path"] == "output/acme-2026-07-06/prep-sheet.pdf"


class TestOfferEdit:
    def test_edit_returns_form(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.get(f"/offers/{row['id']}/edit")
        assert r.status_code == 200
        assert "form" in r.text.lower() or "input" in r.text.lower()

    def test_save_updates_notes(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
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
        updated = db.get_by_id(row["id"], user_id=TEST_USER_ID)
        assert updated["notes"] == "Test note"

    def test_save_does_not_clear_existing_description(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        with db.conn.cursor() as cur:
            cur.execute(
                "UPDATE applications SET description = %s WHERE id = %s AND user_id = %s",
                ("Original job description text.", row["id"], TEST_USER_ID),
            )
        db.conn.commit()
        client_with_data.post(
            f"/offers/{row['id']}",
            data={
                "company": row["company"],
                "role": row["role"],
                "detection_date": row["detection_date"],
                "score_grade": row["score_grade"],
                "score_value": str(row["score_value"]),
                "status": row["status"],
                "notes": "Updated note",
                "offer_url": row["offer_url"] or "",
                "send_date": "",
                "follow_up_date": "",
                "contacts": "",
                "cv_path": "",
                "cover_letter_path": "",
                "description": "",
            },
        )
        updated = db.get_by_id(row["id"], user_id=TEST_USER_ID)
        assert updated["description"] == "Original job description text."

    def test_save_returns_404_for_missing(self, client: TestClient) -> None:
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
    def test_delete_removes_row(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        rid = row["id"]
        r = client_with_data.delete(f"/offers/{rid}")
        assert r.status_code == 200
        assert db.get_by_id(rid, user_id=TEST_USER_ID) is None


class TestOfferStatus:
    def test_status_change_returns_updated_detail(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.post(
            f"/offers/{row['id']}/status", data={"status": "Envoyée"}
        )
        assert r.status_code == 200
        updated = db.get_by_id(row["id"], user_id=TEST_USER_ID)
        assert updated["status"] == "Envoyée"

    def test_invalid_status_rejected(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.post(
            f"/offers/{row['id']}/status", data={"status": "InvalidStatus"}
        )
        assert r.status_code == 422


class TestOfferNotes:
    def test_notes_saved_and_returned(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        r = client_with_data.post(
            f"/offers/{row['id']}/notes",
            data={
                "notes": "Question à poser : stack MLOps\nPoint clé : remote possible ?"
            },
        )
        assert r.status_code == 200
        assert "Question" in r.text
        updated = db.get_by_id(row["id"], user_id=TEST_USER_ID)
        assert "Question à poser" in updated["notes"]

    def test_notes_empty_clears_field(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        db.update(row["id"], {"notes": "old note"}, user_id=TEST_USER_ID)
        r = client_with_data.post(f"/offers/{row['id']}/notes", data={"notes": ""})
        assert r.status_code == 200
        updated = db.get_by_id(row["id"], user_id=TEST_USER_ID)
        assert updated["notes"] == ""

    def test_notes_404_for_missing_offer(self, client: TestClient) -> None:
        r = client.post("/offers/99999/notes", data={"notes": "test"})
        assert r.status_code == 404


class TestStats:
    def test_stats_returns_200(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/stats")
        assert r.status_code == 200

    def test_stats_shows_total_count(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        stats = db.get_stats(user_id=TEST_USER_ID)
        r = client_with_data.get("/stats")
        assert str(stats["total"]) in r.text

    def test_stats_empty_db_returns_200(self, client: TestClient) -> None:
        r = client.get("/stats")
        assert r.status_code == 200
        assert "0" in r.text

    def test_stats_shows_all_statuses(self, client_with_data: TestClient) -> None:
        from db import VALID_STATUSES

        r = client_with_data.get("/stats")
        for s in VALID_STATUSES:
            assert s in r.text


class TestScan:
    def test_scan_start_when_idle_returns_running(
        self, client: TestClient, monkeypatch
    ) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "idle"

        def mock_create_task(coro):
            coro.close()
            return None

        monkeypatch.setattr("asyncio.create_task", mock_create_task)
        r = client.post("/scan/start")
        assert r.status_code == 200
        assert "Scan en cours" in r.text

    def test_scan_start_when_running_does_not_create_second_task(
        self, client: TestClient, monkeypatch
    ) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "running"
        created = []

        def mock_create_task(coro):
            created.append(coro)
            coro.close()
            return None

        monkeypatch.setattr("asyncio.create_task", mock_create_task)
        r = client.post("/scan/start")
        assert r.status_code == 200
        assert len(created) == 0

    def test_scan_status_idle(self, client: TestClient) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "idle"
        dashboard_app.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "Scanner" in r.text
        assert "Scan en cours" not in r.text

    def test_scan_status_done_shows_inserted_count(self, client: TestClient) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "done"
        dashboard_app.app.state.scan_result = {"inserted": 3, "skipped": 5, "error": ""}
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "3" in r.text

    def test_scan_status_error_shows_message(self, client: TestClient) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "error"
        dashboard_app.app.state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "error": "Connection timeout",
        }
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "Erreur" in r.text

    def test_concurrent_scan_start_spawns_only_one_task(
        self, client: TestClient, monkeypatch
    ) -> None:
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "idle"
        created = []

        def mock_create_task(coro):
            created.append(coro)
            coro.close()
            return None

        monkeypatch.setattr(dashboard_app.asyncio, "create_task", mock_create_task)
        r1 = client.post("/scan/start")
        r2 = client.post("/scan/start")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert len(created) == 1

    def test_scan_full_flow(self, client: TestClient, monkeypatch) -> None:
        import app as dashboard_app
        from app import _run_scan_task

        dashboard_app.app.state.scan_status = "idle"
        dashboard_app.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}

        async def fake_run_pipeline(
            _settings, *, skip_descriptions=False, user_id=None
        ):
            return []

        def fake_import_offers(_offers, user_id):
            return (7, 2)

        def fake_expire_stale(_url=None, user_id=None):
            return 0

        def fake_load_settings(user_id=None):
            return {}

        monkeypatch.setattr("scripts.import_offers._run_pipeline", fake_run_pipeline)
        monkeypatch.setattr("scripts.import_offers.import_offers", fake_import_offers)
        monkeypatch.setattr(
            "scripts.import_offers.expire_stale_offers", fake_expire_stale
        )
        monkeypatch.setattr("scripts.pre_filter.load_settings", fake_load_settings)

        asyncio.run(_run_scan_task(dashboard_app.app.state, TEST_USER_ID))

        assert dashboard_app.app.state.scan_status == "done"
        assert dashboard_app.app.state.scan_result["inserted"] == 7

    def test_scan_task_exception_sets_error_status(
        self, client: TestClient, monkeypatch
    ) -> None:
        import app as dashboard_app
        from app import _run_scan_task

        dashboard_app.app.state.scan_status = "idle"
        dashboard_app.app.state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "found": 0,
            "scored": 0,
            "abandoned": 0,
            "error": "",
        }

        async def fake_run_pipeline(
            _settings, *, skip_descriptions=False, user_id=None
        ):
            raise RuntimeError("Connection refused")

        def fake_load_settings(user_id=None):
            return {}

        monkeypatch.setattr("scripts.import_offers._run_pipeline", fake_run_pipeline)
        monkeypatch.setattr("scripts.pre_filter.load_settings", fake_load_settings)

        asyncio.run(_run_scan_task(dashboard_app.app.state, TEST_USER_ID))

        assert dashboard_app.app.state.scan_status == "error"
        assert "Connection refused" in dashboard_app.app.state.scan_result["error"]


class TestPrepareCandidature:
    def test_apply_status_shows_prep_button(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(
            r
            for r in db.get_all({}, user_id=TEST_USER_ID)
            if r["status"] == "À envoyer"
        )
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert f'hx-post="/offers/{row["id"]}/prepare"' in r.text
        assert "✦ Préparer candidature (IA)" in r.text

    def test_apply_status_shows_skip_prep_checkbox(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(
            r
            for r in db.get_all({}, user_id=TEST_USER_ID)
            if r["status"] == "À envoyer"
        )
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "Sans fiche de préparation d'entretien" in r.text
        assert 'name="skip_prep"' in r.text

    def test_interview_status_shows_interview_button(
        self, client_with_interview_offer: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(
            r
            for r in db.get_all({}, user_id=TEST_USER_ID)
            if r["status"] == "Entretien RH"
        )
        r = client_with_interview_offer.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert "copyInterviewCmd" in r.text
        assert f"copyInterviewCmd({row['id']})" in r.text
        assert "prepare-entretien.md" in r.text

    def test_interview_status_hides_prep_button(
        self, client_with_interview_offer: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(
            r
            for r in db.get_all({}, user_id=TEST_USER_ID)
            if r["status"] == "Entretien RH"
        )
        r = client_with_interview_offer.get(f"/offers/{row['id']}")
        assert "copyPrepCmd" not in r.text

    def test_terminal_status_shows_no_action_buttons(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({}, user_id=TEST_USER_ID)[0]
        db.update(row["id"], {"status": "Refusée"}, user_id=TEST_USER_ID)
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "copyPrepCmd" not in r.text
        assert "copyInterviewCmd" not in r.text


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


class TestFollowupReminders:
    def _insert_overdue(self, db, company: str, status: str) -> None:
        _insert_row(
            db,
            company=company,
            offer_url="https://example.com",
            detection_date="2026-06-01",
            score_grade="B",
            score_value=3.5,
            status=status,
            send_date="2026-06-01",
        )

    def test_bandeau_shown_when_overdue_envoyee(self, client: TestClient) -> None:
        import app as dashboard_app

        self._insert_overdue(dashboard_app.app.state.db, "OverdueCo", "Envoyée")
        r = client.get("/")
        assert r.status_code == 200
        assert "relancer" in r.text.lower()

    def test_bandeau_hidden_when_no_followups(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "à relancer" not in r.text.lower()

    def test_offer_list_shows_followup_dot_for_overdue(
        self, client: TestClient
    ) -> None:
        import app as dashboard_app

        self._insert_overdue(dashboard_app.app.state.db, "DotCo", "Entretien RH")
        r = client.get("/offers")
        assert r.status_code == 200
        assert "followup-dot" in r.text


class TestStatsFunnel:
    def test_stats_shows_funnel_steps(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/stats")
        assert r.status_code == 200
        assert "Entretien RH" in r.text
        assert "Entretien tech" in r.text

    def test_stats_shows_exit_statuses(self, client_with_data: TestClient) -> None:
        r = client_with_data.get("/stats")
        assert "Refusée" in r.text
        assert "Abandonnée" in r.text

    def test_build_funnel_computes_rate(self) -> None:
        from app import _build_funnel

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
        funnel, exits, max_count = _build_funnel(by_status)
        envoyee_step = next(s for s in funnel if s["status"] == "Envoyée")
        assert envoyee_step["rate"] == 50.0
        entretien_step = next(s for s in funnel if s["status"] == "Entretien RH")
        assert entretien_step["rate"] is None
        assert len(exits) == 2
        assert exits[0]["status"] == "Refusée"


class TestAuthRoutes:
    def test_login_page_loads(self) -> None:
        import app as dashboard_app

        raw = TestClient(dashboard_app.app)
        r = raw.get("/login", follow_redirects=False)
        assert r.status_code == 200
        assert "login" in r.text.lower()

    def test_session_post_sets_cookies(self) -> None:
        import time

        import app as dashboard_app
        import jwt

        secret = os.environ["SUPABASE_JWT_SECRET"]
        access_token = jwt.encode(
            {
                "sub": "u1",
                "email": "t@t.com",
                "exp": int(time.time()) + 3600,
                "aud": "authenticated",
            },
            secret,
            algorithm="HS256",
        )
        raw = TestClient(dashboard_app.app)
        r = raw.post(
            "/auth/session",
            json={"access_token": access_token, "refresh_token": "dummy-refresh"},
        )
        assert r.status_code == 200
        assert "session" in r.cookies
        assert "refresh" in r.cookies

    def test_session_delete_clears_cookies(self) -> None:
        import app as dashboard_app

        raw = TestClient(dashboard_app.app)
        r = raw.delete("/auth/session", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"


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


@pytest.fixture
def authed_client(client: TestClient, monkeypatch) -> TestClient:
    import user_data

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


class TestReportWidget:
    def test_shows_no_report_message_when_none_exist(
        self, client: TestClient, tmp_path, monkeypatch
    ) -> None:
        import app as dashboard_app

        monkeypatch.setattr(dashboard_app, "REPORTS_DIR", tmp_path)
        r = client.get("/stats")
        assert r.status_code == 200
        assert "Aucun rapport" in r.text

    def test_shows_latest_report_content(
        self, client: TestClient, tmp_path, monkeypatch
    ) -> None:
        import app as dashboard_app

        report_file = tmp_path / "daily-2026-07-03.md"
        report_file.write_text(
            "# Daily Report\n\n**Total offers:** 5", encoding="utf-8"
        )
        monkeypatch.setattr(dashboard_app, "REPORTS_DIR", tmp_path)
        r = client.get("/stats")
        assert r.status_code == 200
        assert "Total offers" in r.text
        assert "2026-07-03" in r.text

    def test_shows_most_recent_when_multiple_reports(
        self, client: TestClient, tmp_path, monkeypatch
    ) -> None:
        import app as dashboard_app

        (tmp_path / "daily-2026-07-01.md").write_text("Old report", encoding="utf-8")
        (tmp_path / "daily-2026-07-03.md").write_text(
            "New report 2026-07-03", encoding="utf-8"
        )
        monkeypatch.setattr(dashboard_app, "REPORTS_DIR", tmp_path)
        r = client.get("/stats")
        assert "New report" in r.text
        assert "Old report" not in r.text


class TestOfferPrepare:
    _LONG_DESCRIPTION = "We need an ML engineer with PyTorch and RAG experience. " * 10

    _SAMPLE_CV = {
        "meta": {"summary": "AI engineer with a background in sales."},
        "experience": [
            {
                "id": 1,
                "title": "AI Engineer",
                "company": "Missia",
                "type": "CDI",
                "period": "2024-2026",
                "sort_order": 0,
                "bullets": ["Built RAG pipelines"],
            }
        ],
        "skills": [{"id": 1, "category": "ML", "skill": "PyTorch", "sort_order": 0}],
        "certifications": [],
        "education": [],
    }

    _SAMPLE_PROFILE = {
        "name": "Arnaud Thery",
        "title": "AI/ML Engineer",
        "email": "arnaud@example.com",
        "phone": "0600000000",
        "location": "Paris",
        "linkedin": "",
        "github": "",
        "profile_md": "",
    }

    def _patch_phases(self, monkeypatch: pytest.MonkeyPatch, dashboard_app) -> None:
        import llm

        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_hf_token",
            lambda conn, uid: "test-hf-token",
        )
        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_profile",
            lambda conn, uid: self._SAMPLE_PROFILE,
        )
        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_cv",
            lambda conn, uid, lang="fr": self._SAMPLE_CV,
        )
        monkeypatch.setattr(
            llm,
            "analyze_offer",
            lambda hf_token, offer: llm.OfferAnalysis(
                top_skills=["PyTorch"],
                keywords=["MLOps"],
                company_context="AI startup.",
                gaps=[],
                hook_angle="Their open-source engine.",
                offer_language="fr",
                requires_english_cv=False,
            ),
        )
        monkeypatch.setattr(
            llm,
            "rewrite_cv_summary",
            lambda hf_token, profile, cv, analysis: llm.CvRewrite(
                highlighted_skills=["PyTorch"], summary="Tailored summary."
            ),
        )
        monkeypatch.setattr(
            llm,
            "write_cover_letter",
            lambda hf_token, profile, cv, offer, analysis: llm.CoverLetterDraft(
                paragraphs=["Hook.", "Proof.", "Close."],
                citations=[{"claim": "Built RAG pipelines", "experience_id": 1}],
            ),
        )
        monkeypatch.setattr(
            llm,
            "generate_prep_questions",
            lambda hf_token, offer, analysis: llm.PrepSheetDraft(
                company_summary="AI startup.",
                tech_stack=["Python"],
                questions=[{"theme": "Technique ML", "question": "Explain RAG."}],
            ),
        )

    def test_prepare_happy_path_writes_all_three_paths(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)
        monkeypatch.setattr(
            "scripts.generate_pdf.generate_pdf", lambda ctx, **kw: tmp_path / "cv.pdf"
        )
        monkeypatch.setattr(
            "scripts.generate_cover_letter.generate_pdf",
            lambda ctx, **kw: tmp_path / "cl.pdf",
        )
        monkeypatch.setattr(
            "scripts.generate_prep_sheet.generate_pdf",
            lambda ctx, **kw: tmp_path / "prep.pdf",
        )

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == str(tmp_path / "cv.pdf")
        assert offer["cover_letter_path"] == str(tmp_path / "cl.pdf")
        assert offer["prep_sheet_path"] == str(tmp_path / "prep.pdf")

    def test_prepare_skip_prep_leaves_prep_sheet_path_empty(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)

        def _fail_prep_questions(hf_token: str, offer: dict, analysis: object) -> None:
            raise AssertionError(
                "generate_prep_questions should not be called when skip_prep=True"
            )

        monkeypatch.setattr(llm, "generate_prep_questions", _fail_prep_questions)
        monkeypatch.setattr(
            "scripts.generate_pdf.generate_pdf", lambda ctx, **kw: tmp_path / "cv.pdf"
        )
        monkeypatch.setattr(
            "scripts.generate_cover_letter.generate_pdf",
            lambda ctx, **kw: tmp_path / "cl.pdf",
        )

        r = client.post(f"/offers/{offer_id}/prepare", data={"skip_prep": "true"})

        assert r.status_code == 200
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == str(tmp_path / "cv.pdf")
        assert offer["prep_sheet_path"] == ""

    def test_prepare_rejects_thin_description(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description="Too short.")

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "trop courte" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_blocks_when_hf_token_missing(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Ajoute ton token Hugging Face" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_llm_failure_shows_error_and_writes_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        monkeypatch.setattr(
            dashboard_app.user_data, "get_hf_token", lambda conn, uid: "test-hf-token"
        )

        def _fail_analyze(hf_token: str, offer: dict) -> None:
            raise llm.LLMError("both providers down")

        monkeypatch.setattr(llm, "analyze_offer", _fail_analyze)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Échec de la préparation IA" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_grounding_failure_shows_error_and_writes_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)

        def _fail_cover_letter(
            hf_token: str, profile: dict, cv: dict, offer: dict, analysis: object
        ) -> None:
            raise llm.GroundingError("invalid citation")

        monkeypatch.setattr(llm, "write_cover_letter", _fail_cover_letter)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Échec de la préparation IA" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_pdf_rendering_failure_shows_error_and_writes_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)

        def _fail_render(ctx: dict, **kw: object) -> None:
            raise RuntimeError("weasyprint boom")

        monkeypatch.setattr("scripts.generate_pdf.generate_pdf", _fail_render)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Échec de la génération des PDF" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""
