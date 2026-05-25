"""Tests for scan_portals pure parsing helpers."""

from __future__ import annotations

from datetime import date


from scripts.scan_portals import (
    build_search_url,
    extract_offer_from_card_data,
    parse_date_string,
)


class TestParseDateString:
    def test_iso_format(self) -> None:
        assert parse_date_string("2026-05-20") == date(2026, 5, 20)

    def test_french_format_with_month_name(self) -> None:
        result = parse_date_string("20 mai 2026")
        assert result == date(2026, 5, 20)

    def test_relative_today(self) -> None:
        result = parse_date_string("Aujourd'hui")
        assert result == date.today()

    def test_relative_yesterday(self) -> None:
        from datetime import timedelta

        result = parse_date_string("Hier")
        assert result == date.today() - timedelta(days=1)

    def test_unknown_string_returns_none(self) -> None:
        assert parse_date_string("n/a") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_date_string("") is None


class TestBuildSearchUrl:
    def test_simple_substitution(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(template, keywords="AI Engineer", location="Paris")
        assert "AI+Engineer" in url or "AI%20Engineer" in url or "AI Engineer" in url
        assert "Paris" in url

    def test_multi_word_keywords_encoded(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(
            template, keywords="Machine Learning Engineer", location="Lyon"
        )
        assert " " not in url.split("?")[1]

    def test_special_chars_encoded(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(template, keywords="C++ Developer", location="Paris")
        assert " " not in url.split("?")[1]


class TestExtractOfferFromCardData:
    def test_full_data_returns_raw_offer(self) -> None:
        from scripts.models import RawOffer

        card_data = {
            "title": "AI Engineer",
            "company": "Mistral AI",
            "url": "https://example.com/offer/123",
            "location": "Paris",
            "date": "2026-05-20",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="wtfj")
        assert isinstance(offer, RawOffer)
        assert offer.title == "AI Engineer"
        assert offer.company == "Mistral AI"
        assert offer.portal == "wtfj"
        assert offer.date_posted == date(2026, 5, 20)

    def test_missing_optional_fields_produce_none(self) -> None:
        card_data = {
            "title": "ML Engineer",
            "company": "Hugging Face",
            "url": "https://example.com/offer/456",
            "location": "",
            "date": "",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="indeed")
        assert offer.location is None
        assert offer.date_posted is None

    def test_title_and_company_stripped(self) -> None:
        card_data = {
            "title": "  LLM Engineer  ",
            "company": "  Nabla  ",
            "url": "https://example.com/offer/789",
            "location": "Paris",
            "date": "",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="apec")
        assert offer.title == "LLM Engineer"
        assert offer.company == "Nabla"

    def test_relative_url_with_base_is_made_absolute(self) -> None:
        card_data = {
            "title": "NLP Engineer",
            "company": "Yseop",
            "url": "/fr/jobs/nlp-engineer-yseop",
            "location": "Paris",
            "date": "",
        }
        offer = extract_offer_from_card_data(
            card_data, portal_id="wtfj", base_url="https://www.welcometothejungle.com"
        )
        assert offer.url.startswith("https://")

    def test_returns_none_when_title_missing(self) -> None:
        card_data = {
            "title": "",
            "company": "SomeCompany",
            "url": "https://example.com/offer/999",
            "location": "Paris",
            "date": "",
        }
        result = extract_offer_from_card_data(card_data, portal_id="wtfj")
        assert result is None


class TestPortalIsActive:
    def test_active_status_returns_true(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "active"}) is True

    def test_needs_auth_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "needs_auth"}) is False

    def test_blocked_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "blocked"}) is False

    def test_missing_status_defaults_to_active(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({}) is True

    def test_unknown_status_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "maintenance"}) is False


class TestEffectiveMaxPages:
    def test_override_takes_precedence(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=1) == 1

    def test_yaml_value_used_when_no_override(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=None) == 5

    def test_defaults_to_3_when_not_in_yaml(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {}}
        assert _effective_max_pages(config, max_pages_override=None) == 3

    def test_override_zero_is_respected(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=0) == 0
