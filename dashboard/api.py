from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from auth import (
    CurrentUser,
    clear_auth_cookies,
    get_current_user_api,
    require_onboarding_complete_api,
    set_auth_cookies,
    validate_access_token,
)
from db import VALID_STATUSES, parse_description

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


@router.get("/offers")
async def list_offers(
    request: Request,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
    status: str = Query(""),
    grade: str = Query(""),
    q: str = Query(""),
    sal_min: str = Query(""),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    filters = {
        k: v
        for k, v in {
            "status": status,
            "grade": grade,
            "q": q,
            "sal_min": sal_min,
        }.items()
        if v
    }
    offers = db.get_all(filters, user_id=user_id)
    followup_ids = [f["id"] for f in db.get_followups(user_id=user_id)]
    return {"offers": offers, "followup_ids": followup_ids, "statuses": VALID_STATUSES}


@router.get("/offers/{offer_id}")
async def get_offer(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {
        "offer": offer,
        "description": parse_description(offer.get("description", "")),
    }


@router.patch("/offers/{offer_id}")
async def update_offer(
    request: Request,
    offer_id: int,
    fields: dict = Body(...),
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    if "status" in fields and fields["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail={"error": "invalid_status"})
    db = request.app.state.db
    user_id = current_user["sub"]
    if db.get_by_id(offer_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = db.update(offer_id, fields, user_id=user_id)
    return {
        "offer": offer,
        "description": parse_description(offer.get("description", "")),
    }


@router.delete("/offers/{offer_id}")
async def delete_offer(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    if db.get_by_id(offer_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    db.delete(offer_id, user_id=user_id)
    return {"ok": True}
