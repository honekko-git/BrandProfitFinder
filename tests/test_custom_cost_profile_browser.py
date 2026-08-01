"""Tests for custom cost profile browser form."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_cost_profile_form_renders() -> None:
    client = TestClient(create_app())
    response = client.get("/acquisition-workspace")
    assert response.status_code == 200
    assert "カスタムコスト設定" in response.text
    assert "exchange_rate" in response.text


def test_save_exchange_rate_only() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/acquisition-workspace/cost-profile/save",
        data={"exchange_rate": "151.5"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_invalid_negative_returns_server_error() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/acquisition-workspace/cost-profile/save",
        data={"exchange_rate": "150", "international_shipping_jpy": "-100"},
    )
    assert response.status_code >= 400
