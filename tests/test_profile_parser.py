import sys
import textwrap
from pathlib import Path

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


def test_load_contact_from_yaml(tmp_config):
    data = parser_mod.load_profile()
    assert data["contact"]["name"] == "Test User"
    assert data["contact"]["email"] == "test@example.com"
    assert data["contact"]["github"] == "github.com/testuser"


def test_load_summary(tmp_config):
    data = parser_mod.load_profile()
    assert "experienced engineer" in data["summary"]


def test_load_experience_entries(tmp_config):
    data = parser_mod.load_profile()
    assert len(data["experience"]) == 1
    exp = data["experience"][0]
    assert exp["title"] == "ML Engineer"
    assert exp["company"] == "Acme Corp"
    assert exp["type"] == "CDI"
    assert exp["period"] == "January 2024 – Present"
    assert len(exp["bullets"]) == 2


def test_load_skills_categories(tmp_config):
    data = parser_mod.load_profile()
    assert "Machine Learning" in data["skills"]
    assert "PyTorch" in data["skills"]["Machine Learning"]
    assert "MLOps" in data["skills"]
    assert "Docker" in data["skills"]["MLOps"]


def test_load_education_and_certs(tmp_config):
    data = parser_mod.load_profile()
    assert len(data["education"]) == 1
    assert data["education"][0]["degree"] == "Master of Science"
    assert data["education"][0]["school"] == "Great School"
    assert "AWS Certified ML Specialty" in data["certifications"]


def test_load_projects(tmp_config):
    data = parser_mod.load_profile()
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "cool-project"
    assert "very cool" in data["projects"][0]["description"]


def test_roundtrip(tmp_config):
    original = parser_mod.load_profile()
    parser_mod.save_profile(original)
    reloaded = parser_mod.load_profile()
    assert reloaded["contact"] == original["contact"]
    assert reloaded["summary"] == original["summary"]
    assert len(reloaded["experience"]) == len(original["experience"])
    assert reloaded["skills"] == original["skills"]
    assert reloaded["education"] == original["education"]
    assert reloaded["certifications"] == original["certifications"]
    assert reloaded["projects"] == original["projects"]


def test_missing_files_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(parser_mod, "_CONTACT_YAML", tmp_path / "contact.yaml")
    monkeypatch.setattr(parser_mod, "_PROFILE_MD", tmp_path / "profile.md")
    data = parser_mod.load_profile()
    assert data["contact"]["name"] == ""
    assert data["summary"] == ""
    assert data["experience"] == []
    assert data["skills"] == {}
