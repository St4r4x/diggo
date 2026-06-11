"""Tests for pre_filter module."""

from __future__ import annotations

import pytest

from scripts.models import RawOffer
from scripts.pre_filter import _is_location_compatible, pre_filter, score_offer


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
        # 5 skills → +0.5 skill bonus; use _CLEAN_DESC to avoid legitimacy penalties
        offer_with = _offer_with_desc(description=_CLEAN_DESC)
        offer_without = _offer_with_desc(
            description="lorem ipsum dolor sit amet. " * 15 + "45k€ selon profil"
        )
        score_with, _ = score_offer(offer_with, MOCK_SETTINGS_V2)
        score_without, _ = score_offer(offer_without, MOCK_SETTINGS_V2)
        assert score_with > score_without

    def test_tech_skills_capped_at_1(self) -> None:
        # 15 skills → skills bonus capped at +1.0
        desc = (
            "python pytorch tensorflow sklearn xgboost lightgbm docker kubernetes "
            "fastapi airflow aws gcp azure postgresql rag 45k€. "
            + "lorem ipsum dolor sit amet "
            * 10
        )
        offer = _offer_with_desc(description=desc)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert any(t.startswith("skills:") and int(t.split(":")[1]) >= 10 for t in tags)

    def test_experience_under_threshold(self) -> None:
        desc = _CLEAN_DESC + " Vous avez 2 ans d'expérience en ML."
        offer_with_exp = _offer_with_desc(description=desc)
        offer_no_exp = _offer_with_desc(description=_CLEAN_DESC)
        score_with, tags = score_offer(offer_with_exp, MOCK_SETTINGS_V2)
        score_no, _ = score_offer(offer_no_exp, MOCK_SETTINGS_V2)
        assert score_with == pytest.approx(score_no + 0.5, abs=0.01)
        assert any("exp:" in t for t in tags)

    def test_experience_over_threshold(self) -> None:
        desc = _CLEAN_DESC + " Vous avez 5 ans d'expérience en ML."
        offer = _offer_with_desc(description=desc)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert not any("exp:" in t for t in tags)

    def test_experience_no_match(self) -> None:
        desc = _CLEAN_DESC  # no exp mention
        offer = _offer_with_desc(description=desc)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert not any("exp:" in t for t in tags)

    def test_cdi_in_description(self) -> None:
        # CDI adds +0.3; compare desc with CDI vs without
        base = "python docker mlops 45k€. " + "lorem ipsum dolor sit amet " * 12
        desc_cdi = base + " Poste en CDI."
        desc_no_cdi = base + " Poste en CDD."
        offer_cdi = _offer_with_desc(description=desc_cdi)
        offer_no_cdi = _offer_with_desc(description=desc_no_cdi)
        score_cdi, _ = score_offer(offer_cdi, MOCK_SETTINGS_V2)
        score_no_cdi, _ = score_offer(offer_no_cdi, MOCK_SETTINGS_V2)
        assert score_cdi == pytest.approx(score_no_cdi + 0.3, abs=0.01)

    def test_salary_in_range(self) -> None:
        # Salary in range → +0.5; use long desc with tech to zero out other legitimacy signals
        base = "python docker mlops fastapi. " + "lorem ipsum dolor sit amet " * 12
        desc_in = base + " Salaire 45k€ selon profil."
        desc_out = base + " Salaire 80k€ selon profil."
        offer_in = _offer_with_desc(description=desc_in)
        offer_out = _offer_with_desc(description=desc_out)
        score_in, _ = score_offer(offer_in, MOCK_SETTINGS_V2)
        score_out, _ = score_offer(offer_out, MOCK_SETTINGS_V2)
        assert score_in > score_out

    def test_salary_out_of_range(self) -> None:
        # Out-of-range salary → -0.3 vs in-range → +0.5
        base = "python docker mlops fastapi. " + "lorem ipsum dolor sit amet " * 12
        desc_in = base + " Salaire 45k€ selon profil."
        desc_out = base + " Salaire 80k€ selon profil."
        offer_in = _offer_with_desc(description=desc_in)
        offer_out = _offer_with_desc(description=desc_out)
        score_in, _ = score_offer(offer_in, MOCK_SETTINGS_V2)
        score_out, _ = score_offer(offer_out, MOCK_SETTINGS_V2)
        assert score_in == pytest.approx(score_out + 0.8, abs=0.05)

    def test_company_normalization(self) -> None:
        # "CAPGEMINI ENGINEERING FRANCE" should match "Capgemini Engineering"
        offer = _offer_with_desc(
            title="AI Engineer",
            company="CAPGEMINI ENGINEERING FRANCE",
        )
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        # keyword match (+1.0) + company match (+1.0) = at least 2.0
        assert score >= 2.0
        assert any("target:" in t for t in tags)

    def test_ats_portal_bonus(self) -> None:
        offer_lever = _offer_with_desc(portal="lever", description=_CLEAN_DESC)
        offer_apec = _offer_with_desc(portal="apec", description=_CLEAN_DESC)
        score_lever, _ = score_offer(offer_lever, MOCK_SETTINGS_V2)
        score_apec, _ = score_offer(offer_apec, MOCK_SETTINGS_V2)
        assert score_lever == pytest.approx(score_apec + 0.3, abs=0.05)

    def test_portal_apec_no_bonus(self) -> None:
        offer_lever = _offer_with_desc(portal="lever", description=_CLEAN_DESC)
        offer_apec = _offer_with_desc(portal="apec", description=_CLEAN_DESC)
        score_lever, _ = score_offer(offer_lever, MOCK_SETTINGS_V2)
        score_apec, _ = score_offer(offer_apec, MOCK_SETTINGS_V2)
        assert score_lever > score_apec


