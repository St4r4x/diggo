"""Tests for pre_filter module."""

from __future__ import annotations

import pytest

from scripts.models import RawOffer
from scripts.pre_filter import score_offer, pre_filter


MOCK_SETTINGS = {
    "search": {
        "keywords": ["AI Engineer", "ML Engineer", "LLM Engineer"],
        "location": "Paris",
    },
    "scoring": {
        "thresholds": {"recommend": 4.0, "consider": 3.0},
        "target_salary_min": 40000,
        "target_salary_max": 55000,
    },
    "target_companies": {
        "french_ai": ["Mistral AI", "Hugging Face"],
        "big_tech": ["Google", "Meta"],
    },
}


def _offer(
    title: str, company: str = "Unknown Corp", location: str = "Paris"
) -> RawOffer:
    return RawOffer(
        title=title,
        company=company,
        url="https://x.com",
        portal="wtfj",
        location=location,
    )


class TestScoreOffer:
    """Tests for score_offer()."""

    def test_perfect_match_scores_high(self) -> None:
        offer = _offer("AI Engineer", company="Mistral AI", location="Paris")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        # keyword match (+1) + target company (+1) + location (+1) = 3.0 minimum
        assert score >= 3.0

    def test_no_keyword_match_scores_low(self) -> None:
        offer = _offer("Java Developer", company="Random Corp", location="Lyon")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        assert score < 3.0

    def test_keyword_match_adds_to_score(self) -> None:
        offer_match = _offer("ML Engineer", company="Unknown", location="Lyon")
        offer_no = _offer("Java Developer", company="Unknown", location="Lyon")
        score_match, _ = score_offer(offer_match, MOCK_SETTINGS)
        score_no, _ = score_offer(offer_no, MOCK_SETTINGS)
        assert score_match > score_no

    def test_target_company_adds_to_score(self) -> None:
        offer_target = _offer("ML Engineer", company="Mistral AI", location="Lyon")
        offer_other = _offer("ML Engineer", company="Random Corp", location="Lyon")
        score_t, _ = score_offer(offer_target, MOCK_SETTINGS)
        score_o, _ = score_offer(offer_other, MOCK_SETTINGS)
        assert score_t > score_o

    def test_location_match_adds_to_score(self) -> None:
        offer_paris = _offer("ML Engineer", company="Unknown", location="Paris")
        offer_other = _offer("ML Engineer", company="Unknown", location="Marseille")
        score_p, _ = score_offer(offer_paris, MOCK_SETTINGS)
        score_o, _ = score_offer(offer_other, MOCK_SETTINGS)
        assert score_p > score_o

    def test_tags_contain_matched_keywords(self) -> None:
        offer = _offer("LLM Engineer", company="Unknown", location="Lyon")
        _, tags = score_offer(offer, MOCK_SETTINGS)
        assert "LLM Engineer" in tags

    def test_score_capped_at_five(self) -> None:
        # Offer that matches everything multiple times
        offer = _offer(
            "AI Engineer ML Engineer LLM Engineer",
            company="Mistral AI",
            location="Paris",
        )
        score, _ = score_offer(offer, MOCK_SETTINGS)
        assert score <= 5.0

    def test_case_insensitive_keyword_match(self) -> None:
        offer = _offer("ai engineer", company="Unknown", location="Lyon")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        assert score > 0

    def test_case_insensitive_company_match(self) -> None:
        offer = _offer("Developer", company="mistral ai", location="Lyon")
        score, _ = score_offer(offer, MOCK_SETTINGS)
        # company match should contribute
        offer_no = _offer("Developer", company="Random Corp", location="Lyon")
        score_no, _ = score_offer(offer_no, MOCK_SETTINGS)
        assert score > score_no


class TestPreFilter:
    """Tests for pre_filter()."""

    def test_empty_list_returns_empty(self) -> None:
        assert pre_filter([], MOCK_SETTINGS) == []

    def test_below_threshold_dropped(self) -> None:
        offers = [_offer("Java Developer", company="Random Corp", location="Lyon")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert result == []

    def test_above_threshold_kept(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result) == 1

    def test_score_written_to_offer(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert result[0].score > 0

    def test_tags_written_to_offer(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result[0].tags) > 0

    def test_mixed_list_filters_correctly(self) -> None:
        offers = [
            _offer("AI Engineer", company="Mistral AI", location="Paris"),
            _offer("Java Developer", company="Random Corp", location="Lyon"),
            _offer("ML Engineer", company="Hugging Face", location="Paris"),
        ]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result) == 2
        titles = [o.title for o in result]
        assert "Java Developer" not in titles


MOCK_SETTINGS_V2 = {
    "search": {
        "keywords": ["AI Engineer", "ML Engineer"],
        "location": "Paris",
        "experience_max_years": 3,
    },
    "scoring": {
        "thresholds": {"recommend": 4.0, "consider": 1.0},
        "target_salary_min": 40000,
        "target_salary_max": 55000,
    },
    "target_companies": {
        "esn": ["Capgemini Engineering"],
    },
}


def _offer_with_desc(
    title: str = "Developer",
    company: str = "Unknown Corp",
    location: str = "Lyon",
    portal: str = "apec",
    description: str = "",
) -> RawOffer:
    return RawOffer(
        title=title,
        company=company,
        url="https://x.com",
        portal=portal,
        location=location,
        description=description,
    )


class TestNewSignals:
    def test_tech_skills_in_description(self) -> None:
        # 5 skills → +0.5
        desc = "We use python, pytorch, docker, fastapi, mlops in production."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_tech_skills_capped_at_1(self) -> None:
        # 15 skills → capped at +1.0
        desc = (
            "python pytorch tensorflow sklearn xgboost lightgbm docker kubernetes "
            "fastapi airflow aws gcp azure postgresql rag"
        )
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_experience_under_threshold(self) -> None:
        desc = "Vous avez 2 ans d'expérience en ML."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_experience_over_threshold(self) -> None:
        desc = "Vous avez 5 ans d'expérience en ML."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_experience_no_match(self) -> None:
        desc = "Rejoignez notre équipe dynamique."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_cdi_in_description(self) -> None:
        desc = "Poste en CDI à Paris."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.3, abs=0.01)

    def test_salary_in_range(self) -> None:
        desc = "Salaire proposé : 45k€ selon profil."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.3, abs=0.01)

    def test_salary_out_of_range(self) -> None:
        desc = "Salaire proposé : 80k€ selon profil."
        offer = _offer_with_desc(description=desc)
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_company_normalization(self) -> None:
        # "CAPGEMINI ENGINEERING FRANCE" should match "Capgemini Engineering"
        offer = _offer_with_desc(
            title="AI Engineer",
            company="CAPGEMINI ENGINEERING FRANCE",
        )
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        # keyword match (+1.0) + company match (+1.0) = 2.0
        assert score == pytest.approx(2.0, abs=0.01)
        assert any("target:" in t for t in tags)

    def test_ats_portal_bonus(self) -> None:
        offer = _offer_with_desc(portal="lever")
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.3, abs=0.01)

    def test_portal_apec_no_bonus(self) -> None:
        offer = _offer_with_desc(portal="apec")
        score, _ = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(0.0, abs=0.01)
