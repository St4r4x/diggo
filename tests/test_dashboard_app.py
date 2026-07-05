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

        async def fake_run_pipeline(_settings, *, skip_descriptions=False):
            return []

        def fake_import_offers(_offers, user_id):
            return (7, 2)

        def fake_expire_stale(_url=None, user_id=None):
            return 0

        def fake_load_settings():
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

        async def fake_run_pipeline(_settings, *, skip_descriptions=False):
            raise RuntimeError("Connection refused")

        def fake_load_settings():
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
        assert "copyPrepCmd" in r.text
        assert f"copyPrepCmd({row['id']})" in r.text

    def test_apply_status_shows_lm_checkbox(self, client_with_data: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(
            r
            for r in db.get_all({}, user_id=TEST_USER_ID)
            if r["status"] == "À envoyer"
        )
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "Inclure lettre de motivation" in r.text
        assert f"lm-toggle-{row['id']}" in r.text

    def test_apply_status_cv_only_command_uses_generate_cv(
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
        assert "generate-cv.md" in r.text

    def test_apply_status_with_lm_command_uses_prepare_candidature(
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
        assert "prepare-candidature.md" in r.text
        assert "--no-prep" in r.text

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
