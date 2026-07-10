from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

PG_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)

_CREATE_OLD_SETTINGS = """
CREATE TEMP TABLE user_settings (
    user_id TEXT PRIMARY KEY,
    hf_token_encrypted BYTEA
)
"""

_CREATE_PROVIDERS = """
CREATE TEMP TABLE user_llm_providers (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key_encrypted BYTEA NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
)
"""

_UPGRADE_BACKFILL_SQL = (
    "INSERT INTO user_llm_providers (user_id, provider, api_key_encrypted, sort_order) "
    "SELECT user_id, 'huggingface', hf_token_encrypted, 0 "
    "FROM user_settings WHERE hf_token_encrypted IS NOT NULL"
)


def test_backfill_copies_hf_token_ciphertext_as_is():
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_OLD_SETTINGS)
        cur.execute(_CREATE_PROVIDERS)
        cur.execute(
            "INSERT INTO user_settings (user_id, hf_token_encrypted) VALUES (%s, %s)",
            ("user-a", psycopg2.Binary(b"fake-ciphertext-bytes")),
        )
        cur.execute(
            "INSERT INTO user_settings (user_id, hf_token_encrypted) VALUES (%s, %s)",
            ("user-b", None),
        )
        cur.execute(_UPGRADE_BACKFILL_SQL)
        cur.execute(
            "SELECT user_id, provider, api_key_encrypted, sort_order FROM user_llm_providers"
        )
        rows = cur.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "user-a"
    assert rows[0][1] == "huggingface"
    assert bytes(rows[0][2]) == b"fake-ciphertext-bytes"
    assert rows[0][3] == 0


def test_backfill_skips_users_with_no_token():
    conn = psycopg2.connect(PG_URL)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(_CREATE_OLD_SETTINGS)
        cur.execute(_CREATE_PROVIDERS)
        cur.execute(
            "INSERT INTO user_settings (user_id, hf_token_encrypted) VALUES (%s, %s)",
            ("user-no-token", None),
        )
        cur.execute(_UPGRADE_BACKFILL_SQL)
        cur.execute("SELECT count(*) FROM user_llm_providers")
        count = cur.fetchone()[0]
    conn.close()

    assert count == 0
