# dashboard/app.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import DB, VALID_STATUSES, open_db

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

app = FastAPI()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Register color maps as Jinja2 globals so they don't appear in per-request
# context (which would cause an unhashable-type error in Jinja2's LRU cache).
templates.env.globals["STATUS_COLORS"] = STATUS_COLORS
templates.env.globals["GRADE_COLORS"] = GRADE_COLORS


def _get_db(request: Request) -> DB:
    db = getattr(request.app.state, "db", None)
    if db is None:
        request.app.state.db = open_db(DB_PATH)
        db = request.app.state.db
    return db


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = _get_db(request)
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
    db = _get_db(request)
    filters = {k: v for k, v in {"status": status, "grade": grade, "q": q}.items() if v}
    offers = db.get_all(filters)
    return templates.TemplateResponse(
        request,
        "partials/offer_list.html",
        {
            "offers": offers,
        },
    )
