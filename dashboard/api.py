from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

import prepare_state
import scan_state
import user_data
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


@router.post("/scan/start")
async def start_scan_route(
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    scan_state.start_scan(current_user["sub"])
    return {"status": "running"}


@router.get("/scan/status")
async def get_scan_status_route(
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    return scan_state.get_scan_state(current_user["sub"])


@router.post("/offers/{offer_id}/prepare")
async def start_prepare_route(
    request: Request,
    offer_id: int,
    skip_prep: bool = Body(False, embed=True),
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if len(offer.get("description", "")) < prepare_state.MIN_OFFER_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "description_too_short",
                "message": (
                    "Description trop courte pour préparer la candidature. "
                    "Complète-la via les notes ou l'édition de l'offre avant "
                    "de réessayer."
                ),
            },
        )
    hf_token = user_data.get_hf_token(db.conn, user_id)
    if not hf_token:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "hf_token_missing",
                "message": (
                    "Ajoute ton token Hugging Face dans les paramètres avant "
                    "de préparer une candidature."
                ),
            },
        )
    prepare_state.start_prepare(offer_id, user_id, skip_prep)
    return {"status": "running"}


@router.get("/offers/{offer_id}/prepare/status")
async def get_prepare_status_route(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    if db.get_by_id(offer_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return prepare_state.get_prepare_state(offer_id)


def _download_offer_file(
    request: Request, offer_id: int, current_user: CurrentUser, field: str
) -> FileResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    path_str = offer.get(field, "")
    if not path_str:
        raise HTTPException(status_code=404, detail="File not generated yet")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/pdf",
        content_disposition_type="attachment",
    )


@router.get("/offers/{offer_id}/cv")
async def download_cv_route(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> FileResponse:
    return _download_offer_file(request, offer_id, current_user, "cv_path")


@router.get("/offers/{offer_id}/cover-letter")
async def download_cover_letter_route(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> FileResponse:
    return _download_offer_file(request, offer_id, current_user, "cover_letter_path")


@router.get("/offers/{offer_id}/prep-sheet")
async def download_prep_sheet_route(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> FileResponse:
    return _download_offer_file(request, offer_id, current_user, "prep_sheet_path")
