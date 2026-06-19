# tests/test_generate_pdf.py

import pytest

from scripts.generate_pdf import _normalize_for_ats, build_cv_context, render_html


def _base_ctx(**overrides: object) -> dict:
    defaults = dict(
        name="Your Name",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        summary="Test summary.",
        experience=[],
        skill_categories={"Langages": ["Python", "Docker"]},
        highlighted_skills=["Python"],
        education=[],
        languages=["Français", "English"],
    )
    defaults.update(overrides)
    return build_cv_context(**defaults)


def test_build_cv_context_returns_required_keys():
    ctx = _base_ctx()
    assert ctx["name"] == "Your Name"
    assert ctx["skill_categories"] == {"Langages": ["Python", "Docker"]}
    assert "Python" in ctx["highlighted_skills"]


def test_build_cv_context_certifications_default_none():
    ctx = _base_ctx()
    assert ctx["certifications"] is None


def test_build_cv_context_certifications_present():
    certs = [{"name": "AWS Dev", "issuer": "Amazon", "year": 2024}]
    ctx = _base_ctx(certifications=certs)
    assert ctx["certifications"] == certs


def test_render_html_contains_name():
    ctx = _base_ctx(name="Your Name", title="AI/ML Engineer", summary="")
    html = render_html(ctx)
    assert "Your Name" in html
    assert "AI/ML Engineer" in html


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_render_html_skills_by_category(lang: str) -> None:
    ctx = _base_ctx(
        skill_categories={"IA/ML": ["PyTorch"], "Langages": ["Python"]},
        highlighted_skills=["PyTorch"],
    )
    html = render_html(ctx, lang=lang)
    assert "PyTorch" in html
    assert "Python" in html
    assert "IA/ML" in html


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_render_html_certifications_shown(lang: str) -> None:
    certs = [{"name": "AWS Dev", "issuer": "Amazon", "year": 2024}]
    ctx = _base_ctx(certifications=certs)
    html = render_html(ctx, lang=lang)
    assert "AWS Dev" in html
    assert "Amazon" in html


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_render_html_certifications_absent(lang: str) -> None:
    ctx = _base_ctx(certifications=None)
    html = render_html(ctx, lang=lang)
    assert "Certifications" not in html


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_render_html_stack_tags_shown(lang: str) -> None:
    job = {
        "title": "AI Engineer",
        "company": "Acme",
        "type": "CDI",
        "period": "2024",
        "bullets": ["Did stuff"],
        "stack": ["Python", "FastAPI"],
    }
    ctx = _base_ctx(experience=[job])
    html = render_html(ctx, lang=lang)
    assert "FastAPI" in html


def test_render_html_stack_absent():
    job = {
        "title": "AI Engineer",
        "company": "Acme",
        "type": "CDI",
        "period": "2024",
        "bullets": ["Did stuff"],
    }
    ctx = _base_ctx(experience=[job])
    html = render_html(ctx)
    # no stack field → no stack-tag div
    assert "stack-tag" not in html


class TestNormalizeForAts:
    def test_em_dash_replaced(self) -> None:
        assert _normalize_for_ats("foo—bar") == "foo--bar"

    def test_en_dash_replaced(self) -> None:
        assert _normalize_for_ats("foo–bar") == "foo-bar"

    def test_smart_quotes_replaced(self) -> None:
        result = _normalize_for_ats("“foo”")
        assert result == '"foo"'

    def test_zero_width_removed(self) -> None:
        assert _normalize_for_ats("foo​bar") == "foobar"

    def test_style_block_preserved(self) -> None:
        html = "<style>.em—dash { color: red; }</style>normal—text"
        result = _normalize_for_ats(html)
        assert "—" in result  # dash inside style preserved
        assert result.endswith("normal--text")

    def test_plain_text_unchanged(self) -> None:
        assert _normalize_for_ats("Hello world") == "Hello world"
