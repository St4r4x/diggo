from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import mistune

import profile_parser
from auth import (
    CurrentUser,
    clear_auth_cookies,
    get_current_user,
    set_auth_cookies,
    validate_access_token,
)
from db import VALID_STATUSES, open_db
from env import load_env

load_env()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)
_SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
_SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
TEMPLATES_DIR = Path(__file__).parent / "templates"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

STATUS_COLORS: dict[str, str] = {
    "À envoyer": "bg-gray-700 text-gray-200",
    "Envoyée": "bg-blue-700 text-white",
    "Relance": "bg-amber-600 text-white",
    "Entretien RH": "bg-violet-700 text-white",
    "Entretien tech": "bg-violet-900 text-white",
    "Offre": "bg-emerald-700 text-white",
    "Acceptée": "bg-emerald-700 text-white",
    "Refusée": "bg-red-700 text-white",
    "Abandonnée": "bg-red-900 text-white",
}

GRADE_COLORS: dict[str, str] = {
    "A": "bg-green-600 text-white",
    "B": "bg-green-700 text-white",
    "C": "bg-yellow-600 text-white",
    "D": "bg-orange-600 text-white",
    "F": "bg-red-700 text-white",
}

_FUNNEL_STEPS = [
    "À envoyer",
    "Envoyée",
    "Relance",
    "Entretien RH",
    "Entretien tech",
    "Offre",
    "Acceptée",
]
_EXIT_STEPS = ["Refusée", "Abandonnée"]


def _build_funnel(
    by_status: dict[str, int],
) -> tuple[list[dict], list[dict], int]:
    funnel: list[dict] = []
    for i, s in enumerate(_FUNNEL_STEPS):
        count = by_status.get(s, 0)
        prev_count = by_status.get(_FUNNEL_STEPS[i - 1], 0) if i > 0 else None
        rate = round(count / prev_count * 100, 1) if prev_count else None
        funnel.append({"status": s, "count": count, "rate": rate})
    exits = [{"status": s, "count": by_status.get(s, 0)} for s in _EXIT_STEPS]
    all_counts = [s["count"] for s in funnel] + [s["count"] for s in exits]
    max_count = max(all_counts) if any(all_counts) else 1
    return funnel, exits, max_count


