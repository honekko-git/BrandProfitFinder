"""Tests for real data truth output in browser validation."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import ValidationResultStore
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_validation_browser_shows_real_data_truth_fields() -> None:
    store = ValidationResultStore()
    client = TestClient(create_app(validation_store=store))
    response = client.post(
        "/validation",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "verification_mode": "REAL",
            "market_mode": "REAL",
        },
    )

    assert response.status_code == 200
    assert "REAL 利益検証" in response.text
    assert "データ状態:" in response.text
    assert "要求モード" in response.text
    assert "フォールバック" in response.text
    assert "為替レート" in response.text

    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.verification_mode == "REAL"
    assert snapshot.real_profit_results
    row = snapshot.real_profit_results[0]
    assert row.data_status in {"LIVE", "FIXTURE", "IMPORT", "MIXED"}
    assert row.actual_purchase_source in response.text
    assert row.actual_domestic_source in response.text


def test_manual_import_shows_import_data_status(monkeypatch) -> None:
    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    title = "Chanel Classic Wallet Black Caviar"

    def _inject_yahoo_html(**kwargs):
        from profit_discovery.discovery_validation import real_profit_verification as module

        queries = build_yahoo_search_queries(title=title, brand="Chanel", category="Wallet")
        kwargs["yahoo_html_by_query"] = {query: yahoo_html for query in queries}
        return module.build_real_profit_verifications(**kwargs)

    monkeypatch.setattr("app.real_profit_pipeline.build_real_profit_verifications", _inject_yahoo_html)

    store = ValidationResultStore()
    client = TestClient(create_app(validation_store=store))
    response = client.post(
        "/validation",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "verification_mode": "REAL",
            "market_mode": "REAL",
            "manual_purchase_title": title,
            "manual_purchase_url": "https://example.invalid/chanel-wallet-manual",
            "manual_purchase_price": "700",
            "manual_purchase_currency": "USD",
        },
    )

    assert response.status_code == 200
    snapshot = store.get()
    assert snapshot is not None
    row = snapshot.real_profit_results[0]
    assert row.actual_purchase_source == "IMPORT"
    assert row.actual_domestic_source == "LIVE"
    assert row.data_status == "MIXED"
    assert "MIXED" in response.text
    assert row.purchase_url == "https://example.invalid/chanel-wallet-manual"
    assert row.yahoo_live_sample_count >= 3
