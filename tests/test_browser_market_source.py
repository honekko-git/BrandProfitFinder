"""Tests for browser market source display."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_browser_search_displays_market_source_and_listing_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )

    assert response.status_code == 200
    assert "市場ソース" in response.text
    assert "状態" in response.text
    assert "URL" in response.text
    assert "Fashionphile" in response.text
