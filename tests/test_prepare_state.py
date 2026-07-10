from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import psycopg2
import pytest

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-32-chars-minimum-ok!")
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

import llm
import prepare_state
import user_data

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
USER_A = "user-a-test"
USER_B = "user-b-test"

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
    "projects": [
        {
            "id": 1,
            "name": "Kaggle Watson",
            "stack": ["PyTorch"],
            "desc": "NLI",
            "sort_order": 0,
        }
    ],
    "languages": [{"id": 1, "name": "Français (natif)", "sort_order": 0}],
    "hobbies": [{"id": 1, "name": "Tennis", "sort_order": 0}],
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

_CREATE_TEMP = """
CREATE TEMP TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
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
def pg_conn():
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_TEMP)
    conn.commit()
    yield conn
    conn.close()


class _NoCloseConn:
    """Proxies cursor/commit/autocommit to a real connection but no-ops close(),
    so prepare_state's own conn.close() doesn't kill the test fixture's connection.
    Mirrors tests/test_import_offers.py's established _NoClose pattern."""

    def __init__(self, real_conn) -> None:
        self._c = real_conn

    def cursor(self):
        return self._c.cursor()

    def commit(self) -> None:
        self._c.commit()

    def close(self) -> None:
        pass

    @property
    def autocommit(self) -> bool:
        return self._c.autocommit

    @autocommit.setter
    def autocommit(self, val: bool) -> None:
        self._c.autocommit = val


class _NoCloseDB:
    def __init__(self, real_db, no_close_conn: _NoCloseConn) -> None:
        self._real = real_db
        self.conn = no_close_conn

    def get_by_id(self, *a, **kw):
        return self._real.get_by_id(*a, **kw)

    def update(self, *a, **kw):
        return self._real.update(*a, **kw)


@pytest.fixture
def prepared_db(pg_conn, monkeypatch):
    from db import DB

    real_db = DB(pg_conn)
    no_close_conn = _NoCloseConn(pg_conn)
    monkeypatch.setattr(
        prepare_state, "open_db", lambda url: _NoCloseDB(real_db, no_close_conn)
    )
    return real_db


def _insert_row(db, user_id: str, description: str = "") -> int:
    with db.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applications (user_id, company, role, detection_date, description)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, "Acme", "ML Engineer", "2026-07-09", description),
        )
        row_id = cur.fetchone()[0]
    db.conn.commit()
    return row_id


def _patch_phases(monkeypatch) -> None:
    monkeypatch.setattr(user_data, "get_hf_token", lambda conn, uid: "test-hf-token")
    monkeypatch.setattr(user_data, "get_profile", lambda conn, uid: _SAMPLE_PROFILE)
    monkeypatch.setattr(user_data, "get_cv", lambda conn, uid, lang="fr": _SAMPLE_CV)
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


def test_get_prepare_state_defaults_to_idle() -> None:
    prepare_state._status.clear()
    prepare_state._stage.clear()
    prepare_state._error.clear()
    state = prepare_state.get_prepare_state(999)
    assert state == {"status": "idle", "stage": "", "error": ""}


def test_start_prepare_sets_running(monkeypatch) -> None:
    prepare_state._status.clear()
    monkeypatch.setattr(asyncio, "create_task", lambda coro: coro.close())
    prepare_state.start_prepare(1, USER_A, skip_prep=False)
    assert prepare_state.get_prepare_state(1)["status"] == "running"


def test_start_prepare_already_running_does_not_spawn_second_task(monkeypatch) -> None:
    prepare_state._status.clear()
    created = []
    monkeypatch.setattr(
        asyncio,
        "create_task",
        lambda coro: created.append(coro) or coro.close(),
    )
    prepare_state.start_prepare(1, USER_A, skip_prep=False)
    prepare_state.start_prepare(1, USER_A, skip_prep=False)
    assert len(created) == 1


def test_prepare_state_isolated_per_offer(monkeypatch) -> None:
    prepare_state._status.clear()
    monkeypatch.setattr(asyncio, "create_task", lambda coro: coro.close())
    prepare_state.start_prepare(1, USER_A, skip_prep=False)
    assert prepare_state.get_prepare_state(1)["status"] == "running"
    assert prepare_state.get_prepare_state(2)["status"] == "idle"


