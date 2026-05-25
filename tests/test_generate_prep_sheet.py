"""Tests for generate_prep_sheet pure helpers (no PDF write, no filesystem)."""

from scripts.generate_prep_sheet import build_prep_sheet_context, render_html


def test_build_prep_sheet_context_returns_required_keys():
    ctx = build_prep_sheet_context(
        company="Mistral AI",
        role="AI Engineer",
        date_str="2026-05-25",
        company_summary="Mistral AI builds frontier open-weight LLMs.",
        tech_stack=["Python", "PyTorch", "vLLM"],
        questions=[
            {
                "theme": "Technique ML",
                "question": "Expliquez la différence entre RLHF et DPO.",
            },
            {
                "theme": "Comportemental",
                "question": "Décrivez un projet complexe que vous avez mené.",
            },
        ],
    )
    assert ctx["company"] == "Mistral AI"
    assert ctx["role"] == "AI Engineer"
    assert ctx["date_str"] == "2026-05-25"
    assert ctx["company_summary"] == "Mistral AI builds frontier open-weight LLMs."
    assert ctx["tech_stack"] == ["Python", "PyTorch", "vLLM"]
    assert len(ctx["questions"]) == 2
    assert ctx["questions"][0]["theme"] == "Technique ML"


def test_render_html_contains_company_and_role():
    ctx = build_prep_sheet_context(
        company="Mistral AI",
        role="AI Engineer",
        date_str="2026-05-25",
        company_summary="Mistral AI builds frontier open-weight LLMs.",
        tech_stack=["Python", "PyTorch"],
        questions=[
            {"theme": "ML", "question": "What is attention?"},
        ],
    )
    html = render_html(ctx)
    assert "Mistral AI" in html
    assert "AI Engineer" in html


def test_render_html_contains_all_tech_badges():
    ctx = build_prep_sheet_context(
        company="Acme",
        role="Dev",
        date_str="2026-05-25",
        company_summary="Summary.",
        tech_stack=["Rust", "Go", "Python"],
        questions=[{"theme": "T", "question": "Q?"}],
    )
    html = render_html(ctx)
    assert "Rust" in html
    assert "Go" in html
    assert "Python" in html


def test_render_html_contains_all_questions():
    questions = [
        {"theme": "ML", "question": "Explain backpropagation."},
        {"theme": "Soft", "question": "Tell me about a failure."},
    ]
    ctx = build_prep_sheet_context(
        company="Acme",
        role="Dev",
        date_str="2026-05-25",
        company_summary="Summary.",
        tech_stack=[],
        questions=questions,
    )
    html = render_html(ctx)
    assert "Explain backpropagation." in html
    assert "Tell me about a failure." in html
    assert "ML" in html
    assert "Soft" in html


def test_render_html_contains_company_summary():
    ctx = build_prep_sheet_context(
        company="Acme",
        role="Dev",
        date_str="2026-05-25",
        company_summary="Acme is a leading widget manufacturer.",
        tech_stack=[],
        questions=[{"theme": "T", "question": "Q?"}],
    )
    html = render_html(ctx)
    assert "Acme is a leading widget manufacturer." in html
