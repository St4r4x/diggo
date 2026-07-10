from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import api
import llm
import user_data
from auth import (
    CurrentUser,
    get_current_user,
)
from db import open_db
from env import load_env

load_env()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)
TEMPLATES_DIR = Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(_DATABASE_URL)
    yield
    app.state.db.close()


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(api.router)


# ── Protected routes ──────────────────────────────────────────────────────────


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
