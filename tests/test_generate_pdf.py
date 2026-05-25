# tests/test_generate_pdf.py
from scripts.generate_pdf import build_cv_context, render_html


def test_build_cv_context_returns_required_keys():
    ctx = build_cv_context(
        name="Your Name",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        summary="Test summary.",
        experience=[],
        skills=["Python", "Docker"],
        highlighted_skills=["Python"],
        education=[],
        languages=["Français", "English"],
    )
    assert ctx["name"] == "Your Name"
    assert "Python" in ctx["skills"]
    assert "Python" in ctx["highlighted_skills"]


def test_render_html_contains_name():
    ctx = build_cv_context(
        name="Your Name",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        summary="",
        experience=[],
        skills=["Python"],
        highlighted_skills=[],
        education=[],
        languages=[],
    )
    html = render_html(ctx)
    assert "Your Name" in html
    assert "AI/ML Engineer" in html
