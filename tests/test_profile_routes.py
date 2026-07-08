import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

FAKE_PROFILE = {
    "contact": {
        "name": "Test User",
        "title": "AI Engineer",
        "email": "test@example.com",
        "phone": "+33 6 00 00 00 00",
        "location": "Paris",
        "linkedin": "",
        "github": "github.com/testuser",
    },
    "profile_md": "An experienced engineer.",
    "summary": "",
    "experience": [],
    "skills": {},
    "education": [],
    "certifications": [],
    "projects": [],
}

FAKE_CV = {
    "meta": {"summary": ""},
    "experience": [],
    "skills": [],
    "certifications": [],
    "education": [],
}


@pytest.fixture
def profile_client(monkeypatch):
    import profile_parser
    import user_data

    import app as dashboard_app
    from auth import get_current_user

    monkeypatch.setattr(
        profile_parser, "load_profile", lambda conn, user_id: dict(FAKE_PROFILE)
    )
    monkeypatch.setattr(
        profile_parser, "save_profile", lambda conn, user_id, data: None
    )
    monkeypatch.setattr(
        user_data, "get_cv", lambda conn, user_id, lang="fr": dict(FAKE_CV)
    )
    monkeypatch.setattr(
        user_data, "save_cv_meta", lambda conn, user_id, lang, summary: None
    )
    monkeypatch.setattr(
        user_data, "save_experience", lambda conn, user_id, lang, entries: None
    )
    monkeypatch.setattr(
        user_data, "save_skills", lambda conn, user_id, lang, entries: None
    )
    monkeypatch.setattr(
        user_data, "save_certifications", lambda conn, user_id, entries: None
    )
    monkeypatch.setattr(
        user_data, "save_education", lambda conn, user_id, lang, entries: None
    )
    monkeypatch.setattr(
        user_data, "delete_experience", lambda conn, user_id, exp_id: None
    )
    monkeypatch.setattr(
        user_data,
        "get_onboarding_state",
        lambda conn, user_id: {
            "is_complete": True,
            "profile_complete": True,
            "search_complete": True,
            "hf_token_complete": True,
        },
    )

    mock_conn = MagicMock()
    mock_conn.commit = MagicMock()
    mock_db = MagicMock()
    mock_db.conn = mock_conn
    dashboard_app.app.state.db = mock_db

    dashboard_app.app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-user",
        "email": "test@example.com",
    }
    yield TestClient(dashboard_app.app)
    dashboard_app.app.dependency_overrides.clear()


class TestProfilePage:
    def test_profile_page_loads(self, profile_client):
        r = profile_client.get("/profile")
        assert r.status_code == 200

    def test_profile_shows_name(self, profile_client):
        r = profile_client.get("/profile")
        assert "Test User" in r.text

    def test_profile_nav_link_present(self, profile_client):
        r = profile_client.get("/profile")
        assert "/profile" in r.text
        assert "Profil" in r.text

    def test_profile_page_shows_onboarding_banner_when_incomplete(
        self, profile_client, monkeypatch
    ) -> None:
        import app as dashboard_app

        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_onboarding_state",
            lambda conn, user_id: {
                "is_complete": False,
                "profile_complete": True,
                "search_complete": False,
                "hf_token_complete": False,
            },
        )
        r = profile_client.get("/profile")
        assert r.status_code == 200
        assert "Mots-clés de recherche" in r.text
        assert "Token Hugging Face" in r.text

    def test_profile_page_hides_onboarding_banner_when_complete(
        self, profile_client, monkeypatch
    ) -> None:
        import app as dashboard_app

        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_onboarding_state",
            lambda conn, user_id: {
                "is_complete": True,
                "profile_complete": True,
                "search_complete": True,
                "hf_token_complete": True,
            },
        )
        r = profile_client.get("/profile")
        assert r.status_code == 200
        assert "Pour démarrer" not in r.text


class TestSaveContact:
    def test_save_contact_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/contact",
            data={
                "name": "New Name",
                "title": "ML Eng",
                "email": "new@test.com",
                "phone": "+33 6 11 11 11 11",
                "location": "Lyon",
                "linkedin": "",
                "github": "github.com/new",
            },
        )
        assert r.status_code == 200

    def test_save_contact_response_contains_saved_flash(self, profile_client):
        r = profile_client.post(
            "/profile/contact",
            data={
                "name": "N",
                "title": "T",
                "email": "e@e.com",
                "phone": "",
                "location": "",
                "linkedin": "",
                "github": "",
            },
        )
        assert "Sauvegardé" in r.text


class TestSaveText:
    def test_save_text_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/text", data={"profile_md": "New summary text."}
        )
        assert r.status_code == 200

    def test_save_text_response_contains_flash(self, profile_client):
        r = profile_client.post(
            "/profile/text", data={"profile_md": "New summary text."}
        )
        assert "Sauvegardé" in r.text


class TestCvRoutes:
    def test_cv_meta_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/cv/meta", data={"lang": "fr", "summary": "A summary"}
        )
        assert r.status_code == 200
        assert "Sauvegardé" in r.text

    def test_cv_experience_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/cv/experience",
            data={"lang": "fr", "data": json.dumps([])},
        )
        assert r.status_code == 200

    def test_cv_experience_invalid_json(self, profile_client):
        r = profile_client.post(
            "/profile/cv/experience", data={"lang": "fr", "data": "bad"}
        )
        assert r.status_code == 200
        assert "invalide" in r.text

    def test_cv_skills_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/cv/skills", data={"lang": "fr", "data": json.dumps([])}
        )
        assert r.status_code == 200

    def test_cv_certifications_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/cv/certifications", data={"data": json.dumps([])}
        )
        assert r.status_code == 200

    def test_cv_education_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/cv/education", data={"lang": "fr", "data": json.dumps([])}
        )
        assert r.status_code == 200
