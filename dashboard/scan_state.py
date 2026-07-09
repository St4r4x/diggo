from __future__ import annotations

# In-process memory only: _status/_result are plain dicts, lost on restart
# and not shared across replicas. Restarting the `api` container is the
# documented way to kill a running scan (see docs/frontend-migration-status.md).
import asyncio
from typing import Any

_EMPTY_RESULT: dict[str, Any] = {
    "inserted": 0,
    "skipped": 0,
    "found": 0,
    "scored": 0,
    "abandoned": 0,
    "error": "",
}

_status: dict[str, str] = {}
_result: dict[str, dict[str, Any]] = {}


def get_scan_state(user_id: str) -> dict[str, Any]:
    return {
        "status": _status.get(user_id, "idle"),
        "result": _result.get(user_id, _EMPTY_RESULT),
    }


async def _run_scan(user_id: str) -> None:
    try:
        from scripts.import_offers import (
            _run_pipeline,
            expire_stale_offers,
            import_offers,
        )
        from scripts.pre_filter import load_settings

        settings = load_settings(user_id=user_id)
        _result[user_id] = dict(_EMPTY_RESULT)

        offers = await _run_pipeline(settings, user_id=user_id)
        _result[user_id]["found"] = len(offers)
        _result[user_id]["scored"] = len(offers)

        inserted, skipped = import_offers(offers, user_id=user_id)
        abandoned = expire_stale_offers(user_id=user_id)

        _result[user_id] = {
            "inserted": inserted,
            "skipped": skipped,
            "found": len(offers),
            "scored": len(offers),
            "abandoned": abandoned,
            "error": "",
        }
        _status[user_id] = "done"
    except Exception as exc:
        _result[user_id] = {**_EMPTY_RESULT, "error": str(exc).splitlines()[0]}
        _status[user_id] = "error"


def start_scan(user_id: str) -> None:
    """Set state to running and enqueue the scan task for this user.
    No-op if a scan is already running for this user."""
    if _status.get(user_id) == "running":
        return
    _status[user_id] = "running"
    _result[user_id] = dict(_EMPTY_RESULT)
    asyncio.create_task(_run_scan(user_id))
