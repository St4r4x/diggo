from __future__ import annotations

# In-process memory only: _status/_stage/_error are plain dicts, lost on
# restart and not shared across replicas. Restarting the `api` container is
# the documented way to kill a running prepare (see docs/frontend-migration-status.md).
import asyncio
import os
from datetime import date as _date
from typing import Any

import llm
import user_data
from db import open_db

MIN_OFFER_DESCRIPTION_LENGTH = 300

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)

_status: dict[int, str] = {}
_stage: dict[int, str] = {}
_error: dict[int, str] = {}


def _group_skills_by_category(skills: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for s in skills:
        grouped.setdefault(s["category"], []).append(s["skill"])
    return grouped


def get_prepare_state(offer_id: int) -> dict[str, Any]:
    return {
        "status": _status.get(offer_id, "idle"),
        "stage": _stage.get(offer_id, ""),
        "error": _error.get(offer_id, ""),
    }


async def _run_prepare(offer_id: int, user_id: str, skip_prep: bool) -> None:
    from scripts.generate_cover_letter import build_cover_letter_context
    from scripts.generate_cover_letter import generate_pdf as generate_cl_pdf
    from scripts.generate_pdf import build_cv_context
    from scripts.generate_pdf import generate_pdf as generate_cv_pdf
    from scripts.generate_prep_sheet import build_prep_sheet_context
    from scripts.generate_prep_sheet import generate_pdf as generate_prep_pdf

    db = open_db(_DATABASE_URL)
    conn = db.conn
    try:
        offer = db.get_by_id(offer_id, user_id=user_id)
        if offer is None:
            _status[offer_id] = "error"
            _error[offer_id] = "Offre introuvable."
            return

        provider_names = [
            p["provider"] for p in user_data.get_llm_providers(conn, user_id)
        ]
        providers: list[tuple[str, str]] = []
        for name in provider_names:
            key = user_data.get_llm_provider_key(conn, user_id, name)
            if key is not None:
                providers.append((name, key))
        if not providers:
            _status[offer_id] = "error"
            if provider_names:
                _error[offer_id] = (
                    "Aucune des clés de fournisseur LLM configurées n'a pu être "
                    "déchiffrée. Réenregistre ta clé dans les paramètres."
                )
            else:
                _error[offer_id] = (
                    "Ajoute au moins un fournisseur LLM dans les paramètres avant "
                    "de préparer une candidature."
                )
            return

        try:
            _stage[offer_id] = "Analyse de l'offre…"
            analysis = await asyncio.to_thread(llm.analyze_offer, providers, offer)
            cv_lang = "en" if analysis.requires_english_cv else "fr"
            cv = user_data.get_cv(conn, user_id, lang=cv_lang)
            profile = user_data.get_profile(conn, user_id)

            _stage[offer_id] = "Rédaction du CV…"
            cv_rewrite = await asyncio.to_thread(
                llm.rewrite_cv_summary, providers, profile, cv, analysis
            )

            _stage[offer_id] = "Rédaction de la lettre…"
            cover_letter_draft = await asyncio.to_thread(
                llm.write_cover_letter, providers, profile, cv, offer, analysis
            )

            prep_draft = None
            if not skip_prep:
                _stage[offer_id] = "Génération de la fiche d'entretien…"
                prep_draft = await asyncio.to_thread(
                    llm.generate_prep_questions, providers, offer, analysis
                )
        except (llm.LLMError, llm.GroundingError) as exc:
            _status[offer_id] = "error"
            _error[offer_id] = f"Échec de la préparation IA : {exc}"
            return

        today = str(_date.today())

        try:
            _stage[offer_id] = "Génération des PDF…"
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
                languages=[lang["name"] for lang in cv["languages"]],
                linkedin=profile["linkedin"],
                github=profile["github"],
                certifications=cv["certifications"],
                projects=cv["projects"],
                hobbies=[hobby["name"] for hobby in cv["hobbies"]],
            )
            cv_path = await asyncio.to_thread(
                generate_cv_pdf,
                cv_context,
                offer=offer["company"],
                output_date=today,
                lang=cv_lang,
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
            cl_path = await asyncio.to_thread(
                generate_cl_pdf,
                cl_context,
                offer=offer["company"],
                output_date=today,
            )

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
                prep_path = await asyncio.to_thread(
                    generate_prep_pdf,
                    prep_context,
                    offer=offer["company"],
                    output_date=today,
                )
        except Exception as exc:
            # PDF rendering (WeasyPrint/Jinja2) can fail in ways we can't enumerate up
            # front - see docs/superpowers/specs/2026-07-06-llm-migration-design.md.
            _status[offer_id] = "error"
            _error[offer_id] = f"Échec de la génération des PDF : {exc}"
            return

        db.update(
            offer_id,
            {
                "cv_path": str(cv_path),
                "cover_letter_path": str(cl_path),
                "prep_sheet_path": str(prep_path) if prep_path else "",
            },
            user_id=user_id,
        )
        _status[offer_id] = "done"
        _stage[offer_id] = ""
    finally:
        conn.close()


def start_prepare(offer_id: int, user_id: str, skip_prep: bool) -> None:
    """Set state to running and enqueue the prepare task for this offer.
    No-op if a prepare is already running for this offer."""
    if _status.get(offer_id) == "running":
        return
    _status[offer_id] = "running"
    _stage[offer_id] = ""
    _error[offer_id] = ""
    asyncio.create_task(_run_prepare(offer_id, user_id, skip_prep))
