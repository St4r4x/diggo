"""LLM client and phase functions for server-side candidature prep.

Hugging Face Inference Providers (openai/gpt-oss-120b) is the primary provider,
via HF's OpenAI-compatible router. On any failure (timeout, 5xx, quota) this
falls back transparently to Gemini Flash.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

_HF_MODEL = "openai/gpt-oss-120b:fastest"
_GEMINI_MODEL = "gemini-2.5-flash"


class LLMError(Exception):
    """Raised when both Hugging Face and Gemini fail to answer."""


class GroundingError(Exception):
    """Raised when a cover letter still cites an unknown experience_id after retry."""


def _call_hf(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    client = OpenAI(
        api_key=os.environ["HF_TOKEN"],
        base_url="https://router.huggingface.co/v1",
    )
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=_HF_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return response.choices[0].message.content or ""


def _call_gemini(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json" if json_mode else None,
    )
    response = client.models.generate_content(
        model=_GEMINI_MODEL, contents=user_prompt, config=config
    )
    return response.text or ""


def call_llm(
    system_prompt: str, user_prompt: str, *, json_schema: dict | None = None
) -> str:
    """Call Hugging Face first; fall back to Gemini on any failure. Logs which provider answered."""
    json_mode = json_schema is not None
    if json_mode:
        user_prompt = (
            f"{user_prompt}\n\nRespond with a JSON object matching this shape: "
            f"{json.dumps(json_schema)}"
        )
    try:
        result = _call_hf(system_prompt, user_prompt, json_mode)
        logger.info("llm: answered by huggingface")
        return result
    except OpenAIError as exc:
        logger.warning("llm: huggingface failed (%s), falling back to gemini", exc)
    try:
        result = _call_gemini(system_prompt, user_prompt, json_mode)
        logger.info("llm: answered by gemini")
        return result
    except Exception as exc:
        # Any Gemini SDK failure here means both providers are down.
        raise LLMError(f"Both Hugging Face and Gemini failed: {exc}") from exc


@dataclass
class OfferAnalysis:
    top_skills: list[str]
    keywords: list[str]
    company_context: str
    gaps: list[str]
    hook_angle: str
    offer_language: str
    requires_english_cv: bool


_ANALYZE_OFFER_SCHEMA = {
    "top_skills": ["string"],
    "keywords": ["string"],
    "company_context": "string",
    "gaps": ["string"],
    "hook_angle": "string",
    "offer_language": "'fr' or 'en'",
    "requires_english_cv": "boolean",
}

_ANALYZE_OFFER_SYSTEM_PROMPT = (
    "You are a career coach analyzing a job posting for a candidate preparing an "
    "application. Extract only what is explicitly present in the posting text, "
    "never invent requirements."
)


def analyze_offer(offer: dict[str, Any]) -> OfferAnalysis:
    user_prompt = (
        f"Job posting for {offer.get('role', '')} at {offer.get('company', '')}:\n\n"
        f"{offer.get('description', '')}\n\n"
        "Extract 5-7 top_skills (exact terms from the posting), keywords, a "
        "company_context (mission, product, size, stack), gaps (skills a typical "
        "candidate profile might be missing based on the posting), a hook_angle "
        "(one concrete why-this-company reason, not generic), the offer_language "
        "('fr' or 'en'), and requires_english_cv (true only if the posting "
        "explicitly asks for an English-language CV/resume submission, not merely "
        "English fluency)."
    )
    raw = call_llm(
        _ANALYZE_OFFER_SYSTEM_PROMPT, user_prompt, json_schema=_ANALYZE_OFFER_SCHEMA
    )
    data = json.loads(raw)
    return OfferAnalysis(
        top_skills=list(data["top_skills"]),
        keywords=list(data["keywords"]),
        company_context=str(data["company_context"]),
        gaps=list(data["gaps"]),
        hook_angle=str(data["hook_angle"]),
        offer_language=str(data["offer_language"]),
        requires_english_cv=bool(data["requires_english_cv"]),
    )


@dataclass
class CvRewrite:
    highlighted_skills: list[str]
    summary: str


_REWRITE_CV_SUMMARY_SCHEMA = {"highlighted_skills": ["string"], "summary": "string"}

_REWRITE_CV_SUMMARY_SYSTEM_PROMPT = (
    "You rewrite a candidate's CV summary to mirror a specific job posting. "
    "Never invent skills the candidate doesn't have."
)


def rewrite_cv_summary(
    profile: dict[str, Any], cv: dict[str, Any], analysis: OfferAnalysis
) -> CvRewrite:
    known_skills = [s["skill"] for s in cv.get("skills", [])]
    lang = "English" if analysis.requires_english_cv else "French"
    user_prompt = (
        f"Candidate's known skills: {known_skills}\n"
        f"Candidate's current CV summary: {cv.get('meta', {}).get('summary', '')}\n"
        f"Target offer top_skills: {analysis.top_skills}\n"
        f"Target offer keywords: {analysis.keywords}\n\n"
        "Pick highlighted_skills: a subset of the candidate's known skills above "
        "that match the offer's top_skills (never invent a skill not in the known "
        f"list). Write a 2-sentence summary in {lang} mirroring the offer's role "
        "and domain."
    )
    raw = call_llm(
        _REWRITE_CV_SUMMARY_SYSTEM_PROMPT,
        user_prompt,
        json_schema=_REWRITE_CV_SUMMARY_SCHEMA,
    )
    data = json.loads(raw)
    valid_skills = set(known_skills)
    highlighted = [s for s in data["highlighted_skills"] if s in valid_skills]
    return CvRewrite(highlighted_skills=highlighted, summary=str(data["summary"]))


@dataclass
class CoverLetterDraft:
    paragraphs: list[str]
    citations: list[dict[str, Any]]


_COVER_LETTER_SCHEMA = {
    "paragraphs": ["string", "string", "string"],
    "citations": [{"claim": "string", "experience_id": 0}],
}

_BANNED_PHRASES = [
    "Je suis très motivé",
    "passionné par",
    "je me permets de",
    "dans l'espoir de",
    "à fort impact",
    "de bout en bout",
    "production-first",
    "rigueur technique",
    "mettre mes compétences au service de",
    "je serais ravi d'échanger sur la façon dont",
    "dans l'attente de votre retour",
]

_PIVOT_SENTENCE = {
    "fr": (
        "Une reconversion délibérée : 8 ans à manager une équipe commerciale, "
        "puis formation en AI engineering, me permet d'allier profondeur "
        "technique et capacité à travailler avec des interlocuteurs non "
        "techniques."
    ),
    "en": (
        "A deliberate pivot: eight years leading a sales team, then "
        "retraining as an AI engineer, means I bring both technical depth "
        "and the communication skills to work directly with non-technical "
        "stakeholders."
    ),
}

_COVER_LETTER_SYSTEM_PROMPT = (
    "You write cover letters for a candidate who pivoted from 8 years in "
    "sales management to AI engineering. Every claim of professional "
    "accomplishment must cite an experience_id from the provided experience "
    "list, never invent one. Never use these phrases: "
    + "; ".join(_BANNED_PHRASES)
    + ". No em-dashes or en-dashes; use commas, periods, colons, or rephrase."
)


def write_cover_letter(
    profile: dict[str, Any],
    cv: dict[str, Any],
    offer: dict[str, Any],
    analysis: OfferAnalysis,
) -> CoverLetterDraft:
    experiences = [
        {
            "experience_id": e["id"],
            "title": e.get("title", ""),
            "company": e.get("company", ""),
            "bullets": e.get("bullets", []),
        }
        for e in cv.get("experience", [])
    ]
    valid_ids = {e["id"] for e in cv.get("experience", [])}
    lang = analysis.offer_language
    pivot = _PIVOT_SENTENCE.get(lang, _PIVOT_SENTENCE["fr"])
    base_user_prompt = (
        f"Company: {offer.get('company', '')}\nRole: {offer.get('role', '')}\n"
        f"Company context: {analysis.company_context}\n"
        f"Hook angle: {analysis.hook_angle}\n"
        f"Candidate's experience (cite only these experience_id values): "
        f"{experiences}\n\n"
        f"Write in {lang}. 3 paragraphs, under 300 words total:\n"
        "1. Hook: one concrete reason tied to the hook_angle, never generic.\n"
        "2. Proof: 2 specific experiences from the list above, each backed by "
        "a citation.\n"
        f'3. Close: include this sentence verbatim: "{pivot}" then mention '
        "availability.\n"
        "Return citations as a list of {claim, experience_id} for every "
        "accomplishment claim."
    )
    user_prompt = base_user_prompt
    invalid: list[dict[str, Any]] = []
    for attempt in range(2):
        raw = call_llm(
            _COVER_LETTER_SYSTEM_PROMPT, user_prompt, json_schema=_COVER_LETTER_SCHEMA
        )
        data = json.loads(raw)
        citations = list(data.get("citations", []))
        invalid = [c for c in citations if c.get("experience_id") not in valid_ids]
        if not invalid:
            return CoverLetterDraft(
                paragraphs=list(data["paragraphs"]), citations=citations
            )
        if attempt == 0:
            bad_ids = [c.get("experience_id") for c in invalid]
            user_prompt = (
                base_user_prompt
                + f"\n\nYour previous answer cited experience_id {bad_ids}, "
                f"which do not exist. Only cite from this list: "
                f"{sorted(valid_ids)}."
            )
    raise GroundingError(
        f"Cover letter still cites invalid experience_id after retry: {invalid}"
    )


@dataclass
class PrepSheetDraft:
    company_summary: str
    tech_stack: list[str]
    questions: list[dict[str, str]]


_PREP_SHEET_SCHEMA = {
    "company_summary": "string",
    "tech_stack": ["string"],
    "questions": [{"theme": "string", "question": "string"}],
}

_PREP_SHEET_SYSTEM_PROMPT = (
    "You write interview prep sheets: a company summary and 8-12 interview "
    "questions covering technical depth, MLOps/deployment, behavioural (STAR "
    "format), and why-this-role."
)


def generate_prep_questions(
    offer: dict[str, Any], analysis: OfferAnalysis
) -> PrepSheetDraft:
    user_prompt = (
        f"Company: {offer.get('company', '')}\nRole: {offer.get('role', '')}\n"
        f"Company context: {analysis.company_context}\n"
        f"Top skills required: {analysis.top_skills}\n\n"
        "Write a 2-3 sentence company_summary, a tech_stack list, and 8-12 "
        "questions covering technical depth (linked to top_skills), "
        "MLOps/deployment, behavioural, and why-us/why-this-role."
    )
    raw = call_llm(
        _PREP_SHEET_SYSTEM_PROMPT, user_prompt, json_schema=_PREP_SHEET_SCHEMA
    )
    data = json.loads(raw)
    return PrepSheetDraft(
        company_summary=str(data["company_summary"]),
        tech_stack=list(data["tech_stack"]),
        questions=list(data["questions"]),
    )
