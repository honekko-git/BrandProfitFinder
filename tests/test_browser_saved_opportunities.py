"""Tests for browser saved opportunity flows."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import DashboardResultStore


def test_save_button_persists_opportunity(tmp_path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "brand_profit.db"))
    search_response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )
    assert search_response.status_code == 200
    assert "候補を保存" in search_response.text

    store: DashboardResultStore = client.app.state.result_store
    snapshot = store.get()
    assert snapshot is not None
    product_id = snapshot.arbitrage_ranking[0].external_id

    save_response = client.post(f"/opportunities/{product_id}/save", follow_redirects=False)
    assert save_response.status_code == 303

    saved_response = client.get("/saved")
    assert saved_response.status_code == 200
    assert "Chanel" in saved_response.text
    assert "Fashionphile" in saved_response.text
    assert "NEW" in saved_response.text


def test_saved_page_and_detail_status(tmp_path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "brand_profit.db"))
    client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )
    store: DashboardResultStore = client.app.state.result_store
    snapshot = store.get()
    assert snapshot is not None
    product_id = snapshot.arbitrage_ranking[0].external_id
    client.post(f"/opportunities/{product_id}/save")

    detail_before = client.get(f"/product/{product_id}")
    assert detail_before.status_code == 200
    assert "保存状態" in detail_before.text
    assert "NEW" in detail_before.text
    assert "WATCHING にする" in detail_before.text

    record_id = client.app.state.opportunity_store.list_all()[0].id
    status_response = client.post(
        f"/saved/{record_id}/status",
        data={"status": "WATCHING", "redirect_to": f"/product/{product_id}"},
        follow_redirects=False,
    )
    assert status_response.status_code == 303

    detail_after = client.get(f"/product/{product_id}")
    assert detail_after.status_code == 200
    assert "WATCHING" in detail_after.text
    assert "PURCHASED にする" in detail_after.text
