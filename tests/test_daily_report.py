"""Tests for daily_report module."""

from __future__ import annotations

from datetime import date
from pathlib import Path


from scripts.daily_report import render_report, report_path
from scripts.models import RawOffer


def _offer(
    title: str,
    company: str,
    portal: str = "wtfj",
    score: float = 4.0,
    location: str = "Paris",
    url: str = "https://example.com/offer",
) -> RawOffer:
    offer = RawOffer(
        title=title,
        company=company,
        url=url,
        portal=portal,
        location=location,
        date_posted=date(2026, 5, 25),
        score=score,
        tags=["AI Engineer", "target:Mistral AI"],
    )
    return offer


class TestReportPath:
    """Tests for report_path()."""

    def test_returns_path_object(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert isinstance(p, Path)

    def test_filename_format(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert p.name == "daily-2026-05-25.md"

    def test_parent_is_reports_dir(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert p.parent.name == "reports"


class TestRenderReport:
    """Tests for render_report()."""

    def test_empty_offers_produces_valid_markdown(self) -> None:
        md = render_report([], report_date=date(2026, 5, 25))
        assert "# Daily Report" in md
        assert "2026-05-25" in md
        assert "No offers" in md or "0 offer" in md

    def test_offer_title_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "AI Engineer" in md

    def test_offer_company_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Mistral AI" in md

    def test_offer_url_in_output(self) -> None:
        offers = [
            _offer("AI Engineer", "Mistral AI", url="https://example.com/offer/42")
        ]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "https://example.com/offer/42" in md

    def test_offer_score_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", score=4.5)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "4.5" in md

    def test_offers_sorted_by_score_descending(self) -> None:
        offers = [
            _offer("B offer", "Corp B", score=3.5),
            _offer("A offer", "Corp A", score=4.5),
            _offer("C offer", "Corp C", score=3.0),
        ]
        md = render_report(offers, report_date=date(2026, 5, 25))
        pos_a = md.index("A offer")
        pos_b = md.index("B offer")
        pos_c = md.index("C offer")
        assert pos_a < pos_b < pos_c

    def test_portal_label_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", portal="apec")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "apec" in md.lower()

    def test_total_count_in_header(self) -> None:
        offers = [
            _offer("AI Engineer", "Mistral AI"),
            _offer("ML Engineer", "Hugging Face"),
        ]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "2" in md

    def test_recommend_section_present(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", score=4.5)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Recommend" in md or "recommend" in md

    def test_consider_section_present(self) -> None:
        offers = [_offer("ML Engineer", "Hugging Face", score=3.2)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Consider" in md or "consider" in md
