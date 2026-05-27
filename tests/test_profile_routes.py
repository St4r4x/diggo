import sys
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

SAMPLE_CONTACT_YAML = textwrap.dedent("""\
    name: Test User
    title: AI Engineer
    email: test@example.com
    phone: "+33 6 00 00 00 00"
    location: Paris
    linkedin: ""
    github: github.com/testuser
""")

SAMPLE_PROFILE_MD = textwrap.dedent("""\
    # Profile — Test User

    ## Contact
    - Email: test@example.com
    - Phone: +33 6 00 00 00 00
    - Location: Paris
    - LinkedIn:
    - GitHub: github.com/testuser

    ## Summary
    An experienced engineer.

    ## Experience

    ### ML Engineer — Acme Corp (CDI, January 2024 – Present)
    - Built a pipeline

    ## Education
    - **MSc AI** — Great School (2022–2024)

    ## Certifications & Training
    - AWS ML

    ## Skills

    ### Machine Learning
    - PyTorch

    ## Personal Projects

    - **cool-project**: A cool project
""")


@pytest.fixture
def profile_files(tmp_path):
    contact_file = tmp_path / "contact.yaml"
    profile_file = tmp_path / "profile.md"
    contact_file.write_text(SAMPLE_CONTACT_YAML, encoding="utf-8")
    profile_file.write_text(SAMPLE_PROFILE_MD, encoding="utf-8")
    return contact_file, profile_file


@pytest.fixture
def profile_client(profile_files, monkeypatch):
    import profile_parser as parser_mod
    import sqlite3
    import app as dashboard_app
    from db import DB

    contact_file, profile_file = profile_files
    monkeypatch.setattr(parser_mod, "_CONTACT_YAML", contact_file)
    monkeypatch.setattr(parser_mod, "_PROFILE_MD", profile_file)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL,
        role TEXT NOT NULL, offer_url TEXT NOT NULL DEFAULT '',
        detection_date TEXT NOT NULL, score_grade TEXT NOT NULL DEFAULT '',
        score_value REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'À envoyer',
        send_date TEXT, contacts TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '', cv_path TEXT NOT NULL DEFAULT '',
        cover_letter_path TEXT NOT NULL DEFAULT '', follow_up_date TEXT,
        description TEXT NOT NULL DEFAULT '')""")
    conn.commit()
    dashboard_app.app.state.db = DB(conn)
    return TestClient(dashboard_app.app)


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

    def test_save_contact_persists_to_yaml(self, profile_client, profile_files):
        contact_file, _ = profile_files
        profile_client.post(
            "/profile/contact",
            data={
                "name": "Updated",
                "title": "Eng",
                "email": "u@test.com",
                "phone": "",
                "location": "",
                "linkedin": "",
                "github": "",
            },
        )
        import yaml

        saved = yaml.safe_load(contact_file.read_text())
        assert saved["name"] == "Updated"

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


class TestSaveSummary:
    def test_save_summary_returns_200(self, profile_client):
        r = profile_client.post(
            "/profile/summary", data={"summary": "New summary text."}
        )
        assert r.status_code == 200

    def test_save_summary_response_contains_flash(self, profile_client):
        r = profile_client.post(
            "/profile/summary", data={"summary": "New summary text."}
        )
        assert "Sauvegardé" in r.text


class TestSaveExperience:
    def test_save_experience_returns_200(self, profile_client):
        import json

        payload = json.dumps(
            [
                {
                    "title": "SWE",
                    "company": "Acme",
                    "type": "CDI",
                    "period": "2024 – Present",
                    "bullets": ["Built things"],
                }
            ]
        )
        r = profile_client.post("/profile/experience", data={"data": payload})
        assert r.status_code == 200

    def test_save_experience_response_contains_flash(self, profile_client):
        import json

        r = profile_client.post("/profile/experience", data={"data": json.dumps([])})
        assert "Sauvegardé" in r.text

    def test_save_experience_persists(self, profile_client, profile_files):
        import json

        _, profile_file = profile_files
        payload = json.dumps(
            [
                {
                    "title": "SWE",
                    "company": "Acme",
                    "type": "CDI",
                    "period": "2024 – Present",
                    "bullets": ["Built things"],
                }
            ]
        )
        profile_client.post("/profile/experience", data={"data": payload})
        text = profile_file.read_text(encoding="utf-8")
        assert "SWE" in text
        assert "Acme" in text


class TestSaveSkills:
    def test_save_skills_returns_200(self, profile_client):
        import json

        payload = json.dumps({"Machine Learning": ["PyTorch", "Scikit-learn"]})
        r = profile_client.post("/profile/skills", data={"data": payload})
        assert r.status_code == 200

    def test_save_skills_response_contains_flash(self, profile_client):
        import json

        r = profile_client.post("/profile/skills", data={"data": json.dumps({})})
        assert "Sauvegardé" in r.text

    def test_save_skills_persists(self, profile_client, profile_files):
        import json

        _, profile_file = profile_files
        payload = json.dumps({"Deep Learning": ["PyTorch", "TensorFlow"]})
        profile_client.post("/profile/skills", data={"data": payload})
        text = profile_file.read_text(encoding="utf-8")
        assert "Deep Learning" in text
        assert "PyTorch" in text


class TestSaveEducation:
    def test_save_education_returns_200(self, profile_client):
        import json

        payload = json.dumps(
            {
                "education": [
                    {"degree": "MSc", "school": "School", "period": "2022–2024"}
                ],
                "certifications": ["AWS ML"],
            }
        )
        r = profile_client.post("/profile/education", data={"data": payload})
        assert r.status_code == 200

    def test_save_education_response_contains_flash(self, profile_client):
        import json

        r = profile_client.post(
            "/profile/education",
            data={"data": json.dumps({"education": [], "certifications": []})},
        )
        assert "Sauvegardé" in r.text

    def test_save_education_persists(self, profile_client, profile_files):
        import json

        _, profile_file = profile_files
        payload = json.dumps(
            {
                "education": [
                    {"degree": "PhD AI", "school": "ENS", "period": "2025–2028"}
                ],
                "certifications": ["GCP ML Engineer"],
            }
        )
        profile_client.post("/profile/education", data={"data": payload})
        text = profile_file.read_text(encoding="utf-8")
        assert "PhD AI" in text
        assert "GCP ML Engineer" in text


class TestSaveProjects:
    def test_save_projects_returns_200(self, profile_client):
        import json

        payload = json.dumps([{"name": "my-proj", "description": "A project"}])
        r = profile_client.post("/profile/projects", data={"data": payload})
        assert r.status_code == 200

    def test_save_projects_response_contains_flash(self, profile_client):
        import json

        r = profile_client.post("/profile/projects", data={"data": json.dumps([])})
        assert "Sauvegardé" in r.text

    def test_save_projects_persists(self, profile_client, profile_files):
        import json

        _, profile_file = profile_files
        payload = json.dumps(
            [{"name": "awesome-tool", "description": "Does great things"}]
        )
        profile_client.post("/profile/projects", data={"data": payload})
        text = profile_file.read_text(encoding="utf-8")
        assert "awesome-tool" in text
        assert "Does great things" in text
