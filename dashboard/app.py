# dashboard/app.py
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    import profile_parser

    profile = profile_parser.load_profile()
    profile_exists = profile_parser._PROFILE_MD.exists()
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"profile": profile, "profile_exists": profile_exists},
    )
