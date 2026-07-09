from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import mistune

import api
import llm
import profile_parser
import user_data
from auth import (
    CurrentUser,
    get_current_user,
    require_onboarding_complete,
)
from db import VALID_STATUSES, open_db, parse_description
from env import load_env

load_env()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)
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
_MIN_OFFER_DESCRIPTION_LENGTH = 300


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


def _group_skills_by_category(skills: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for s in skills:
        grouped.setdefault(s["category"], []).append(s["skill"])
    return grouped


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

app.include_router(api.router)


# ── Protected routes ──────────────────────────────────────────────────────────


@app.post("/offers/{offer_id}/prepare", response_class=HTMLResponse)
async def offer_prepare(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(require_onboarding_complete),
    skip_prep: bool = Form(False),
) -> HTMLResponse:
    from datetime import date as _date

    from scripts.generate_cover_letter import build_cover_letter_context
    from scripts.generate_cover_letter import generate_pdf as generate_cl_pdf
    from scripts.generate_pdf import build_cv_context
    from scripts.generate_pdf import generate_pdf as generate_cv_pdf
    from scripts.generate_prep_sheet import build_prep_sheet_context
    from scripts.generate_prep_sheet import generate_pdf as generate_prep_pdf

    db = request.app.state.db
    conn = db.conn
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    def _error(message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "partials/offer_detail.html",
            {
                "offer": offer,
                "statuses": VALID_STATUSES,
                "parsed_desc": parse_description(offer.get("description", "")),
                "prep_error": message,
            },
        )

    if len(offer.get("description", "")) < _MIN_OFFER_DESCRIPTION_LENGTH:
        return _error(
            "Description trop courte pour préparer la candidature. "
            "Complète-la via les notes ou l'édition de l'offre avant de réessayer."
        )

    hf_token = user_data.get_hf_token(conn, user_id)
    if not hf_token:
        return _error(
            "Ajoute ton token Hugging Face dans les paramètres avant de préparer "
            "une candidature."
        )

    try:
        analysis = llm.analyze_offer(hf_token, offer)
        cv_lang = "en" if analysis.requires_english_cv else "fr"
        cv = user_data.get_cv(conn, user_id, lang=cv_lang)
        profile = user_data.get_profile(conn, user_id)
        cv_rewrite = llm.rewrite_cv_summary(hf_token, profile, cv, analysis)
        cover_letter_draft = llm.write_cover_letter(
            hf_token, profile, cv, offer, analysis
        )
        prep_draft = (
            None
            if skip_prep
            else llm.generate_prep_questions(hf_token, offer, analysis)
        )
    except (llm.LLMError, llm.GroundingError) as exc:
        return _error(f"Échec de la préparation IA : {exc}")

    today = str(_date.today())

    try:
        cv_context = build_cv_context(
            name=profile["name"],
            title=profile["title"],
            email=profile["email"],
            phone=profile["phone"],
            location=profile["location"],
            summary=cv_rewrite.summary,
            experience=cv["experience"],
            skill_categories=_group_skills_by_category(cv["skills"]),
            highlighted_skills=cv_rewrite.highlighted_skills,
            education=cv["education"],
            languages=[],
            linkedin=profile["linkedin"],
            github=profile["github"],
            certifications=cv["certifications"],
        )
        cv_path = generate_cv_pdf(
            cv_context, offer=offer["company"], output_date=today, lang=cv_lang
        )

        recipient = (
            "Madame, Monsieur,"
            if analysis.offer_language == "fr"
            else "Dear Hiring Team,"
        )
        cl_context = build_cover_letter_context(
            name=profile["name"],
            title=profile["title"],
            email=profile["email"],
            phone=profile["phone"],
            location=profile["location"],
            date_str=today,
            company=offer["company"],
            role=offer["role"],
            recipient=recipient,
            paragraphs=cover_letter_draft.paragraphs,
            lang=analysis.offer_language,
        )
        cl_path = generate_cl_pdf(cl_context, offer=offer["company"], output_date=today)

        prep_path = None
        if prep_draft is not None:
            prep_context = build_prep_sheet_context(
                company=offer["company"],
                role=offer["role"],
                date_str=today,
                company_summary=prep_draft.company_summary,
                tech_stack=prep_draft.tech_stack,
                questions=prep_draft.questions,
            )
            prep_path = generate_prep_pdf(
                prep_context, offer=offer["company"], output_date=today
            )
    except Exception as exc:
        # PDF rendering (WeasyPrint/Jinja2) can fail in ways we can't enumerate up
        # front; the design spec requires any rendering failure to surface as a
        # clear error, not a 500 - see docs/superpowers/specs/2026-07-06-llm-migration-design.md.
        return _error(f"Échec de la génération des PDF : {exc}")

    offer = db.update(
        offer_id,
        {
            "cv_path": str(cv_path),
            "cover_letter_path": str(cl_path),
            "prep_sheet_path": str(prep_path) if prep_path else "",
        },
        user_id=user_id,
    )
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
            "parsed_desc": parse_description(offer.get("description", "")),
        },
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(
    request: Request,
    current_user: CurrentUser = Depends(require_onboarding_complete),
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
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    profile = profile_parser.load_profile(conn, user_id)
    cv = user_data.get_cv(conn, user_id, lang="fr")
    cv_en = user_data.get_cv(conn, user_id, lang="en")
    onboarding = user_data.get_onboarding_state(conn, user_id)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile": profile,
            "cv": cv,
            "cv_en": cv_en,
            "current_user": current_user,
            "onboarding": onboarding,
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
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    existing = profile_parser.load_profile(conn, user_id)
    existing["contact"] = {
        "name": name,
        "title": title,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
    }
    profile_parser.save_profile(conn, user_id, existing)
    conn.commit()
    return templates.TemplateResponse(
        request,
        "partials/profile_contact.html",
        {"profile": existing, "saved": True},
    )


@app.post("/profile/text", response_class=HTMLResponse)
async def profile_save_text(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    profile_md: str = Form(""),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    existing = profile_parser.load_profile(conn, user_id)
    existing["profile_md"] = profile_md
    profile_parser.save_profile(conn, user_id, existing)
    conn.commit()
    return templates.TemplateResponse(
        request,
        "partials/profile_text.html",
        {"profile": existing, "saved": True},
    )


@app.post("/profile/cv/meta", response_class=HTMLResponse)
async def profile_save_cv_meta(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    lang: str = Form("fr"),
    summary: str = Form(""),
) -> HTMLResponse:
    if lang not in ("fr", "en"):
        lang = "fr"
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.save_cv_meta(conn, user_id, lang, summary)
    conn.commit()
    cv = user_data.get_cv(conn, user_id, lang=lang)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_meta.html",
        {"cv": cv, "lang": lang, "saved": True},
    )


@app.post("/profile/cv/experience", response_class=HTMLResponse)
async def profile_save_cv_experience(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    lang: str = Form("fr"),
    data: str = Form(""),
) -> HTMLResponse:
    if lang not in ("fr", "en"):
        lang = "fr"
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    try:
        entries = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        cv = user_data.get_cv(conn, user_id, lang=lang)
        return templates.TemplateResponse(
            request,
            "partials/profile_cv_experience.html",
            {"cv": cv, "lang": lang, "saved": False, "error": "Format JSON invalide"},
        )
    user_data.save_experience(conn, user_id, lang, entries)
    conn.commit()
    cv = user_data.get_cv(conn, user_id, lang=lang)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_experience.html",
        {"cv": cv, "lang": lang, "saved": True},
    )