def _parse_description(raw: str) -> dict:
    """Return parsed description dict from JSON, or legacy text in mission field."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        "mission": raw,
        "profil": "",
        "stack": "",
        "avantages": "",
        "contrat": "",
        "salaire": "",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(_DATABASE_URL)
    app.state.scan_status = "idle"
    app.state.scan_result: dict = {
        "inserted": 0,
        "skipped": 0,
        "found": 0,
        "scored": 0,
        "abandoned": 0,
        "error": "",
    }
    yield
    app.state.db.close()


app = FastAPI(lifespan=lifespan)
_scan_lock = asyncio.Lock()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.globals["STATUS_COLORS"] = STATUS_COLORS
templates.env.globals["GRADE_COLORS"] = GRADE_COLORS
templates.env.globals["supabase_url"] = _SUPABASE_URL
templates.env.globals["supabase_anon_key"] = _SUPABASE_ANON_KEY


# ── Public auth routes ────────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html")


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/signup.html")


@app.get("/auth/confirm", response_class=HTMLResponse)
async def auth_confirm_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/confirm.html")


@app.get("/auth/reset-password", response_class=HTMLResponse)
async def auth_reset_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/reset-password.html")


@app.post("/auth/session")
async def auth_session_create(
    request: Request,
    access_token: str = Body(...),
    refresh_token: str = Body(...),
) -> JSONResponse:
    validate_access_token(access_token)
    response = JSONResponse({"ok": True})
    set_auth_cookies(response, access_token, refresh_token)
    return response


@app.delete("/auth/session")
async def auth_session_delete(request: Request) -> RedirectResponse:
    response = RedirectResponse("/login", status_code=302)
    clear_auth_cookies(response)
    return response


# ── Protected routes ──────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    offers = db.get_all({}, user_id=user_id)
    followup_ids = {f["id"] for f in db.get_followups(user_id=user_id)}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "offers": offers,
            "statuses": VALID_STATUSES,
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
            "followup_ids": followup_ids,
            "current_user": current_user,
        },
    )


@app.get("/offers", response_class=HTMLResponse)
async def offer_list(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    status: str = Query(""),
    grade: str = Query(""),
    q: str = Query(""),
    sal_min: str = Query(""),
) -> HTMLResponse:
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
    followup_ids = {f["id"] for f in db.get_followups(user_id=user_id)}
    return templates.TemplateResponse(
        request,
        "partials/offer_list.html",
        {
            "offers": offers,
            "followup_ids": followup_ids,
        },
    )


@app.get("/offers/{offer_id}/edit", response_class=HTMLResponse)
async def offer_edit_form(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return templates.TemplateResponse(
        request,
        "partials/offer_form.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
        },
    )


@app.get("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_detail(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
            "parsed_desc": _parse_description(offer.get("description", "")),
        },
    )


@app.post("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_save(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    company: str = Form(""),
    role: str = Form(""),
    offer_url: str = Form(""),
    detection_date: str = Form(""),
    score_grade: str = Form(""),
    score_value: str = Form("0"),
    status: str = Form("À envoyer"),
    send_date: str = Form(""),
    follow_up_date: str = Form(""),
    contacts: str = Form(""),
    notes: str = Form(""),
    cv_path: str = Form(""),
    cover_letter_path: str = Form(""),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    if db.get_by_id(offer_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    try:
        sv = float(score_value)
    except (ValueError, TypeError):
        sv = 0.0
    fields = {
        "company": company,
        "role": role,
        "offer_url": offer_url,
        "detection_date": detection_date,
        "score_grade": score_grade,
        "score_value": sv,
        "status": status,
        "send_date": send_date or None,
        "follow_up_date": follow_up_date or None,
        "contacts": contacts,
        "notes": notes,
        "cv_path": cv_path,
        "cover_letter_path": cover_letter_path,
    }
    offer = db.update(offer_id, fields, user_id=user_id)
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
            "parsed_desc": _parse_description(offer.get("description", "")),
        },
    )


@app.delete("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_delete(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    db.delete(offer_id, user_id=user_id)
    return templates.TemplateResponse(request, "partials/offer_empty.html", {})


@app.post("/offers/{offer_id}/notes", response_class=HTMLResponse)
async def offer_notes(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    notes: str = Form(""),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    if db.get_by_id(offer_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = db.update(offer_id, {"notes": notes}, user_id=user_id)
    return templates.TemplateResponse(
        request,
        "partials/offer_notes.html",
        {"offer": offer, "saved": True},
    )


@app.post("/offers/{offer_id}/status", response_class=HTMLResponse)
async def offer_status(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    status: str = Form(...),
) -> HTMLResponse:
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    db = request.app.state.db
    user_id = current_user["sub"]
    offer = db.update_status(offer_id, status, user_id=user_id)
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
            "parsed_desc": _parse_description(offer.get("description", "")),
        },
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    db = request.app.state.db
    user_id = current_user["sub"]
    stats = db.get_stats(user_id=user_id)
    funnel, exits, max_count = _build_funnel(stats["by_status"])
    report_files = list(REPORTS_DIR.glob("daily-*.md")) if REPORTS_DIR.is_dir() else []
    latest_report_html: str | None = None
    latest_report_date: str | None = None
    if report_files:
        latest = max(report_files, key=lambda p: p.name)
        latest_report_date = latest.stem.replace("daily-", "")
        latest_report_html = mistune.html(latest.read_text(encoding="utf-8"))
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "stats": stats,
            "statuses": VALID_STATUSES,
            "funnel": funnel,
            "exits": exits,
            "max_count": max_count,
            "latest_report_html": latest_report_html,
            "latest_report_date": latest_report_date,
            "current_user": current_user,
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    profile = profile_parser.load_profile()
    profile_exists = profile_parser._PROFILE_MD.exists()
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile": profile,
            "profile_exists": profile_exists,
            "current_user": current_user,
        },
    )


@app.post("/profile/contact", response_class=HTMLResponse)
async def profile_save_contact(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    name: str = Form(""),
    title: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    location: str = Form(""),
    linkedin: str = Form(""),
    github: str = Form(""),
) -> HTMLResponse:
    data = profile_parser.load_profile()
    data["contact"] = {
        "name": name,
        "title": title,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
    }
    try:
        profile_parser.save_profile(data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_contact.html",
            {"profile": data, "saved": False, "error": "Erreur lors de la sauvegarde"},
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_contact.html",
        {"profile": data, "saved": True},
    )


@app.post("/profile/summary", response_class=HTMLResponse)
async def profile_save_summary(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    summary: str = Form(""),
) -> HTMLResponse:
    data = profile_parser.load_profile()
    data["summary"] = summary
    try:
        profile_parser.save_profile(data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_summary.html",
            {"profile": data, "saved": False, "error": "Erreur lors de la sauvegarde"},
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_summary.html",
        {"profile": data, "saved": True},
    )


@app.post("/profile/experience", response_class=HTMLResponse)
async def profile_save_experience(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    data: str = Form(""),
) -> HTMLResponse:
    profile_data = profile_parser.load_profile()
    try:
        profile_data["experience"] = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return templates.TemplateResponse(
            request,
            "partials/profile_experience.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    try:
        profile_parser.save_profile(profile_data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_experience.html",
            {
                "profile": profile_data,
                "saved": False,
                "error": "Erreur lors de la sauvegarde",
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_experience.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/skills", response_class=HTMLResponse)
async def profile_save_skills(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    data: str = Form(""),
) -> HTMLResponse:
    profile_data = profile_parser.load_profile()
    try:
        profile_data["skills"] = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return templates.TemplateResponse(
            request,
            "partials/profile_skills.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    try:
        profile_parser.save_profile(profile_data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_skills.html",
            {
                "profile": profile_data,
                "saved": False,
                "error": "Erreur lors de la sauvegarde",
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_skills.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/education", response_class=HTMLResponse)
async def profile_save_education(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    data: str = Form(""),
) -> HTMLResponse:
    profile_data = profile_parser.load_profile()
    try:
        parsed = json.loads(data)
        profile_data["education"] = parsed.get("education", [])
        profile_data["certifications"] = parsed.get("certifications", [])
    except (json.JSONDecodeError, ValueError, AttributeError):
        return templates.TemplateResponse(
            request,
            "partials/profile_education.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    try:
        profile_parser.save_profile(profile_data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_education.html",
            {
                "profile": profile_data,
                "saved": False,
                "error": "Erreur lors de la sauvegarde",
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_education.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/projects", response_class=HTMLResponse)
async def profile_save_projects(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    data: str = Form(""),
) -> HTMLResponse:
    profile_data = profile_parser.load_profile()
    try:
        profile_data["projects"] = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return templates.TemplateResponse(
            request,
            "partials/profile_projects.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    try:
        profile_parser.save_profile(profile_data)
    except OSError:
        return templates.TemplateResponse(
            request,
            "partials/profile_projects.html",
            {
                "profile": profile_data,
                "saved": False,
                "error": "Erreur lors de la sauvegarde",
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/profile_projects.html",
        {"profile": profile_data, "saved": True},
    )


async def _run_scan_task(app_state: Any, user_id: str) -> None:
    try:
        from scripts.import_offers import (
            _run_pipeline,
            expire_stale_offers,
            import_offers,
        )
        from scripts.pre_filter import load_settings

        settings = load_settings()
        app_state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "found": 0,
            "scored": 0,
            "abandoned": 0,
            "error": "",
        }

        offers = await _run_pipeline(settings)
        app_state.scan_result["found"] = len(offers)
        app_state.scan_result["scored"] = len(offers)

        inserted, skipped = import_offers(offers, user_id=user_id)
        abandoned = expire_stale_offers(user_id=user_id)

        app_state.scan_result = {
            "inserted": inserted,
            "skipped": skipped,
            "found": len(offers),
            "scored": len(offers),
            "abandoned": abandoned,
            "error": "",
        }
        app_state.scan_status = "done"
    except Exception as exc:
        app_state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "found": 0,
            "scored": 0,
            "abandoned": 0,
            "error": str(exc).splitlines()[0],
        }
        app_state.scan_status = "error"


def _start_scan(app_state: Any, user_id: str) -> bool:
    """Set state to running and enqueue task. Returns False if already running."""
    if app_state.scan_status == "running":
        return False
    app_state.scan_status = "running"
    app_state.scan_result = {
        "inserted": 0,
        "skipped": 0,
        "found": 0,
        "scored": 0,
        "abandoned": 0,
        "error": "",
    }
    asyncio.create_task(_run_scan_task(app_state, user_id))
    return True


@app.post("/scan/start", response_class=HTMLResponse)
async def scan_start(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    async with _scan_lock:
        started = _start_scan(request.app.state, user_id=current_user["sub"])
        if not started:
            return templates.TemplateResponse(
                request,
                "partials/scan_status.html",
                {"status": "running", "result": request.app.state.scan_result},
            )
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {"status": "running", "result": request.app.state.scan_result},
    )


@app.get("/scan/status", response_class=HTMLResponse)
async def scan_status(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
        },
    )
