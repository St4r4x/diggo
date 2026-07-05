from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import pytest

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
    portal_queries TEXT[] NOT NULL DEFAULT '{}',
    location TEXT NOT NULL DEFAULT '',
    contract TEXT NOT NULL DEFAULT 'CDI',
    experience_max_years INT NOT NULL DEFAULT 3,
    salary_min INT NOT NULL DEFAULT 0,
    salary_max INT NOT NULL DEFAULT 0,
    target_companies TEXT[] NOT NULL DEFAULT '{}',
    follow_up_days INT NOT NULL DEFAULT 7
)
"""


@pytest.fixture
def conn(monkeypatch):
    c = psycopg2.connect(PG_URL)
    c.autocommit = False
    with c.cursor() as cur:
        cur.execute(_CREATE_PROFILES)
        cur.execute(_CREATE_SETTINGS)
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
    result_b = user_data.get_profile(conn, USER_B)
    assert result_b["name"] == ""


def test_get_settings_empty_returns_defaults(conn):
    result = user_data.get_settings(conn, USER_A)
    assert result["keywords"] == []
    assert result["follow_up_days"] == 7


def test_save_and_get_settings(conn):
    data = {
        "keywords": ["AI Engineer", "ML Engineer"],
        "portal_queries": ["AI"],
        "location": "Paris",
        "contract": "CDI",
        "experience_max_years": 3,
        "salary_min": 40000,
        "salary_max": 60000,
        "target_companies": ["Mistral AI"],
        "follow_up_days": 7,
    }
    user_data.save_settings(conn, USER_A, data)
    result = user_data.get_settings(conn, USER_A)
    assert result["keywords"] == ["AI Engineer", "ML Engineer"]
    assert result["salary_min"] == 40000