@app.delete("/profile/cv/experience/{exp_id}", response_class=HTMLResponse)
async def profile_delete_cv_experience(
    request: Request,
    exp_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    lang: str = Query("fr"),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_experience(conn, user_id, exp_id)
    conn.commit()
    cv = user_data.get_cv(conn, user_id, lang=lang)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_experience.html",
        {"cv": cv, "lang": lang, "saved": True},
    )


@app.post("/profile/cv/skills", response_class=HTMLResponse)
async def profile_save_cv_skills(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    lang: str = Form("fr"),
    data: str = Form(""),
) -> HTMLResponse:
    if lang not in ("fr", "en"):
        lang = "fr"
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    try:
        entries = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        cv = user_data.get_cv(conn, user_id, lang=lang)
        return templates.TemplateResponse(
            request,
            "partials/profile_cv_skills.html",
            {"cv": cv, "lang": lang, "saved": False, "error": "Format JSON invalide"},
        )
    user_data.save_skills(conn, user_id, lang, entries)
    conn.commit()
    cv = user_data.get_cv(conn, user_id, lang=lang)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_skills.html",
        {"cv": cv, "lang": lang, "saved": True},
    )


@app.post("/profile/cv/certifications", response_class=HTMLResponse)
async def profile_save_cv_certifications(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    data: str = Form(""),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    try:
        entries = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        cv = user_data.get_cv(conn, user_id)
        return templates.TemplateResponse(
            request,
            "partials/profile_cv_certifications.html",
            {"cv": cv, "saved": False, "error": "Format JSON invalide"},
        )
    user_data.save_certifications(conn, user_id, entries)
    conn.commit()
    cv = user_data.get_cv(conn, user_id)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_certifications.html",
        {"cv": cv, "saved": True},
    )


