"""Tests for the browser dashboard application."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, create_app
from app.store import DashboardResultStore


def test_app_import() -> None:
    assert app is not None
    assert app.title == "LuxuryBrandProfitFinder"


def test_create_app_uses_custom_store() -> None:
    store = DashboardResultStore()
    client = TestClient(create_app(result_store=store))
    response = client.get("/")
    assert response.status_code == 200
    assert client.app.state.result_store is store


def test_dashboard_route_renders() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "LuxuryBrandProfitFinder" in response.text
    assert "中古高級品 利益ダッシュボード" in response.text
    assert "Louis Vuitton" in response.text
    assert "Wallet" in response.text


def test_search_route_renders_ranking_cards() -> None:
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
    assert "アービトラージ順位" in response.text
    assert "仕入先" in response.text
    assert "販売市場" in response.text
    assert "推定利益" in response.text


def test_product_detail_route_renders_after_search() -> None:
    client = TestClient(app)
    search_response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )
    assert search_response.status_code == 200

    store: DashboardResultStore = client.app.state.result_store
    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking

    product_id = snapshot.arbitrage_ranking[0].external_id
    detail_response = client.get(f"/product/{product_id}")

    assert detail_response.status_code == 200
    assert "価格比較" in detail_response.text
    assert "AI判定" in detail_response.text
    assert "仕入URL" in detail_response.text
    assert "販売URL" in detail_response.text
