"""Tests for scan_ats: providers, resolve_provider, scan_ats integration."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from scripts.scan_ats import (
    AshbyProvider,
    GreenhouseProvider,
    LeverProvider,
    resolve_provider,
    scan_ats,
)


class TestResolveProvider:
    def test_greenhouse_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://job-boards.greenhouse.io/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is GreenhouseProvider
        assert slug == "acme"

    def test_greenhouse_job_boards_url_detected(self) -> None:
        entry = {
            "name": "Acme",
            "careers_url": "https://job-boards.greenhouse.io/mistralai",
        }
        provider, slug = resolve_provider(entry)
        assert provider is GreenhouseProvider
        assert slug == "mistralai"

    def test_lever_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://jobs.lever.co/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is LeverProvider
        assert slug == "acme"

    def test_ashby_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://jobs.ashbyhq.com/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is AshbyProvider
        assert slug == "acme"

    def test_unknown_url_returns_none(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://www.acme.com/careers"}
        assert resolve_provider(entry) is None

    def test_missing_careers_url_returns_none(self) -> None:
        entry = {"name": "Acme"}
        assert resolve_provider(entry) is None


class TestGreenhouseProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={
                "jobs": [
                    {
                        "title": "AI Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "location": {"name": "Paris"},
                    },
                    {
                        "title": "ML Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                        "location": {"name": "Remote"},
                    },
                ]
            },
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 2
        assert offers[0].title == "AI Engineer"
        assert offers[0].company == "Acme Corp"
        assert offers[0].url == "https://boards.greenhouse.io/acme/jobs/1"
        assert offers[0].location == "Paris"
        assert offers[0].portal == "greenhouse"

    @pytest.mark.asyncio
    async def test_fetch_empty_jobs_array(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={"jobs": []},
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert offers == []

    @pytest.mark.asyncio
    async def test_fetch_http_error_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            status_code=404,
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestLeverProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[
                {
                    "text": "Data Scientist",
                    "hostedUrl": "https://jobs.lever.co/acme/123",
                    "categories": {"location": "Paris, France"},
                }
            ],
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 1
        assert offers[0].title == "Data Scientist"
        assert offers[0].company == "Acme Corp"
        assert offers[0].url == "https://jobs.lever.co/acme/123"
        assert offers[0].location == "Paris, France"
        assert offers[0].portal == "lever"

    @pytest.mark.asyncio
    async def test_fetch_empty_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[],
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert offers == []

    @pytest.mark.asyncio
    async def test_fetch_http_500_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            status_code=500,
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestAshbyProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.ashbyhq.com/posting-api/job-board/acme",
            json={
                "jobs": [
                    {
                        "title": "LLM Engineer",
                        "jobUrl": "https://jobs.ashbyhq.com/acme/abc",
                        "location": "Paris",
                    }
                ]
            },
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await AshbyProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 1
        assert offers[0].title == "LLM Engineer"
        assert offers[0].portal == "ashby"

    @pytest.mark.asyncio
    async def test_fetch_empty_jobs_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.ashbyhq.com/posting-api/job-board/acme",
            json={"jobs": []},
        )
        import httpx

        async with httpx.AsyncClient() as client:
            offers = await AshbyProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestScanAts:
    @pytest.mark.asyncio
    async def test_returns_offers_from_all_providers(
        self, httpx_mock: HTTPXMock, tmp_path
    ) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme GH'\n  careers_url: 'https://job-boards.greenhouse.io/acme'\n"
            "- name: 'Acme Lever'\n  careers_url: 'https://jobs.lever.co/acmelever'\n"
        )
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={
                "jobs": [
                    {
                        "title": "AI Eng",
                        "absolute_url": "https://gh.io/1",
                        "location": {"name": "Paris"},
                    }
                ]
            },
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acmelever",
            json=[
                {
                    "text": "ML Eng",
                    "hostedUrl": "https://lever.co/1",
                    "categories": {"location": "Paris"},
                }
            ],
        )
        offers = await scan_ats(ats_map_path=ats_map)
        assert len(offers) == 2

    @pytest.mark.asyncio
    async def test_company_filter(self, httpx_mock: HTTPXMock, tmp_path) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme'\n  careers_url: 'https://jobs.lever.co/acme'\n"
            "- name: 'Beta'\n  careers_url: 'https://jobs.lever.co/beta'\n"
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[
                {
                    "text": "Dev",
                    "hostedUrl": "https://lever.co/1",
                    "categories": {"location": ""},
                }
            ],
        )
        offers = await scan_ats(ats_map_path=ats_map, company_filter="Acme")
        assert len(offers) == 1
        assert offers[0].company == "Acme"

    @pytest.mark.asyncio
    async def test_unknown_provider_skipped(
        self, httpx_mock: HTTPXMock, tmp_path
    ) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Unknown Co'\n  careers_url: 'https://custom.com/careers'\n"
        )
        offers = await scan_ats(ats_map_path=ats_map)
        assert offers == []

    @pytest.mark.asyncio
    async def test_keyword_filter(self, httpx_mock: HTTPXMock, tmp_path) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme'\n  careers_url: 'https://jobs.lever.co/acme'\n"
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[
                {
                    "text": "AI Engineer",
                    "hostedUrl": "https://lever.co/1",
                    "categories": {"location": "Paris"},
                },
                {
                    "text": "Office Manager",
                    "hostedUrl": "https://lever.co/2",
                    "categories": {"location": "Paris"},
                },
            ],
        )
        offers = await scan_ats(ats_map_path=ats_map, keywords=["AI Engineer"])
        assert len(offers) == 1
        assert offers[0].title == "AI Engineer"