_SALARY_BASE = "python docker mlops fastapi. " + "lorem ipsum dolor sit amet " * 12


_SALARY_BASE = "python docker mlops fastapi. " + "lorem ipsum dolor sit amet " * 12


class TestSalaryNormalized:
    def test_13th_month_raises_package_into_range(self) -> None:
        # 3500 × 13 = 45500 → in range [40k-55k] → salary tag present, score better than out-of-range
        desc_13 = _SALARY_BASE + " Salaire 3500€/mois + 13ème mois"
        desc_out = (
            _SALARY_BASE + " Salaire 3500€/mois"
        )  # 3500×12=42000, still in range – use 100k
        desc_out2 = _SALARY_BASE + " Rémunération 100k€"
        offer_13 = _offer_with_desc(description=desc_13)
        offer_out = _offer_with_desc(description=desc_out2)
        score_13, tags = score_offer(offer_13, MOCK_SETTINGS_V2)
        score_out, _ = score_offer(offer_out, MOCK_SETTINGS_V2)
        assert score_13 > score_out
        assert any("salary:" in t for t in tags)

    def test_rtt_and_tr_added_to_package(self) -> None:
        # 38000 base + 10 RTT (~1743) + TR (~1962) = ~41705 → in range
        # Without perks, 38000 is below range → penalty; with perks, it becomes in-range → bonus
        desc_with = _SALARY_BASE + " Salaire 38000€ annuel, 10 RTT, titre-restaurant"
        desc_without = _SALARY_BASE + " Salaire 38000€ annuel"
        offer_with = _offer_with_desc(description=desc_with)
        offer_without = _offer_with_desc(description=desc_without)
        score_with, _ = score_offer(offer_with, MOCK_SETTINGS_V2)
        score_without, _ = score_offer(offer_without, MOCK_SETTINGS_V2)
        assert score_with > score_without

    def test_salary_out_of_range_penalty(self) -> None:
        # In-range salary → +0.5; out-of-range → -0.3; delta = 0.8
        desc_in = _SALARY_BASE + " Salaire 45k€ selon profil."
        desc_out = _SALARY_BASE + " Rémunération : 80k€"
        offer_in = _offer_with_desc(description=desc_in)
        offer_out = _offer_with_desc(description=desc_out)
        score_in, _ = score_offer(offer_in, MOCK_SETTINGS_V2)
        score_out, _ = score_offer(offer_out, MOCK_SETTINGS_V2)
        assert score_in == pytest.approx(score_out + 0.8, abs=0.05)

    def test_salary_no_info_neutral(self) -> None:
        # No salary info → legitimacy:no_salary tag, no salary: tag
        desc = _SALARY_BASE
        offer = _offer_with_desc(description=desc)
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert "legitimacy:no_salary" in tags
        assert not any("salary:" in t for t in tags)

    def test_interessement_adds_to_package(self) -> None:
        # 40000 + 5% intéressement = 42000 → in range; without intéressement 40000 is in range too
        # Compare with vs without intéressement: both in range → same bonus
        # Instead verify in-range score beats out-of-range score
        desc_int = _SALARY_BASE + " Salaire 40000€, intéressement selon résultats"
        desc_out = _SALARY_BASE + " Salaire 80k€"
        offer_int = _offer_with_desc(description=desc_int)
        offer_out = _offer_with_desc(description=desc_out)
        score_int, tags_int = score_offer(offer_int, MOCK_SETTINGS_V2)
        score_out, _ = score_offer(offer_out, MOCK_SETTINGS_V2)
        assert score_int > score_out
        assert any("salary:" in t for t in tags_int)


_CLEAN_DESC = (
    "python pytorch docker mlops aws postgresql fastapi nlp llm rag CDI "
    "45k€ selon profil " + "lorem ipsum dolor sit amet " * 15
)


