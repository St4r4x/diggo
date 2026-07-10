from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

import llm


def test_call_llm_uses_first_provider_when_it_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "_call_openai_compatible", lambda *a, **k: "first answer")

    result = llm.call_llm([("huggingface", "hf_token")], "system", "user")
    assert result == "first answer"


def test_call_llm_falls_back_to_second_provider_on_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def _fake_call(provider, api_key, system_prompt, user_prompt, json_mode):
        calls.append(provider)
        if provider == "huggingface":
            raise llm.OpenAIError("network down")
        return "groq answer"

    monkeypatch.setattr(llm, "_call_openai_compatible", _fake_call)

    result = llm.call_llm(
        [("huggingface", "hf_token"), ("groq", "groq_key")], "system", "user"
    )
    assert result == "groq answer"
    assert calls == ["huggingface", "groq"]


def test_call_llm_falls_back_to_second_provider_on_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def _fake_call(provider, api_key, system_prompt, user_prompt, json_mode):
        calls.append(provider)
        if provider == "huggingface":
            raise llm.AuthenticationError(
                message="bad key", response=_fake_response(401), body=None
            )
        return "groq answer"

    monkeypatch.setattr(llm, "_call_openai_compatible", _fake_call)

    result = llm.call_llm(
        [("huggingface", "hf_token"), ("groq", "groq_key")], "system", "user"
    )
    assert result == "groq answer"
    assert calls == ["huggingface", "groq"]


def test_call_llm_dispatches_anthropic_to_its_own_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []

    def _fake_anthropic(api_key, system_prompt, user_prompt, json_mode):
        seen.append(api_key)
        return "claude answer"

    monkeypatch.setattr(llm, "_call_anthropic", _fake_anthropic)

    result = llm.call_llm([("anthropic", "sk-ant-key")], "system", "user")
    assert result == "claude answer"
    assert seen == ["sk-ant-key"]


def test_call_llm_raises_llm_error_when_all_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _always_fail(provider, api_key, system_prompt, user_prompt, json_mode):
        raise llm.OpenAIError(f"{provider} is down")

    monkeypatch.setattr(llm, "_call_openai_compatible", _always_fail)

    with pytest.raises(llm.LLMError):
        llm.call_llm(
            [("huggingface", "hf_token"), ("groq", "groq_key")], "system", "user"
        )


def test_call_llm_raises_llm_error_immediately_when_no_providers() -> None:
    with pytest.raises(llm.LLMError, match="Aucun fournisseur"):
        llm.call_llm([], "system", "user")


def test_call_llm_appends_json_schema_hint_to_user_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_prompts = []

    def _capture(provider, api_key, system_prompt, user_prompt, json_mode):
        seen_prompts.append(user_prompt)
        return "{}"

    monkeypatch.setattr(llm, "_call_openai_compatible", _capture)
    llm.call_llm(
        [("huggingface", "hf_token")],
        "system",
        "user",
        json_schema={"foo": "bar"},
    )
    assert '"foo": "bar"' in seen_prompts[0]


def test_validate_provider_key_succeeds_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return None

    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: _FakeClient())
    llm.validate_provider_key("huggingface", "hf_valid_token")  # should not raise


def _fake_response(status_code: int):
    import httpx

    request = httpx.Request("POST", "https://router.huggingface.co/v1/chat/completions")
    return httpx.Response(status_code, request=request)


def test_validate_provider_key_raises_llm_error_on_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_auth_error(**kwargs):
        raise llm.AuthenticationError(
            message="invalid token", response=_fake_response(401), body=None
        )

    class _FakeClient:
        class chat:
            class completions:
                create = staticmethod(_raise_auth_error)

    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: _FakeClient())
    with pytest.raises(llm.LLMError, match="invalide"):
        llm.validate_provider_key("huggingface", "hf_bad_token")


def test_validate_provider_key_raises_llm_error_on_missing_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_permission_error(**kwargs):
        raise llm.PermissionDeniedError(
            message="no inference permission", response=_fake_response(403), body=None
        )

    class _FakeClient:
        class chat:
            class completions:
                create = staticmethod(_raise_permission_error)

    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: _FakeClient())
    with pytest.raises(llm.LLMError, match="permission"):
        llm.validate_provider_key(
            "huggingface", "hf_token_without_inference_permission"
        )


def test_validate_provider_key_raises_llm_error_on_other_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_generic_error(**kwargs):
        raise llm.OpenAIError("network down")

    class _FakeClient:
        class chat:
            class completions:
                create = staticmethod(_raise_generic_error)

    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: _FakeClient())
    with pytest.raises(llm.LLMError, match="réessaie"):
        llm.validate_provider_key("huggingface", "hf_some_token")


_CANNED_ANALYSIS = {
    "top_skills": ["PyTorch", "Kubernetes", "RAG"],
    "keywords": ["MLOps", "production ML"],
    "company_context": "AI startup building developer tools, ~40 people, Python stack.",
    "gaps": ["Kubernetes"],
    "hook_angle": "They open-sourced their inference engine, which I've used personally.",
    "offer_language": "en",
    "requires_english_cv": True,
}


