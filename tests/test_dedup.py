"""Tests for dedup module."""

from __future__ import annotations

from scripts.dedup import deduplicate, normalize_key
from scripts.models import RawOffer


def _make_offer(
    title: str, company: str, portal: str = "wtfj", url: str = "https://x.com"
) -> RawOffer:
    return RawOffer(title=title, company=company, url=url, portal=portal)


class TestNormalizeKey:
    """Tests for normalize_key()."""

    def test_lowercase_and_strip(self) -> None:
        assert (
            normalize_key("  AI Engineer  ", "  Mistral AI  ")
            == "ai engineer||mistral ai"
        )

    def test_accent_normalization(self) -> None:
        # accents are stripped during normalization
        key = normalize_key("Ingénieur IA", "Société Générale")
        assert "ingenieur ia" in key
        assert "societe generale" in key

    def test_punctuation_stripped(self) -> None:
        key = normalize_key("AI/ML Engineer", "Hugging-Face")
        assert "/" not in key
        assert "-" not in key

    def test_multiple_spaces_collapsed(self) -> None:
        key = normalize_key("AI  ML  Engineer", "Big  Corp")
        assert "  " not in key


class TestDeduplicate:
    """Tests for deduplicate()."""

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []

    def test_no_duplicates_unchanged(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("ML Engineer", "Hugging Face", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 2

    def test_exact_duplicate_removed(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("AI Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_first_occurrence_kept(self) -> None:
        offers = [
            _make_offer(
                "AI Engineer", "Mistral AI", portal="wtfj", url="https://wtfj.com/1"
            ),
            _make_offer(
                "AI Engineer", "Mistral AI", portal="indeed", url="https://indeed.com/2"
            ),
        ]
        result = deduplicate(offers)
        assert result[0].portal == "wtfj"

    def test_case_insensitive_dedup(self) -> None:
        offers = [
            _make_offer("ai engineer", "mistral ai", portal="wtfj"),
            _make_offer("AI Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_accent_insensitive_dedup(self) -> None:
        offers = [
            _make_offer("Ingénieur IA", "Société Générale", portal="wtfj"),
            _make_offer("Ingenieur IA", "Societe Generale", portal="apec"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_different_titles_not_deduplicated(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("ML Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 2

    def test_preserves_order_of_first_occurrence(self) -> None:
        offers = [
            _make_offer("A", "CompA", portal="wtfj"),
            _make_offer("B", "CompB", portal="wtfj"),
            _make_offer("A", "CompA", portal="indeed"),
            _make_offer("C", "CompC", portal="wtfj"),
        ]
        result = deduplicate(offers)
        assert [o.title for o in result] == ["A", "B", "C"]
