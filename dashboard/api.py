from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse, RedirectResponse

from auth import (
    CurrentUser,
    clear_auth_cookies,
    get_current_user_api,
    set_auth_cookies,
    validate_access_token,
)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_user_api),
) -> CurrentUser:
    return current_user


@router.post("/auth/session")
async def auth_session_create(
    access_token: str = Body(...),
    refresh_token: str = Body(...),
) -> JSONResponse:
    validate_access_token(access_token)
    response = JSONResponse({"ok": True})
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.delete("/auth/session")
async def auth_session_delete() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=302)
    clear_auth_cookies(response)
    return response
