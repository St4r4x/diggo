from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import CurrentUser, get_current_user_api

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_user_api),
) -> CurrentUser:
    return current_user