def test_analyze_offer_parses_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(_CANNED_ANALYSIS))
    offer = {
        "company": "Acme",
        "role": "ML Engineer",
        "description": "We need PyTorch...",
    }

    analysis = llm.analyze_offer([("huggingface", "test-hf-token")], offer)

    assert analysis.top_skills == ["PyTorch", "Kubernetes", "RAG"]
    assert analysis.offer_language == "en"
    assert analysis.requires_english_cv is True
    assert analysis.gaps == ["Kubernetes"]


_SAMPLE_CV = {
    "meta": {"summary": "AI engineer with a background in sales."},
    "experience": [
        {
            "id": 1,
            "title": "AI Engineer",
            "company": "Missia",
            "bullets": ["Built RAG pipelines"],
        }
    ],
    "skills": [
        {"id": 1, "category": "ML", "skill": "PyTorch", "sort_order": 0},
        {"id": 2, "category": "ML", "skill": "scikit-learn", "sort_order": 1},
    ],
    "certifications": [],
    "education": [],
}


def test_rewrite_cv_summary_keeps_known_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    canned = {"highlighted_skills": ["PyTorch"], "summary": "Tailored summary."}
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))
    analysis = llm.OfferAnalysis(
        top_skills=["PyTorch"],
        keywords=[],
        company_context="",
        gaps=[],
        hook_angle="",
        offer_language="fr",
        requires_english_cv=False,
    )

    result = llm.rewrite_cv_summary(
        [("huggingface", "test-hf-token")], {}, _SAMPLE_CV, analysis
    )

    assert result.highlighted_skills == ["PyTorch"]
    assert result.summary == "Tailored summary."


def test_rewrite_cv_summary_drops_unknown_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "highlighted_skills": ["PyTorch", "Kubernetes"],
        "summary": "Tailored summary.",
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))
    analysis = llm.OfferAnalysis(
        top_skills=["PyTorch", "Kubernetes"],
        keywords=[],
        company_context="",
        gaps=["Kubernetes"],
        hook_angle="",
        offer_language="fr",
        requires_english_cv=False,
    )

    result = llm.rewrite_cv_summary(
        [("huggingface", "test-hf-token")], {}, _SAMPLE_CV, analysis
    )

    assert result.highlighted_skills == ["PyTorch"]


_SAMPLE_OFFER = {"company": "Acme", "role": "ML Engineer", "description": "..."}


def _analysis(lang: str = "fr") -> "llm.OfferAnalysis":
    return llm.OfferAnalysis(
        top_skills=["PyTorch"],
        keywords=["MLOps"],
        company_context="AI startup.",
        gaps=[],
        hook_angle="Their open-source inference engine.",
        offer_language=lang,
        requires_english_cv=False,
    )


def test_write_cover_letter_accepts_valid_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "paragraphs": ["Hook.", "Proof.", "Close."],
        "citations": [{"claim": "Built RAG pipelines", "experience_id": 1}],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    result = llm.write_cover_letter(
        [("huggingface", "test-hf-token")], {}, _SAMPLE_CV, _SAMPLE_OFFER, _analysis()
    )

    assert result.paragraphs == ["Hook.", "Proof.", "Close."]
    assert result.citations[0]["experience_id"] == 1


def test_write_cover_letter_retries_once_on_invalid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        _json.dumps(
            {
                "paragraphs": ["Hook.", "Proof.", "Close."],
                "citations": [{"claim": "Invented claim", "experience_id": 999}],
            }
        ),
        _json.dumps(
            {
                "paragraphs": ["Hook.", "Proof fixed.", "Close."],
                "citations": [{"claim": "Built RAG pipelines", "experience_id": 1}],
            }
        ),
    ]
    calls = []

    def _fake_call_llm(
        providers: list, system_prompt: str, user_prompt: str, **kwargs: object
    ) -> str:
        calls.append(user_prompt)
        return responses[len(calls) - 1]

    monkeypatch.setattr(llm, "call_llm", _fake_call_llm)

    result = llm.write_cover_letter(
        [("huggingface", "test-hf-token")], {}, _SAMPLE_CV, _SAMPLE_OFFER, _analysis()
    )

    assert len(calls) == 2
    assert "999" in calls[1]
    assert result.paragraphs == ["Hook.", "Proof fixed.", "Close."]


def test_write_cover_letter_raises_grounding_error_after_second_invalid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "paragraphs": ["Hook.", "Proof.", "Close."],
        "citations": [{"claim": "Invented claim", "experience_id": 999}],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    with pytest.raises(llm.GroundingError):
        llm.write_cover_letter(
            [("huggingface", "test-hf-token")],
            {},
            _SAMPLE_CV,
            _SAMPLE_OFFER,
            _analysis(),
        )


def test_generate_prep_questions_parses_llm_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "company_summary": "AI startup building developer tools.",
        "tech_stack": ["Python", "Kubernetes"],
        "questions": [
            {
                "theme": "Technique ML",
                "question": "How would you deploy a RAG pipeline?",
            },
            {"theme": "MLOps", "question": "How do you monitor model drift?"},
        ],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    result = llm.generate_prep_questions(
        [("huggingface", "test-hf-token")], _SAMPLE_OFFER, _analysis()
    )

    assert result.company_summary == "AI startup building developer tools."
    assert result.tech_stack == ["Python", "Kubernetes"]
    assert len(result.questions) == 2
    assert result.questions[0]["theme"] == "Technique ML"
