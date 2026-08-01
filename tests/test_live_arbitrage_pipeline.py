"""End-to-end tests for live connector arbitrage and browser pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import run_used_luxury_dashboard_search
from app.storage.models import OpportunityStatus
from app.store import DashboardResultStore, SQLiteOpportunityStore
from marketplace.connectors import MarketConnectorConfig, MarketConnectorResolver, MarketListing
from marketplace.connectors.live.fashionphile.connector import FashionphileLiveConnector
from marketplace.connectors.live.http_client import MarketHttpClient
from profit_discovery.cli.discovery_command import build_default_discovery_runner
from profit_discovery.multi_brand import MultiBrandDiscoveryRunner


class _FakeHttpClient(MarketHttpClient):
    def __init__(self, payload: dict) -> None:
        super().__init__(retry_count=0)
        self._payload = payload

    def get_json(self, url: str, *, params: dict[str, str] | None = None) -> dict:
        return self._payload


def test_live_arbitrage_pipeline_preserves_profit_fields_with_fixture_fallback(monkeypatch) -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    fixture_result = run_used_luxury_dashboard_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )
    live_result = run_used_luxury_dashboard_search(
        brand="Chanel",
        category="Wallet",
        market_mode="LIVE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )

    fixture_item = fixture_result.snapshot.arbitrage_ranking[0]
    live_item = live_result.snapshot.arbitrage_ranking[0]
    fixture_candidate = fixture_result.snapshot.candidates_by_id[fixture_item.external_id]
    live_candidate = live_result.snapshot.candidates_by_id[live_item.external_id]

    assert fixture_candidate.profit_result is not None
    assert live_candidate.profit_result is not None
    assert live_candidate.profit_result.profit_jpy == fixture_candidate.profit_result.profit_jpy
    assert live_candidate.profit_result.profit_margin == fixture_candidate.profit_result.profit_margin
    assert live_candidate.profit_result.roi == fixture_candidate.profit_result.roi
    assert live_item.decision == fixture_item.decision
    assert live_result.snapshot.market_mode == "LIVE"
    assert live_result.snapshot.connector_executions


def test_live_connector_to_browser_and_sqlite_save(monkeypatch, tmp_path: Path) -> None:
    listing = MarketListing(
        id="live-fp-001",
        title="Live Chanel Wallet",
        brand="Chanel",
        category="wallet",
        condition="Excellent",
        price=Decimal("1200"),
        currency="USD",
        market_name="Fashionphile",
        url="https://example.invalid/live-fp-001",
        source_type="LIVE",
        created_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    class _LiveFashionphile(FashionphileLiveConnector):
        def search_products(self, query: str):
            return [listing]

    def _build_live(market_name: str, config: MarketConnectorConfig):
        if market_name == "Fashionphile":
            return _LiveFashionphile(config=config)
        from marketplace.connectors.live.mercari.connector import MercariLiveConnector
        from marketplace.connectors.live.yahoo.connector import YahooAuctionLiveConnector

        if market_name == "Yahoo Auction":
            return YahooAuctionLiveConnector(config=config)
        return MercariLiveConnector()

    monkeypatch.setattr("marketplace.connectors.resolver._build_live_connector", _build_live)

    store = DashboardResultStore()
    opportunity_store = SQLiteOpportunityStore(database_path=tmp_path / "brand_profit.db")
    client = TestClient(create_app(result_store=store, opportunity_store=opportunity_store))
    response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "LIVE",
        },
    )

    assert response.status_code == 200
    assert "市場モード LIVE" in response.text
    assert "取得元" in response.text
    assert "価格" in response.text
    assert "状態" in response.text

    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking
    item = snapshot.arbitrage_ranking[0]
    saved = opportunity_store.save_arbitrage(item)
    assert saved.estimated_profit == item.estimated_profit
    assert float(saved.profit_margin) == float(item.profit_margin)
    assert saved.decision == item.decision
    assert saved.status is OpportunityStatus.NEW


def test_injected_live_connector_resolution_metadata() -> None:
    listing = MarketListing(
        id="injected-live-001",
        title="Injected Listing",
        brand="Chanel",
        category="wallet",
        condition="Good",
        price=Decimal("100000"),
        currency="JPY",
        market_name="Fashionphile",
        url="https://example.invalid/injected-live-001",
        source_type="LIVE",
        created_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    class _InjectedLive:
        market_name = "Fashionphile"
        source_type = "LIVE"

        def search_products(self, query: str):
            return [listing]

        def get_product(self, url: str):
            return listing if url == listing.url else None

    resolution = MarketConnectorResolver(
        MarketConnectorConfig(enable_live=True, use_fixture=True),
    ).resolve("Fashionphile", injected_connector=_InjectedLive())

    assert resolution.execution is not None
    assert resolution.execution.actual_source == "LIVE"
    assert resolution.connector.search_products("Chanel")[0].title == "Injected Listing"