@app.post("/profile/cv/education", response_class=HTMLResponse)
async def profile_save_cv_education(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    lang: str = Form("fr"),
    data: str = Form(""),
) -> HTMLResponse:
    if lang not in ("fr", "en"):
        lang = "fr"
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    try:
        entries = json.loads(data)
    except (json.JSONDecodeError, ValueError):
        cv = user_data.get_cv(conn, user_id, lang=lang)
        return templates.TemplateResponse(
            request,
            "partials/profile_cv_education.html",
            {"cv": cv, "lang": lang, "saved": False, "error": "Format JSON invalide"},
        )
    user_data.save_education(conn, user_id, lang, entries)
    conn.commit()
    cv = user_data.get_cv(conn, user_id, lang=lang)
    return templates.TemplateResponse(
        request,
        "partials/profile_cv_education.html",
        {"cv": cv, "lang": lang, "saved": True},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    settings = user_data.get_settings(conn, user_id)
    ats_targets = user_data.get_ats_targets(conn, user_id)
    hf_token_set = user_data.get_hf_token(conn, user_id) is not None
    onboarding = user_data.get_onboarding_state(conn, user_id)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "settings": settings,
            "ats_targets": ats_targets,
            "current_user": current_user,
            "hf_token_set": hf_token_set,
            "onboarding": onboarding,
        },
    )


@app.post("/settings/search", response_class=HTMLResponse)
async def settings_save_search(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    keywords: str = Form(""),
    portal_queries: str = Form(""),
    location: str = Form(""),
    contract: str = Form("CDI"),
    experience_max_years: int = Form(3),
    salary_min: int = Form(0),
    salary_max: int = Form(0),
    target_companies: str = Form(""),
    follow_up_days: int = Form(7),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    data = {
        "keywords": [k.strip() for k in keywords.splitlines() if k.strip()],
        "portal_queries": [k.strip() for k in portal_queries.splitlines() if k.strip()],
        "location": location,
        "contract": contract,
        "experience_max_years": experience_max_years,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "target_companies": [
            c.strip() for c in target_companies.splitlines() if c.strip()
        ],
        "follow_up_days": follow_up_days,
    }
    user_data.save_settings(conn, user_id, data)
    conn.commit()
    return templates.TemplateResponse(
        request,
        "partials/settings_search.html",
        {"settings": data, "saved": True},
    )


@app.post("/settings/ats", response_class=HTMLResponse)
async def settings_ats_add(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    name: str = Form(""),
    careers_url: str = Form(""),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.add_ats_target(conn, user_id, name, careers_url)
    conn.commit()
    ats_targets = user_data.get_ats_targets(conn, user_id)
    return templates.TemplateResponse(
        request,
        "partials/settings_ats.html",
        {"ats_targets": ats_targets},
    )


@app.delete("/settings/ats/{target_id}", response_class=HTMLResponse)
async def settings_ats_delete(
    request: Request,
    target_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_ats_target(conn, user_id, target_id)
    conn.commit()
    ats_targets = user_data.get_ats_targets(conn, user_id)
    return templates.TemplateResponse(
        request,
        "partials/settings_ats.html",
        {"ats_targets": ats_targets},
    )


@app.post("/settings/hf-token", response_class=HTMLResponse)
async def settings_save_hf_token(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    hf_token: str = Form(""),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    token = hf_token.strip()
    if not token:
        user_data.delete_hf_token(conn, user_id)
        conn.commit()
        return templates.TemplateResponse(
            request,
            "partials/settings_hf_token.html",
            {"hf_token_set": False},
        )
    try:
        llm.validate_hf_token(token)
    except llm.LLMError as exc:
        return templates.TemplateResponse(
            request,
            "partials/settings_hf_token.html",
            {"hf_token_set": False, "hf_token_error": str(exc)},
        )
    user_data.save_hf_token(conn, user_id, token)
    conn.commit()
    return templates.TemplateResponse(
        request,
        "partials/settings_hf_token.html",
        {"hf_token_set": True},
    )


@app.delete("/settings/hf-token", response_class=HTMLResponse)
async def settings_delete_hf_token(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    conn = request.app.state.db.conn
    user_id = current_user["sub"]
    user_data.delete_hf_token(conn, user_id)
    conn.commit()
    return templates.TemplateResponse(
        request,
        "partials/settings_hf_token.html",
        {"hf_token_set": False},
    )


async def _run_scan_task(app_state: Any, user_id: str) -> None:
    try:
        from scripts.import_offers import (
            _run_pipeline,
            expire_stale_offers,
            import_offers,
        )
        from scripts.pre_filter import load_settings

        settings = load_settings(user_id=user_id)
        app_state.scan_result = {
            "inserted": 0,
            "skipped": 0,
            "found": 0,
            "scored": 0,
            "abandoned": 0,
            "error": "",
        }

        offers = await _run_pipeline(settings, user_id=user_id)
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
    current_user: CurrentUser = Depends(require_onboarding_complete),
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
