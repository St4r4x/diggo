from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
import user_data

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
USER_A = "user-a-test"
USER_B = "user-b-test"

_CREATE_PROFILES = """
CREATE TEMP TABLE user_profiles (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    linkedin TEXT NOT NULL DEFAULT '',
    github TEXT NOT NULL DEFAULT '',
    profile_md TEXT NOT NULL DEFAULT ''
)
"""

_CREATE_SETTINGS = """
CREATE TEMP TABLE user_settings (
    user_id TEXT PRIMARY KEY,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    enabled_portals TEXT[] NOT NULL DEFAULT '{}',
    location TEXT NOT NULL DEFAULT '',
    contract TEXT NOT NULL DEFAULT 'CDI',
    experience_max_years INT NOT NULL DEFAULT 3,
    salary_min INT NOT NULL DEFAULT 0,
    salary_max INT NOT NULL DEFAULT 0,
    target_companies TEXT[] NOT NULL DEFAULT '{}',
    follow_up_days INT NOT NULL DEFAULT 7
)
"""

_CREATE_LLM_PROVIDERS = """
CREATE TEMP TABLE user_llm_providers (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key_encrypted BYTEA NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    UNIQUE (user_id, provider)
)
"""


@pytest.fixture
def conn(monkeypatch):
    c = psycopg2.connect(PG_URL)
    c.autocommit = False
    with c.cursor() as cur:
        cur.execute(_CREATE_PROFILES)
        cur.execute(_CREATE_SETTINGS)
        cur.execute(_CREATE_LLM_PROVIDERS)
    c.commit()
    monkeypatch.setattr(user_data, "_migrate_profile_from_files", lambda: None)
    monkeypatch.setattr(user_data, "_migrate_settings_from_files", lambda: None)
    yield c
    c.close()


def test_get_profile_empty_returns_defaults(conn):
    result = user_data.get_profile(conn, USER_A)
    assert result["name"] == ""
    assert result["profile_md"] == ""


def test_save_and_get_profile(conn):
    data = {
        "name": "Alice",
        "title": "ML Engineer",
        "email": "a@x.com",
        "phone": "",
        "location": "Paris",
        "linkedin": "",
        "github": "",
        "profile_md": "# Hello",
    }
    user_data.save_profile(conn, USER_A, data)
    conn.commit()
    result = user_data.get_profile(conn, USER_A)
    assert result["name"] == "Alice"
    assert result["profile_md"] == "# Hello"


def test_profile_isolated_per_user(conn):
    user_data.save_profile(
        conn,
        USER_A,
        {
            "name": "Alice",
            "title": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "profile_md": "",
        },
    )
    conn.commit()
    result_b = user_data.get_profile(conn, USER_B)
    assert result_b["name"] == ""


def test_get_settings_empty_returns_defaults(conn):
    result = user_data.get_settings(conn, USER_A)
    assert result["keywords"] == []
    assert result["follow_up_days"] == 7


def test_save_and_get_settings(conn):
    data = {
        "keywords": ["AI Engineer", "ML Engineer"],
        "enabled_portals": ["apec"],
        "location": "Paris",
        "contract": "CDI",
        "experience_max_years": 3,
        "salary_min": 40000,
        "salary_max": 60000,
        "target_companies": ["Mistral AI"],
        "follow_up_days": 7,
    }
    user_data.save_settings(conn, USER_A, data)
    conn.commit()
    result = user_data.get_settings(conn, USER_A)
    assert result["keywords"] == ["AI Engineer", "ML Engineer"]
    assert result["salary_min"] == 40000


