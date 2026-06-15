"""Tests for description_parser module."""

from __future__ import annotations

from scripts.models import ParsedDescription


def test_parsed_description_fields() -> None:
    pd = ParsedDescription(mission="m", profil="p", stack="s", avantages="a", contrat="c", salaire="sal")
    assert pd.mission == "m"
    assert pd.profil == "p"
    assert pd.stack == "s"
    assert pd.avantages == "a"
    assert pd.contrat == "c"
    assert pd.salaire == "sal"


def test_parsed_description_defaults() -> None:
    pd = ParsedDescription()
    assert pd.mission == ""
    assert pd.profil == ""
    assert pd.stack == ""
    assert pd.avantages == ""
    assert pd.contrat == ""
    assert pd.salaire == ""
