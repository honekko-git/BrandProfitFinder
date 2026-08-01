"""End-to-end tests for import to arbitrage browser pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.import_pipeline import run_import_dashboard_pipeline
from app.main import create_app
from app.storage.models import OpportunityStatus
from app.storage.market_listing_repository import MarketListingRepository
from app.store import DashboardResultStore, SQLiteMarketListingStore, SQLiteOpportunityStore
from marketplace.connectors.models import MarketListing
from marketplace.importers.manual_importer import ManualImporter


def _sample_listing() -> MarketListing:
    return ManualImporter().create_listing(
        title="CHANEL Classic Wallet",
        brand="Chanel",
        category="Wallet",
        condition="Used",
        price="50000",
        currency="JPY",
        market_name="Fashionphile",
        url="https://example.invalid/import-chanel-wallet",
    )


def test_import_arbitrage_pipeline_preserves_profit_fields(tmp_path: Path) -> None:
    listing = _sample_listing()
    repository = MarketListingRepository(tmp_path / "brand_profit.db")
    result = run_import_dashboard_pipeline(
        [listing],
        listing_repository=repository,
    )

    assert result.ranked_count >= 1
    arbitrage = result.snapshot.arbitrage_ranking[0]
    candidate = result.snapshot.candidates_by_id[arbitrage.external_id]
    assert candidate.profit_result is not None
    assert candidate.profit_result.profit_jpy is not None
    assert candidate.profit_result.profit_margin is not None
    assert candidate.profit_result.roi is not None
    assert candidate.buy_decision is not None
    assert arbitrage.decision == candidate.buy_decision.decision.value
    assert arbitrage.estimated_profit == candidate.profit_result.profit_jpy
    assert arbitrage.listing_url == listing.url
    assert len(repository.list_all()) == 1


def test_import_manual_form_to_browser_and_sqlite(tmp_path: Path) -> None:
    store = DashboardResultStore()
    opportunity_store = SQLiteOpportunityStore(database_path=tmp_path / "brand_profit.db")
    market_listing_store = SQLiteMarketListingStore(database_path=tmp_path / "brand_profit.db")
    client = TestClient(
        create_app(
            result_store=store,
            opportunity_store=opportunity_store,
            market_listing_store=market_listing_store,
        )
    )

    response = client.post(
        "/import/manual",
        data={
            "title": "CHANEL Classic Wallet",
            "brand": "Chanel",
            "category": "Wallet",
            "condition": "Used",
            "price": "50000",
            "currency": "JPY",
            "market_name": "Fashionphile",
            "url": "https://example.invalid/import-chanel-wallet",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    dashboard = client.get("/?imported=1")
    assert dashboard.status_code == 200
    assert "取込が完了しました" in dashboard.text

    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking
    item = snapshot.arbitrage_ranking[0]
    assert item.brand == "Chanel"
    assert "Chanel" in dashboard.text
    candidate = snapshot.candidates_by_id[item.external_id]
    assert candidate.profit_result is not None

    saved = opportunity_store.save_arbitrage(item)
    assert float(saved.estimated_profit) == float(candidate.profit_result.profit_jpy)
    assert float(saved.profit_margin) == float(candidate.profit_result.profit_margin)
    assert saved.decision == candidate.buy_decision.decision.value
    assert saved.status is OpportunityStatus.NEW

    imported_page = client.get("/imported")
    assert imported_page.status_code == 200
    assert "CHANEL Classic Wallet" in imported_page.text
    assert "Fashionphile" in imported_page.text


def test_import_csv_upload_pipeline(tmp_path: Path) -> None:
    csv_path = tmp_path / "market_listings.csv"
    csv_path.write_text(
        "title,brand,category,condition,price,currency,market_name,url\n"
        "CHANEL Wallet,Chanel,Wallet,Used,50000,JPY,Fashionphile,https://example.invalid/csv-chanel\n",
        encoding="utf-8",
    )

    store = DashboardResultStore()
    market_listing_store = SQLiteMarketListingStore(database_path=tmp_path / "brand_profit.db")
    client = TestClient(
        create_app(
            result_store=store,
            market_listing_store=market_listing_store,
        )
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/import/csv",
            files={"csv_file": ("market_listings.csv", handle, "text/csv")},
            follow_redirects=False,
        )

    assert response.status_code == 303
    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking
    assert market_listing_store.list_all()
