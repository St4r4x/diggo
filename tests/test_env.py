import os
from pathlib import Path
import sys

import pytest


def test_app_loads_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://test:test@localhost/test\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
    from env import load_env

    load_env(env_file)
    assert os.getenv("DATABASE_URL") == "postgresql://test:test@localhost/test"
