# dashboard/app.py
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import profile_parser
from db import VALID_STATUSES, open_db

DB_PATH = Path(__file__).parent / "data" / "applications.db"
TEMPLATES_DIR = Path(__file__).parent / "templates"

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(DB_PATH)
    app.state.scan_status = "idle"
    app.state.scan_result: dict = {
        "inserted": 0,
        "skipped": 0,
        "found": 0,
        "scored": 0,
        "error": "",
    }
    yield
    app.state.db.conn.close()


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Register color maps as Jinja2 globals so every template (including
# {% include %} partials) can access them without repeating them in
# every TemplateResponse call.
templates.env.globals["STATUS_COLORS"] = STATUS_COLORS
templates.env.globals["GRADE_COLORS"] = GRADE_COLORS


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = request.app.state.db
    offers = db.get_all({})
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "offers": offers,
            "statuses": VALID_STATUSES,
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
        },
    )


@app.get("/offers", response_class=HTMLResponse)
async def offer_list(
    request: Request,
    status: str = Query(""),
    grade: str = Query(""),
    q: str = Query(""),
):
    db = request.app.state.db
    filters = {k: v for k, v in {"status": status, "grade": grade, "q": q}.items() if v}
    offers = db.get_all(filters)
    return templates.TemplateResponse(
        request,
        "partials/offer_list.html",
        {
            "offers": offers,
        },
    )


@app.get("/offers/{offer_id}/edit", response_class=HTMLResponse)
async def offer_edit_form(request: Request, offer_id: int):
    db = request.app.state.db
    offer = db.get_by_id(offer_id)
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
async def offer_detail(request: Request, offer_id: int):
    db = request.app.state.db
    offer = db.get_by_id(offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
        },
    )


@app.post("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_save(
    request: Request,
    offer_id: int,
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
):
    db = request.app.state.db
    if db.get_by_id(offer_id) is None:
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
    offer = db.update(offer_id, fields)
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
        },
    )


@app.delete("/offers/{offer_id}", response_class=HTMLResponse)
async def offer_delete(request: Request, offer_id: int):
    db = request.app.state.db
    db.delete(offer_id)
    return templates.TemplateResponse(
        request,
        "partials/offer_empty.html",
        {},
    )


@app.post("/offers/{offer_id}/status", response_class=HTMLResponse)
async def offer_status(request: Request, offer_id: int, status: str = Form(...)):
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    db = request.app.state.db
    offer = db.update_status(offer_id, status)
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
        },
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    db = request.app.state.db
    stats = db.get_stats()
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "stats": stats,
            "statuses": VALID_STATUSES,
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):

    profile = profile_parser.load_profile()
    profile_exists = profile_parser._PROFILE_MD.exists()
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"profile": profile, "profile_exists": profile_exists},
    )


@app.post("/profile/contact", response_class=HTMLResponse)
async def profile_save_contact(
    request: Request,
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
    request: Request, data: str = Form("")
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
    profile_parser.save_profile(profile_data)
    return templates.TemplateResponse(
        request,
        "partials/profile_experience.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/skills", response_class=HTMLResponse)
async def profile_save_skills(request: Request, data: str = Form("")):
    profile_data = profile_parser.load_profile()
    try:
        profile_data["skills"] = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return templates.TemplateResponse(
            request,
            "partials/profile_skills.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    profile_parser.save_profile(profile_data)
    return templates.TemplateResponse(
        request,
        "partials/profile_skills.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/education", response_class=HTMLResponse)
async def profile_save_education(request: Request, data: str = Form("")):
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
    profile_parser.save_profile(profile_data)
    return templates.TemplateResponse(
        request,
        "partials/profile_education.html",
        {"profile": profile_data, "saved": True},
    )


@app.post("/profile/projects", response_class=HTMLResponse)
async def profile_save_projects(request: Request, data: str = Form("")):
    profile_data = profile_parser.load_profile()
    try:
        profile_data["projects"] = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return templates.TemplateResponse(
            request,
            "partials/profile_projects.html",
            {"profile": profile_data, "saved": False, "error": "Format JSON invalide"},
        )
    profile_parser.save_profile(profile_data)
    return templates.TemplateResponse(
        request,
        "partials/profile_projects.html",
        {"profile": profile_data, "saved": True},
    )


async def _run_scan_task(app_state) -> None:
    try:
        from scripts.import_offers import _run_pipeline, import_offers
        from scripts.pre_filter import load_settings

        settings = load_settings()
        app_state.scan_result["found"] = 0
        app_state.scan_result["scored"] = 0

        offers = await _run_pipeline(settings)
        app_state.scan_result["found"] = len(offers)
        app_state.scan_result["scored"] = len(offers)

        inserted, skipped = import_offers(offers, DB_PATH)
        app_state.scan_result = {
            "inserted": inserted,
            "skipped": skipped,
            "found": len(offers),
            "scored": len(offers),
            "error": "",
        }
        app_state.scan_status = "done"
    except Exception as exc:
        app_state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "found": 0,
            "scored": 0,
            "error": str(exc).splitlines()[0],
        }
        app_state.scan_status = "error"


@app.post("/scan/start", response_class=HTMLResponse)
async def scan_start(request: Request):
    if request.app.state.scan_status == "running":
        return templates.TemplateResponse(
            request,
            "partials/scan_status.html",
            {"status": "running", "result": request.app.state.scan_result},
        )
    request.app.state.scan_status = "running"
    request.app.state.scan_result = {
        "inserted": 0,
        "skipped": 0,
        "found": 0,
        "scored": 0,
        "error": "",
    }
    asyncio.create_task(_run_scan_task(request.app.state))
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {"status": "running", "result": request.app.state.scan_result},
    )


@app.get("/scan/status", response_class=HTMLResponse)
async def scan_status(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
        },
    )