def test_llm_providers_missing_returns_empty_list(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    assert user_data.get_llm_providers(conn, USER_A) == []


def test_llm_provider_key_missing_returns_none(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    assert user_data.get_llm_provider_key(conn, USER_A, "huggingface") is None


def test_save_and_get_llm_provider_roundtrip(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_secret123")
    conn.commit()
    assert user_data.get_llm_provider_key(conn, USER_A, "huggingface") == "hf_secret123"
    providers = user_data.get_llm_providers(conn, USER_A)
    assert providers == [{"provider": "huggingface", "sort_order": 0}]


def test_save_llm_provider_isolated_per_user(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_secret123")
    conn.commit()
    assert user_data.get_llm_provider_key(conn, USER_B, "huggingface") is None


def test_save_llm_provider_twice_overwrites_key(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_first")
    conn.commit()
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_second")
    conn.commit()
    assert user_data.get_llm_provider_key(conn, USER_A, "huggingface") == "hf_second"
    providers = user_data.get_llm_providers(conn, USER_A)
    assert len(providers) == 1


def test_save_second_llm_provider_appends_after_first(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_key")
    conn.commit()
    user_data.save_llm_provider(conn, USER_A, "groq", "groq_key")
    conn.commit()
    providers = user_data.get_llm_providers(conn, USER_A)
    assert providers == [
        {"provider": "huggingface", "sort_order": 0},
        {"provider": "groq", "sort_order": 1},
    ]


def test_delete_llm_provider_removes_it(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_secret123")
    conn.commit()
    user_data.delete_llm_provider(conn, USER_A, "huggingface")
    conn.commit()
    assert user_data.get_llm_providers(conn, USER_A) == []


def test_llm_provider_key_undecryptable_with_current_key_returns_none(
    conn, monkeypatch
):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_secret123")
    conn.commit()

    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    assert user_data.get_llm_provider_key(conn, USER_A, "huggingface") is None


def test_reorder_llm_providers_updates_sort_order(conn, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    user_data.save_llm_provider(conn, USER_A, "huggingface", "hf_key")
    user_data.save_llm_provider(conn, USER_A, "groq", "groq_key")
    conn.commit()

    user_data.reorder_llm_providers(conn, USER_A, ["groq", "huggingface"])
    conn.commit()

    providers = user_data.get_llm_providers(conn, USER_A)
    assert providers == [
        {"provider": "groq", "sort_order": 0},
        {"provider": "huggingface", "sort_order": 1},
    ]


_CREATE_ATS_TARGETS = """
CREATE TEMP TABLE user_ats_targets (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    careers_url TEXT NOT NULL
)
"""


@pytest.fixture
def conn_with_ats(monkeypatch):
    c = psycopg2.connect(PG_URL)
    c.autocommit = False
    with c.cursor() as cur:
        cur.execute(_CREATE_ATS_TARGETS)
    c.commit()
    monkeypatch.setattr(user_data, "_migrate_ats_from_files", lambda: None)
    yield c
    c.close()


def test_ats_targets_empty(conn_with_ats):
    result = user_data.get_ats_targets(conn_with_ats, USER_A)
    assert result == []


def test_add_and_get_ats_target(conn_with_ats):
    new_id = user_data.add_ats_target(
        conn_with_ats, USER_A, "Mistral AI", "https://jobs.lever.co/mistral"
    )
    conn_with_ats.commit()
    assert isinstance(new_id, int)
    targets = user_data.get_ats_targets(conn_with_ats, USER_A)
    assert len(targets) == 1
    assert targets[0]["name"] == "Mistral AI"
    assert targets[0]["id"] == new_id


def test_delete_ats_target(conn_with_ats):
    new_id = user_data.add_ats_target(
        conn_with_ats, USER_A, "Mistral AI", "https://jobs.lever.co/mistral"
    )
    conn_with_ats.commit()
    user_data.delete_ats_target(conn_with_ats, USER_A, new_id)
    conn_with_ats.commit()
    assert user_data.get_ats_targets(conn_with_ats, USER_A) == []


def test_delete_ats_target_wrong_user(conn_with_ats):
    new_id = user_data.add_ats_target(
        conn_with_ats, USER_A, "Mistral AI", "https://jobs.lever.co/mistral"
    )
    conn_with_ats.commit()
    user_data.delete_ats_target(conn_with_ats, USER_B, new_id)
    conn_with_ats.commit()
    # Should NOT delete — wrong user_id
    assert len(user_data.get_ats_targets(conn_with_ats, USER_A)) == 1


def test_ats_targets_isolated_per_user(conn_with_ats):
    user_data.add_ats_target(
        conn_with_ats, USER_A, "Mistral AI", "https://jobs.lever.co/mistral"
    )
    conn_with_ats.commit()
    assert user_data.get_ats_targets(conn_with_ats, USER_B) == []


_CREATE_CV_TABLES = """
CREATE TEMP TABLE user_cv_meta (
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, lang)
);
CREATE TEMP TABLE user_experience (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
);
CREATE TEMP TABLE user_experience_bullets (
    id SERIAL PRIMARY KEY,
    experience_id INT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
);
CREATE TEMP TABLE user_skills (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    category TEXT NOT NULL,
    skill TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
);
CREATE TEMP TABLE user_certifications (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    issuer TEXT NOT NULL DEFAULT '',
    year INT
);
CREATE TEMP TABLE user_education (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    degree TEXT NOT NULL DEFAULT '',
    school TEXT NOT NULL DEFAULT '',
    year INT
);
CREATE TEMP TABLE user_projects (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    stack TEXT[] NOT NULL DEFAULT '{}',
    "desc" TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
);
CREATE TEMP TABLE user_languages (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
);
CREATE TEMP TABLE user_hobbies (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
)
"""


@pytest.fixture
def conn_with_cv(monkeypatch):
    c = psycopg2.connect(PG_URL)
    c.autocommit = False
    with c.cursor() as cur:
        for stmt in _CREATE_CV_TABLES.split(";"):
            if stmt.strip():
                cur.execute(stmt)
    c.commit()
    monkeypatch.setattr(user_data, "_migrate_cv_from_files", lambda lang="fr": None)
    yield c
    c.close()


def test_get_cv_empty(conn_with_cv):
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["meta"]["summary"] == ""
    assert cv["experience"] == []
    assert cv["skills"] == []
    assert cv["certifications"] == []
    assert cv["education"] == []
    assert cv["projects"] == []
    assert cv["languages"] == []
    assert cv["hobbies"] == []


def test_save_and_get_cv_meta(conn_with_cv):
    user_data.save_cv_meta(
        conn_with_cv, USER_A, "fr", "AI Engineer with 3 years experience"
    )
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["meta"]["summary"] == "AI Engineer with 3 years experience"


def test_save_experience_with_bullets(conn_with_cv):
    entries = [
        {
            "title": "ML Engineer",
            "company": "Missia",
            "type": "Alternance",
            "period": "2024-2026",
            "sort_order": 0,
            "bullets": ["Built CV pipeline", "Deployed on edge"],
        }
    ]
    user_data.save_experience(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert len(cv["experience"]) == 1
    assert cv["experience"][0]["title"] == "ML Engineer"
    assert cv["experience"][0]["bullets"] == ["Built CV pipeline", "Deployed on edge"]


def test_save_experience_replaces_existing(conn_with_cv):
    user_data.save_experience(
        conn_with_cv,
        USER_A,
        "fr",
        [
            {
                "title": "Old",
                "company": "",
                "type": "",
                "period": "",
                "sort_order": 0,
                "bullets": [],
            }
        ],
    )
    user_data.save_experience(
        conn_with_cv,
        USER_A,
        "fr",
        [
            {
                "title": "New",
                "company": "",
                "type": "",
                "period": "",
                "sort_order": 0,
                "bullets": [],
            }
        ],
    )
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert len(cv["experience"]) == 1
    assert cv["experience"][0]["title"] == "New"


def test_save_skills(conn_with_cv):
    entries = [
        {"category": "IA/ML", "skill": "PyTorch", "sort_order": 0},
        {"category": "IA/ML", "skill": "HuggingFace", "sort_order": 1},
    ]
    user_data.save_skills(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert len(cv["skills"]) == 2
    assert cv["skills"][0]["skill"] == "PyTorch"


def test_save_certifications(conn_with_cv):
    entries = [{"name": "GCP ML Engineer", "issuer": "Google", "year": 2025}]
    user_data.save_certifications(conn_with_cv, USER_A, entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["certifications"][0]["name"] == "GCP ML Engineer"


def test_save_education(conn_with_cv):
    entries = [{"degree": "MSc AI", "school": "EPITA", "year": 2026}]
    user_data.save_education(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["education"][0]["degree"] == "MSc AI"


def test_save_projects(conn_with_cv):
    entries = [
        {
            "name": "Kaggle Watson",
            "stack": ["PyTorch", "DeBERTa-v3"],
            "desc": "Multilingual NLI",
            "sort_order": 0,
        }
    ]
    user_data.save_projects(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["projects"][0]["name"] == "Kaggle Watson"
    assert cv["projects"][0]["stack"] == ["PyTorch", "DeBERTa-v3"]
    assert cv["projects"][0]["desc"] == "Multilingual NLI"


def test_save_projects_replaces_existing(conn_with_cv):
    user_data.save_projects(
        conn_with_cv, USER_A, "fr", [{"name": "Old", "stack": [], "desc": ""}]
    )
    user_data.save_projects(
        conn_with_cv, USER_A, "fr", [{"name": "New", "stack": [], "desc": ""}]
    )
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert len(cv["projects"]) == 1
    assert cv["projects"][0]["name"] == "New"


def test_save_languages(conn_with_cv):
    entries = [
        {"name": "Français (natif)", "sort_order": 0},
        {"name": "Anglais (professionnel)", "sort_order": 1},
    ]
    user_data.save_languages(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert [lang["name"] for lang in cv["languages"]] == [
        "Français (natif)",
        "Anglais (professionnel)",
    ]


def test_save_hobbies(conn_with_cv):
    entries = [{"name": "Tennis", "sort_order": 0}]
    user_data.save_hobbies(conn_with_cv, USER_A, "fr", entries)
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["hobbies"][0]["name"] == "Tennis"


def test_migrate_cv_from_files_includes_projects_languages_hobbies(
    conn_with_cv, monkeypatch
):
    monkeypatch.setattr(
        user_data,
        "_migrate_cv_from_files",
        lambda lang="fr": {
            "summary": "",
            "experience": [],
            "skills": [],
            "certifications": [],
            "education": [],
            "projects": [
                {"name": "Proj", "stack": ["Python"], "desc": "d", "sort_order": 0}
            ],
            "languages": [{"name": "Français", "sort_order": 0}],
            "hobbies": [{"name": "Cinéma", "sort_order": 0}],
        },
    )
    cv = user_data.get_cv(conn_with_cv, USER_A, lang="fr")
    assert cv["projects"][0]["name"] == "Proj"
    assert cv["languages"][0]["name"] == "Français"
    assert cv["hobbies"][0]["name"] == "Cinéma"


_CREATE_ONBOARDING_TABLES = (
    _CREATE_PROFILES
    + ";"
    + _CREATE_SETTINGS
    + ";"
    + _CREATE_LLM_PROVIDERS
    + ";"
    + _CREATE_CV_TABLES
)


@pytest.fixture
def conn_onboarding(monkeypatch):
    c = psycopg2.connect(PG_URL)
    c.autocommit = False
    with c.cursor() as cur:
        for stmt in _CREATE_ONBOARDING_TABLES.split(";"):
            if stmt.strip():
                cur.execute(stmt)
    c.commit()
    monkeypatch.setattr(user_data, "_migrate_profile_from_files", lambda: None)
    monkeypatch.setattr(user_data, "_migrate_settings_from_files", lambda: None)
    monkeypatch.setattr(user_data, "_migrate_cv_from_files", lambda lang="fr": None)
    monkeypatch.setenv("SECRET_KEY", Fernet.generate_key().decode())
    yield c
    c.close()


def test_onboarding_state_all_incomplete_by_default(conn_onboarding):
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["profile_complete"] is False
    assert state["search_complete"] is False
    assert state["llm_provider_complete"] is False
    assert state["is_complete"] is False


def test_onboarding_state_profile_complete_requires_name_email_summary_experience_skill(
    conn_onboarding,
):
    user_data.save_profile(
        conn_onboarding,
        USER_A,
        {
            "name": "Alice",
            "title": "",
            "email": "a@x.com",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "profile_md": "",
        },
    )
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["profile_complete"] is False  # no summary/experience/skill yet

    user_data.save_cv_meta(conn_onboarding, USER_A, "fr", "Summary text")
    user_data.save_experience(
        conn_onboarding,
        USER_A,
        "fr",
        [
            {
                "title": "Dev",
                "company": "Acme",
                "type": "CDI",
                "period": "2024",
                "bullets": [],
            }
        ],
    )
    user_data.save_skills(
        conn_onboarding, USER_A, "fr", [{"category": "Langages", "skill": "Python"}]
    )
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["profile_complete"] is True


def test_onboarding_state_search_complete_requires_keywords(conn_onboarding):
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["search_complete"] is False

    user_data.save_settings(
        conn_onboarding,
        USER_A,
        {
            "keywords": ["AI Engineer"],
            "enabled_portals": [],
            "location": "",
            "contract": "CDI",
            "experience_max_years": 3,
            "salary_min": 0,
            "salary_max": 0,
            "target_companies": [],
            "follow_up_days": 7,
        },
    )
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["search_complete"] is True


def test_onboarding_state_llm_provider_complete_requires_saved_provider(
    conn_onboarding,
):
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["llm_provider_complete"] is False

    user_data.save_llm_provider(conn_onboarding, USER_A, "huggingface", "hf_secret123")
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["llm_provider_complete"] is True


def test_onboarding_state_is_complete_requires_all_three(conn_onboarding):
    user_data.save_profile(
        conn_onboarding,
        USER_A,
        {
            "name": "Alice",
            "title": "",
            "email": "a@x.com",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "profile_md": "",
        },
    )
    user_data.save_cv_meta(conn_onboarding, USER_A, "fr", "Summary text")
    user_data.save_experience(
        conn_onboarding,
        USER_A,
        "fr",
        [
            {
                "title": "Dev",
                "company": "Acme",
                "type": "CDI",
                "period": "2024",
                "bullets": [],
            }
        ],
    )
    user_data.save_skills(
        conn_onboarding, USER_A, "fr", [{"category": "Langages", "skill": "Python"}]
    )
    user_data.save_settings(
        conn_onboarding,
        USER_A,
        {
            "keywords": ["AI Engineer"],
            "enabled_portals": [],
            "location": "",
            "contract": "CDI",
            "experience_max_years": 3,
            "salary_min": 0,
            "salary_max": 0,
            "target_companies": [],
            "follow_up_days": 7,
        },
    )
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["is_complete"] is False  # LLM provider still missing

    user_data.save_llm_provider(conn_onboarding, USER_A, "huggingface", "hf_secret123")
    conn_onboarding.commit()
    state = user_data.get_onboarding_state(conn_onboarding, USER_A)
    assert state["is_complete"] is True
