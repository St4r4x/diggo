"""Tests for generate_cover_letter pure helpers (no PDF write, no filesystem)."""

from scripts.generate_cover_letter import build_cover_letter_context, render_html


def test_build_cover_letter_context_returns_required_keys():
    ctx = build_cover_letter_context(
        name="Your Name",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Mistral AI",
        role="AI Engineer",
        recipient="Madame, Monsieur,",
        paragraphs=["Para 1.", "Para 2.", "Para 3."],
    )
    assert ctx["name"] == "Your Name"
    assert ctx["company"] == "Mistral AI"
    assert ctx["role"] == "AI Engineer"
    assert ctx["paragraphs"] == ["Para 1.", "Para 2.", "Para 3."]


def test_render_html_contains_name_and_company():
    ctx = build_cover_letter_context(
        name="Your Name",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Mistral AI",
        role="AI Engineer",
        recipient="Madame, Monsieur,",
        paragraphs=["First paragraph.", "Second paragraph.", "Third paragraph."],
    )
    html = render_html(ctx)
    assert "Your Name" in html
    assert "Mistral AI" in html
    assert "AI Engineer" in html
    assert "First paragraph." in html


def test_render_html_contains_all_paragraphs():
    paragraphs = ["Para A.", "Para B.", "Para C."]
    ctx = build_cover_letter_context(
        name="Test",
        title="Engineer",
        email="a@b.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Acme",
        role="Dev",
        recipient="Madame, Monsieur,",
        paragraphs=paragraphs,
    )
    html = render_html(ctx)
    for para in paragraphs:
        assert para in html


def test_render_html_empty_role_omits_role_div():
    ctx = build_cover_letter_context(
        name="Test",
        title="Engineer",
        email="a@b.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Acme",
        role="",
        recipient="Madame, Monsieur,",
        paragraphs=["Only para."],
    )
    html = render_html(ctx)
    assert "Acme" in html
    assert 'class="role"' not in html


def test_default_context_contains_required_keys():
    from scripts.generate_cover_letter import default_context

    ctx = default_context(company="Acme", role="Dev")
    assert ctx["company"] == "Acme"
    assert ctx["role"] == "Dev"
    assert "name" in ctx
    assert "email" in ctx
    assert len(ctx["paragraphs"]) == 3