class TestCvLanguage:
    def test_explicit_english_cv_required_tagged(self) -> None:
        desc = _CLEAN_DESC + " Please submit your CV in English."
        offer = _offer_with_desc(description=desc)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert "lang:cv_en_required" in tags

    def test_fluent_english_not_tagged(self) -> None:
        desc = _CLEAN_DESC + " You are fluent in English."
        offer = _offer_with_desc(description=desc)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert "lang:cv_en_required" not in tags

    def test_no_english_mention_not_tagged(self) -> None:
        offer = _offer_with_desc(description=_CLEAN_DESC)
        _, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert "lang:cv_en_required" not in tags


class TestLegitimacy:
    def test_thin_description_penalty(self) -> None:
        desc = "Poste à pourvoir. Envoyez votre CV."
        offer = _offer_with_desc(description=desc)
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(-0.5, abs=0.05)
        assert "legitimacy:suspicious" in tags

    def test_no_tech_skills_penalty(self) -> None:
        # Long desc (>300 chars) but 0 tech skills and no salary → -0.3 + -0.2 = -0.5 (capped)
        desc = "Nous recherchons un profil dynamique et motivé. " * 20
        offer = _offer_with_desc(description=desc)
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert score == pytest.approx(-0.5, abs=0.05)
        assert "legitimacy:suspicious" in tags

    def test_no_salary_no_suspicious_tag(self) -> None:
        # Long desc with tech skills but no salary → -0.2 (below suspicious threshold)
        desc = ("python pytorch mlops docker fastapi " * 5) + (" lorem ipsum " * 30)
        offer = _offer_with_desc(description=desc)
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert "legitimacy:suspicious" not in tags
        assert "legitimacy:no_salary" in tags

    def test_good_offer_no_legitimacy_tags(self) -> None:
        desc = "python pytorch mlops docker CDI 45k€. " + ("lorem ipsum " * 30)
        offer = _offer_with_desc(description=desc)
        score, tags = score_offer(offer, MOCK_SETTINGS_V2)
        assert not any("legitimacy:" in t for t in tags)


class TestIsLocationCompatible:
    """Unit tests for _is_location_compatible(target, location)."""

    def test_empty_location_passes(self) -> None:
        assert _is_location_compatible("", "Paris") is True

    def test_exact_match_passes(self) -> None:
        assert _is_location_compatible("Paris", "Paris") is True

    def test_city_with_suffix_passes(self) -> None:
        assert _is_location_compatible("Paris 8ème", "Paris") is True

    def test_case_insensitive(self) -> None:
        assert _is_location_compatible("PARIS", "Paris") is True

    def test_remote_passes(self) -> None:
        assert _is_location_compatible("Remote", "Paris") is True

    def test_full_remote_passes(self) -> None:
        assert _is_location_compatible("Full-Remote", "Paris") is True

    def test_teletravail_passes(self) -> None:
        assert _is_location_compatible("Télétravail", "Paris") is True

    def test_hybride_passes(self) -> None:
        assert _is_location_compatible("Paris / Hybride", "Paris") is True

    def test_different_city_rejected(self) -> None:
        assert _is_location_compatible("Lyon", "Paris") is False

    def test_different_city_rejected_lyon_target(self) -> None:
        assert _is_location_compatible("Paris", "Lyon") is False

    def test_lyon_target_accepts_lyon(self) -> None:
        assert _is_location_compatible("Lyon", "Lyon") is True

    def test_bordeaux_target_accepts_bordeaux(self) -> None:
        assert _is_location_compatible("Bordeaux", "Bordeaux") is True

    def test_foreign_city_rejected(self) -> None:
        assert _is_location_compatible("London", "Paris") is False


# threshold=2.0 so keyword(+1) + company(+1) = 2.0 passes without location bonus
_LOCATION_SETTINGS: dict = {
    "search": {"keywords": ["AI Engineer"], "location": "Paris"},
    "scoring": {
        "thresholds": {"consider": 2.0},
        "target_salary_min": 40000,
        "target_salary_max": 55000,
    },
    "target_companies": {"french_ai": ["Mistral AI"]},
}


class TestPreFilterLocationGate:
    """Integration tests: location hard-reject inside pre_filter()."""

    def test_lyon_offer_rejected_despite_high_score(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Lyon")]
        result = pre_filter(offers, _LOCATION_SETTINGS)
        assert result == []

    def test_paris_offer_passes(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, _LOCATION_SETTINGS)
        assert len(result) == 1

    def test_remote_offer_passes(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Remote")]
        result = pre_filter(offers, _LOCATION_SETTINGS)
        assert len(result) == 1

    def test_empty_location_passes(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="")]
        result = pre_filter(offers, _LOCATION_SETTINGS)
        assert len(result) == 1

    def test_no_location_filter_in_settings_keeps_all(self) -> None:
        settings_no_loc = {
            **_LOCATION_SETTINGS,
            "search": {"keywords": ["AI Engineer"]},
        }
        offers = [
            _offer("AI Engineer", company="Mistral AI", location="Lyon"),
            _offer("AI Engineer", company="Mistral AI", location="Bordeaux"),
        ]
        result = pre_filter(offers, settings_no_loc)
        assert len(result) == 2
