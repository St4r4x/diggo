"""Tests for scripts/liveness.py — uses pytest-httpx for HTTP mocking."""

from __future__ import annotations

import httpx
from pytest_httpx import HTTPXMock


class TestCheckLiveness:
    def test_404_returns_expired(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_response(url="https://example.com/job/123", status_code=404)
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "expired"
        assert "404" in reason

    def test_410_returns_expired(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_response(url="https://example.com/job/123", status_code=410)
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "expired"
        assert "410" in reason

    def test_body_pattern_fr_expired(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_response(
            url="https://example.com/job/123",
            status_code=200,
            text="Désolé, cette offre a expiré.",
        )
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "expired"
        assert "body_pattern" in reason

    def test_body_pattern_en_expired(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_response(
            url="https://example.com/job/123",
            status_code=200,
            text="This job is no longer available.",
        )
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "expired"

    def test_200_clean_body_active(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_response(
            url="https://example.com/job/123",
            status_code=200,
            text="<html><body><h1>Senior ML Engineer</h1><p>Apply now!</p></body></html>",
        )
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "active"
        assert reason == "ok"

    def test_network_error_uncertain(self, httpx_mock: HTTPXMock) -> None:
        from scripts.liveness import check_liveness

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        status, reason = check_liveness("https://example.com/job/123")
        assert status == "uncertain"
        assert "network_error" in reason

    def test_empty_url_uncertain(self) -> None:
        from scripts.liveness import check_liveness

        status, reason = check_liveness("")
        assert status == "uncertain"
        assert reason == "no_url"
