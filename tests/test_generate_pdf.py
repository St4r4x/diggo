# tests/test_generate_pdf.py
from scripts.generate_pdf import _normalize_for_ats, build_cv_context, render_html


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