def test_run_prepare_success_writes_all_three_paths(
    prepared_db, monkeypatch, tmp_path
) -> None:
    prepare_state._status.clear()
    offer_id = _insert_row(prepared_db, USER_A, description=_LONG_DESCRIPTION)
    _patch_phases(monkeypatch)
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

    asyncio.run(prepare_state._run_prepare(offer_id, USER_A, skip_prep=False))

    state = prepare_state.get_prepare_state(offer_id)
    assert state["status"] == "done"
    offer = prepared_db.get_by_id(offer_id, user_id=USER_A)
    assert offer["cv_path"] == str(tmp_path / "cv.pdf")
    assert offer["cover_letter_path"] == str(tmp_path / "cl.pdf")
    assert offer["prep_sheet_path"] == str(tmp_path / "prep.pdf")


def test_run_prepare_cv_context_includes_projects_languages_hobbies(
    prepared_db, monkeypatch, tmp_path
) -> None:
    prepare_state._status.clear()
    offer_id = _insert_row(prepared_db, USER_A, description=_LONG_DESCRIPTION)
    _patch_phases(monkeypatch)
    captured_ctx = {}

    def _capture_cv_pdf(ctx, **kw):
        captured_ctx.update(ctx)
        return tmp_path / "cv.pdf"

    monkeypatch.setattr("scripts.generate_pdf.generate_pdf", _capture_cv_pdf)
    monkeypatch.setattr(
        "scripts.generate_cover_letter.generate_pdf",
        lambda ctx, **kw: tmp_path / "cl.pdf",
    )
    monkeypatch.setattr(
        "scripts.generate_prep_sheet.generate_pdf",
        lambda ctx, **kw: tmp_path / "prep.pdf",
    )

    asyncio.run(prepare_state._run_prepare(offer_id, USER_A, skip_prep=False))

    assert captured_ctx["projects"] == _SAMPLE_CV["projects"]
    assert captured_ctx["languages"] == ["Français (natif)"]
    assert captured_ctx["hobbies"] == ["Tennis"]


def test_run_prepare_skip_prep_leaves_prep_sheet_path_empty(
    prepared_db, monkeypatch, tmp_path
) -> None:
    prepare_state._status.clear()
    offer_id = _insert_row(prepared_db, USER_A, description=_LONG_DESCRIPTION)
    _patch_phases(monkeypatch)

    def _fail_prep_questions(hf_token, offer, analysis):
        raise AssertionError("should not be called when skip_prep=True")

    monkeypatch.setattr(llm, "generate_prep_questions", _fail_prep_questions)
    monkeypatch.setattr(
        "scripts.generate_pdf.generate_pdf", lambda ctx, **kw: tmp_path / "cv.pdf"
    )
    monkeypatch.setattr(
        "scripts.generate_cover_letter.generate_pdf",
        lambda ctx, **kw: tmp_path / "cl.pdf",
    )

    asyncio.run(prepare_state._run_prepare(offer_id, USER_A, skip_prep=True))

    offer = prepared_db.get_by_id(offer_id, user_id=USER_A)
    assert offer["cv_path"] == str(tmp_path / "cv.pdf")
    assert offer["prep_sheet_path"] == ""


def test_run_prepare_llm_failure_sets_error(prepared_db, monkeypatch) -> None:
    prepare_state._status.clear()
    offer_id = _insert_row(prepared_db, USER_A, description=_LONG_DESCRIPTION)
    monkeypatch.setattr(user_data, "get_hf_token", lambda conn, uid: "test-hf-token")

    def _fail_analyze(hf_token, offer):
        raise llm.LLMError("both providers down")

    monkeypatch.setattr(llm, "analyze_offer", _fail_analyze)

    asyncio.run(prepare_state._run_prepare(offer_id, USER_A, skip_prep=False))

    state = prepare_state.get_prepare_state(offer_id)
    assert state["status"] == "error"
    assert "Échec de la préparation IA" in state["error"]
    offer = prepared_db.get_by_id(offer_id, user_id=USER_A)
    assert offer["cv_path"] == ""


def test_run_prepare_pdf_failure_sets_error(prepared_db, monkeypatch) -> None:
    prepare_state._status.clear()
    offer_id = _insert_row(prepared_db, USER_A, description=_LONG_DESCRIPTION)
    _patch_phases(monkeypatch)

    def _fail_render(ctx, **kw):
        raise RuntimeError("weasyprint boom")

    monkeypatch.setattr("scripts.generate_pdf.generate_pdf", _fail_render)

    asyncio.run(prepare_state._run_prepare(offer_id, USER_A, skip_prep=False))

    state = prepare_state.get_prepare_state(offer_id)
    assert state["status"] == "error"
    assert "Échec de la génération des PDF" in state["error"]
    offer = prepared_db.get_by_id(offer_id, user_id=USER_A)
    assert offer["cv_path"] == ""
