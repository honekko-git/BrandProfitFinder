"""Browser tests for profit validation discovery."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import SQLiteOpportunityStore, ValidationResultStore
from profit_discovery.models import BuyDecision


def test_validation_page_renders_form_and_results(tmp_path) -> None:
    validation_store = ValidationResultStore()
    opportunity_store = SQLiteOpportunityStore(database_path=tmp_path / "brand_profit.db")
    client = TestClient(
        create_app(
            validation_store=validation_store,
            opportunity_store=opportunity_store,
        )
    )

    page = client.get("/validation")
    assert page.status_code == 200
    assert "利益検証結果" in page.text
    assert "Chanel" in page.text
    assert "Wallet" in page.text

    response = client.post(
        "/validation",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )
    assert response.status_code == 200
    assert "検証順位" in response.text
    assert "仕入先" in response.text
    assert "販売市場" in response.text
    assert "利益" in response.text

    snapshot = validation_store.get()
    assert snapshot is not None
    assert snapshot.validation_ranking


def test_validation_save_allows_buy_only(tmp_path) -> None:
    validation_store = ValidationResultStore()
    opportunity_store = SQLiteOpportunityStore(database_path=tmp_path / "brand_profit.db")
    client = TestClient(
        create_app(
            validation_store=validation_store,
            opportunity_store=opportunity_store,
        )
    )
    client.post(
        "/validation",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )
    snapshot = validation_store.get()
    assert snapshot is not None
    assert snapshot.validation_ranking

    buy_item = next(
        (item for item in snapshot.validation_ranking if item.decision == BuyDecision.BUY.value),
        snapshot.validation_ranking[0],
    )
    if buy_item.decision != BuyDecision.BUY.value:
        return

    save_response = client.post(
        f"/validation/{buy_item.external_id}/save",
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    saved_items = opportunity_store.list_all()
    assert len(saved_items) == 1
    assert saved_items[0].decision == BuyDecision.BUY.value

    non_buy = next(
        (item for item in snapshot.validation_ranking if item.decision != BuyDecision.BUY.value),
        None,
    )
    if non_buy is not None:
        blocked = client.post(f"/validation/{non_buy.external_id}/save")
        assert blocked.status_code == 400
