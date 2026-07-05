import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
import profile_parser as parser_mod

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
    An experienced engineer with production ML background.

    ## Experience

    ### ML Engineer — Acme Corp (CDI, January 2024 – Present)
    - Built real-time inference pipeline
    - Deployed model to edge device

    ## Education
    - **Master of Science** — Great School (2022–2024)

    ## Certifications & Training
    - AWS Certified ML Specialty

    ## Skills

    ### Machine Learning
    - PyTorch
    - Scikit-learn

    ### MLOps
    - Docker
    - GitHub Actions

    ## Personal Projects

    - **cool-project**: A very cool project with many features
""")


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch):
    contact_file = tmp_path / "contact.yaml"
    profile_file = tmp_path / "profile.md"
    contact_file.write_text(SAMPLE_CONTACT_YAML, encoding="utf-8")
    profile_file.write_text(SAMPLE_PROFILE_MD, encoding="utf-8")
    monkeypatch.setattr(parser_mod, "_CONTACT_YAML", contact_file)
    monkeypatch.setattr(parser_mod, "_PROFILE_MD", profile_file)
    return tmp_path


# --- file-based helper tests (used by user_data migration path) ---


def test_parse_contact_from_yaml(tmp_config):
    data = parser_mod._parse_contact(parser_mod._CONTACT_YAML)
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"
    assert data["github"] == "github.com/testuser"


def test_parse_profile_md_summary(tmp_config):
    data = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert "experienced engineer" in data["summary"]


def test_parse_profile_md_experience(tmp_config):
    data = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert len(data["experience"]) == 1
    exp = data["experience"][0]
    assert exp["title"] == "ML Engineer"
    assert exp["company"] == "Acme Corp"
    assert exp["type"] == "CDI"
    assert exp["period"] == "January 2024 – Present"
    assert len(exp["bullets"]) == 2


def test_parse_profile_md_skills(tmp_config):
    data = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert "Machine Learning" in data["skills"]
    assert "PyTorch" in data["skills"]["Machine Learning"]
    assert "MLOps" in data["skills"]
    assert "Docker" in data["skills"]["MLOps"]


def test_parse_profile_md_education_and_certs(tmp_config):
    data = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert len(data["education"]) == 1
    assert data["education"][0]["degree"] == "Master of Science"
    assert data["education"][0]["school"] == "Great School"
    assert "AWS Certified ML Specialty" in data["certifications"]


def test_parse_profile_md_projects(tmp_config):
    data = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "cool-project"
    assert "very cool" in data["projects"][0]["description"]


def test_missing_files_return_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(parser_mod, "_CONTACT_YAML", tmp_path / "contact.yaml")
    monkeypatch.setattr(parser_mod, "_PROFILE_MD", tmp_path / "profile.md")
    contact = parser_mod._parse_contact(parser_mod._CONTACT_YAML)
    md = parser_mod._parse_profile_md(parser_mod._PROFILE_MD)
    assert contact["name"] == ""
    assert md["summary"] == ""
    assert md["experience"] == []
    assert md["skills"] == {}


# --- DB-backed load/save tests ---


def test_load_profile_db(monkeypatch):
    import user_data

    fake_profile = {
        "name": "DB User",
        "title": "Dev",
        "email": "db@test.com",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "profile_md": "some md",
    }
    monkeypatch.setattr(user_data, "get_profile", lambda conn, uid: fake_profile)
    conn = MagicMock()
    result = parser_mod.load_profile(conn, "uid-1")
    assert result["contact"]["name"] == "DB User"
    assert result["profile_md"] == "some md"
    assert result["experience"] == []  # compat shim


def test_save_profile_db(monkeypatch):
    import user_data

    saved = {}

    def fake_save(conn, uid, data):
        saved.update(data)

    monkeypatch.setattr(user_data, "save_profile", fake_save)
    conn = MagicMock()
    parser_mod.save_profile(
        conn,
        "uid-1",
        {
            "contact": {
                "name": "Updated",
                "title": "",
                "email": "",
                "phone": "",
                "location": "",
                "linkedin": "",
                "github": "",
            },
            "profile_md": "md",
        },
    )
    assert saved["name"] == "Updated"
    assert saved["profile_md"] == "md"
