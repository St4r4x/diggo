"""Tests for description_parser module."""

from __future__ import annotations

from scripts.description_parser import parse_description
from scripts.models import ParsedDescription


def test_parsed_description_fields() -> None:
    pd = ParsedDescription(
        mission="m", profil="p", stack="s", avantages="a", contrat="c", salaire="sal"
    )
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


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def test_generic_puts_everything_in_mission() -> None:
    pd = parse_description("Some job description text.", "unknown_portal")
    assert pd.mission == "Some job description text."
    assert pd.profil == ""
    assert pd.stack == ""


# ---------------------------------------------------------------------------
# APEC parser
# ---------------------------------------------------------------------------

_APEC_BLOB = (
    "Développer des modèles ML pour nos clients. "
    "Profil recherché Python, PyTorch. "
    "L'entreprise est une startup IA fondée en 2020."
)


def test_apec_mission_extracted() -> None:
    pd = parse_description(_APEC_BLOB, "apec")
    assert "Développer des modèles" in pd.mission


def test_apec_profil_extracted() -> None:
    pd = parse_description(_APEC_BLOB, "apec")
    assert "Python" in pd.profil


def test_apec_avantages_empty_when_absent() -> None:
    pd = parse_description(_APEC_BLOB, "apec")
    assert pd.avantages == ""


# ---------------------------------------------------------------------------
# HTML heading parser (Lever / Greenhouse / Ashby)
# ---------------------------------------------------------------------------

_HTML_DESC = """
<h3>About the role</h3>
<p>You will build ML pipelines.</p>
<h3>Requirements</h3>
<p>3+ years Python. PyTorch experience.</p>
<h3>What we offer</h3>
<p>CDI, 50k€, RTT, titre-restaurant.</p>
<h3>Tech stack</h3>
<p>Python, FastAPI, Docker, Kubernetes.</p>
"""


def test_lever_mission_from_about_role() -> None:
    pd = parse_description(_HTML_DESC, "lever")
    assert "ML pipelines" in pd.mission


def test_lever_profil_from_requirements() -> None:
    pd = parse_description(_HTML_DESC, "lever")
    assert "PyTorch" in pd.profil


def test_lever_avantages_from_what_we_offer() -> None:
    pd = parse_description(_HTML_DESC, "lever")
    assert "RTT" in pd.avantages


def test_lever_stack_from_tech_stack() -> None:
    pd = parse_description(_HTML_DESC, "lever")
    assert "Docker" in pd.stack


def test_greenhouse_same_as_lever() -> None:
    pd = parse_description(_HTML_DESC, "greenhouse")
    assert "ML pipelines" in pd.mission


def test_ashby_same_as_lever() -> None:
    pd = parse_description(_HTML_DESC, "ashby")
    assert "ML pipelines" in pd.mission


# ---------------------------------------------------------------------------
# Heuristic parser (Indeed / WTTJ / LinkedIn / Glassdoor)
# ---------------------------------------------------------------------------

_HEURISTIC_DESC = """
Missions :
Développer et déployer des modèles ML en production.

Profil recherché :
Expérience en Python et MLOps. Minimum 2 ans.

Stack technique :
Python, Docker, Kubernetes, MLflow.

Avantages :
CDI, 48k€, 12 RTT, titre-restaurant.
"""


def test_indeed_mission_extracted() -> None:
    pd = parse_description(_HEURISTIC_DESC, "indeed")
    assert "Développer" in pd.mission


def test_indeed_profil_extracted() -> None:
    pd = parse_description(_HEURISTIC_DESC, "indeed")
    assert "MLOps" in pd.profil


def test_indeed_stack_extracted() -> None:
    pd = parse_description(_HEURISTIC_DESC, "indeed")
    assert "MLflow" in pd.stack


def test_indeed_avantages_extracted() -> None:
    pd = parse_description(_HEURISTIC_DESC, "indeed")
    assert "RTT" in pd.avantages


def test_wtfj_same_as_indeed() -> None:
    pd = parse_description(_HEURISTIC_DESC, "wtfj")
    assert "Développer" in pd.mission


def test_linkedin_same_as_indeed() -> None:
    pd = parse_description(_HEURISTIC_DESC, "linkedin")
    assert "Développer" in pd.mission


def test_glassdoor_same_as_indeed() -> None:
    pd = parse_description(_HEURISTIC_DESC, "glassdoor")
    assert "Développer" in pd.mission
