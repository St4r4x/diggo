from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import mistune

import llm
import prepare_state
import profile_parser
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
from db import VALID_STATUSES, build_funnel, parse_description
from scripts.scan_portals import list_portals_meta

REPORTS_DIR = Path(__file__).parent.parent / "reports"

router = APIRouter(prefix="/api")

_KNOWN_LLM_PROVIDERS = {"huggingface", "ollama_cloud", "openai", "anthropic", "groq"}


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
    provider_names = [
        p["provider"] for p in user_data.get_llm_providers(db.conn, user_id)
    ]
    providers_configured = [
        name
        for name in provider_names
        if user_data.get_llm_provider_key(db.conn, user_id, name) is not None
    ]
    if not providers_configured:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "hf_token_missing",
                "message": (
                    "Ajoute au moins un fournisseur LLM dans les paramètres avant "
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


@router.get("/stats")
async def get_stats_route(
    request: Request,
    current_user: CurrentUser = Depends(require_onboarding_complete_api),
) -> dict:
    db = request.app.state.db
    user_id = current_user["sub"]
    stats = db.get_stats(user_id=user_id)
    funnel, exits, max_count = build_funnel(stats["by_status"])
    report_files = list(REPORTS_DIR.glob("daily-*.md")) if REPORTS_DIR.is_dir() else []
    latest_report_html: str | None = None
    latest_report_date: str | None = None
    if report_files:
        latest = max(report_files, key=lambda p: p.name)
        latest_report_date = latest.stem.replace("daily-", "")
        latest_report_html = mistune.html(latest.read_text(encoding="utf-8"))
    return {
        "stats": stats,
        "funnel": funnel,
        "exits": exits,
        "max_count": max_count,
        "latest_report_html": latest_report_html,
        "latest_report_date": latest_report_date,
    }


@router.get("/profile")
async def get_profile_route(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    profile = profile_parser.load_profile(conn, user_id)
    cv = user_data.get_cv(conn, user_id, lang="fr")
    cv_en = user_data.get_cv(conn, user_id, lang="en")
    onboarding = user_data.get_onboarding_state(conn, user_id)
    return {
        "profile": {
            "contact": profile["contact"],
            "profile_md": profile["profile_md"],
        },
        "cv": cv,
        "cv_en": cv_en,
        "onboarding": onboarding,
    }


@router.patch("/profile/contact")
async def update_profile_contact(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    contact: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    existing = profile_parser.load_profile(conn, user_id)
    existing["contact"] = {
        "name": contact.get("name", ""),
        "title": contact.get("title", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "location": contact.get("location", ""),
        "linkedin": contact.get("linkedin", ""),
        "github": contact.get("github", ""),
    }
    profile_parser.save_profile(conn, user_id, existing)
    conn.commit()
    return {"ok": True}


@router.patch("/profile/text")
async def update_profile_text(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    body: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    existing = profile_parser.load_profile(conn, user_id)
    existing["profile_md"] = body.get("profile_md", "")
    profile_parser.save_profile(conn, user_id, existing)
    conn.commit()
    return {"ok": True}


def _lang_query(lang: str = Query("fr")) -> str:
    """Normalize the ?lang= query param, matching the old Jinja2 routes' fallback."""
    return lang if lang in ("fr", "en") else "fr"


@router.put("/profile/cv/meta")
async def update_profile_cv_meta(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    body: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_cv_meta(conn, user_id, lang, body.get("summary", ""))
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/experience")
async def update_profile_cv_experience(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_experience(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.delete("/profile/cv/experience/{exp_id}")
async def delete_profile_cv_experience(
    request: Request,
    exp_id: int,
    current_user: CurrentUser = Depends(get_current_user_api),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_experience(conn, user_id, exp_id)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/skills")
async def update_profile_cv_skills(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_skills(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/certifications")
async def update_profile_cv_certifications(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_certifications(conn, user_id, entries)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/education")
async def update_profile_cv_education(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_education(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/projects")
async def update_profile_cv_projects(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_projects(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/languages")
async def update_profile_cv_languages(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_languages(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.put("/profile/cv/hobbies")
async def update_profile_cv_hobbies(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    lang: str = Depends(_lang_query),
    entries: list = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_hobbies(conn, user_id, lang, entries)
    conn.commit()
    return {"ok": True}


@router.get("/settings")
async def get_settings_route(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    settings = user_data.get_settings(conn, user_id)
    ats_targets = user_data.get_ats_targets(conn, user_id)
    llm_providers = user_data.get_llm_providers(conn, user_id)
    onboarding = user_data.get_onboarding_state(conn, user_id)
    return {
        "settings": settings,
        "ats_targets": ats_targets,
        "llm_providers": llm_providers,
        "onboarding": onboarding,
        "available_portals": list_portals_meta(),
    }


@router.put("/settings/search")
async def update_settings_search(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    data: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_settings(conn, user_id, data)
    conn.commit()
    return {"ok": True}


@router.post("/settings/ats")
async def add_settings_ats(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    body: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.add_ats_target(
        conn, user_id, body.get("name", ""), body.get("careers_url", "")
    )
    conn.commit()
    ats_targets = user_data.get_ats_targets(conn, user_id)
    return {"ats_targets": ats_targets}


@router.delete("/settings/ats/{target_id}")
async def delete_settings_ats(
    request: Request,
    target_id: int,
    current_user: CurrentUser = Depends(get_current_user_api),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_ats_target(conn, user_id, target_id)
    conn.commit()
    ats_targets = user_data.get_ats_targets(conn, user_id)
    return {"ats_targets": ats_targets}


@router.put("/settings/llm-providers/reorder")
async def reorder_settings_llm_providers(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user_api),
    body: dict = Body(...),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.reorder_llm_providers(conn, user_id, body.get("order", []))
    conn.commit()
    return {"llm_providers": user_data.get_llm_providers(conn, user_id)}


@router.put("/settings/llm-providers/{provider}")
async def save_settings_llm_provider(
    request: Request,
    provider: str,
    current_user: CurrentUser = Depends(get_current_user_api),
    body: dict = Body(...),
) -> dict:
    if provider not in _KNOWN_LLM_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    api_key = body.get("api_key", "").strip()
    if not api_key:
        user_data.delete_llm_provider(conn, user_id, provider)
        conn.commit()
        return {"llm_providers": user_data.get_llm_providers(conn, user_id)}
    try:
        await asyncio.to_thread(llm.validate_provider_key, provider, api_key)
    except llm.LLMError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_provider_key", "message": str(exc)},
        )
    user_data.save_llm_provider(conn, user_id, provider, api_key)
    conn.commit()
    return {"llm_providers": user_data.get_llm_providers(conn, user_id)}


@router.delete("/settings/llm-providers/{provider}")
async def delete_settings_llm_provider(
    request: Request,
    provider: str,
    current_user: CurrentUser = Depends(get_current_user_api),
) -> dict:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_llm_provider(conn, user_id, provider)
    conn.commit()
    return {"llm_providers": user_data.get_llm_providers(conn, user_id)}
