"""Pipeline tests for market connector integration with arbitrage and browser."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import run_used_luxury_dashboard_search
from app.store import DashboardResultStore
from marketplace.connectors import MarketListing
from marketplace.connectors.resolver import MarketConnectorResolver
from profit_discovery.cli.discovery_command import (
    build_default_discovery_runner,
    build_production_discovery_pipeline,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner


def test_arbitrage_connector_pipeline_preserves_profit_integrity() -> None:
    runner = build_default_discovery_runner(used_luxury=True)

    direct_result = MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
    )
    direct_candidate = next(
        item for item in direct_result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )

    dashboard_result = run_used_luxury_dashboard_search(
        brand="Chanel",
        category="Wallet",
        market_mode="FIXTURE",
        max_results_per_brand=1,
        runner=MultiBrandDiscoveryRunner(discovery_runner=runner.discovery_runner),
    )

    arbitrage = dashboard_result.snapshot.arbitrage_ranking[0]
    browser_candidate = dashboard_result.snapshot.candidates_by_id[arbitrage.external_id]

    assert direct_candidate.profit_result is not None
    assert browser_candidate.profit_result is not None
    assert browser_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert browser_candidate.profit_result.profit_margin == direct_candidate.profit_result.profit_margin
    assert browser_candidate.profit_result.roi == direct_candidate.profit_result.roi
    assert direct_candidate.buy_decision is not None
    assert browser_candidate.buy_decision is not None
    assert browser_candidate.buy_decision.decision == direct_candidate.buy_decision.decision
    assert arbitrage.market_source
    assert arbitrage.condition
    assert arbitrage.listing_url


def test_market_listing_to_arbitrage_to_browser_flow() -> None:
    store = DashboardResultStore()
    client = TestClient(create_app(result_store=store))
    response = client.post(
        "/search",
        data={
            "brand": "Chanel",
            "category": "Wallet",
            "market_mode": "FIXTURE",
        },
    )

    assert response.status_code == 200
    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.arbitrage_ranking
    assert snapshot.listings_by_id or snapshot.arbitrage_ranking[0].listing_url

    item = snapshot.arbitrage_ranking[0]
    detail_response = client.get(f"/product/{item.external_id}")
    assert detail_response.status_code == 200
    assert item.market_source in detail_response.text
    assert item.condition in detail_response.text


def test_injected_market_connector_can_be_used_by_resolver() -> None:
    listing = MarketListing(
        id="injected-001",
        title="Injected Chanel Wallet",
        brand="Chanel",
        category="wallet",
        condition="Excellent",
        price=100000,
        currency="JPY",
        market_name="Fashionphile",
        url="https://example.invalid/injected-001",
        source_type="INJECTED",
        created_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    class _InjectedConnector:
        market_name = "Fashionphile"
        source_type = "INJECTED"

        def search_products(self, query: str):
            return [listing]

        def get_product(self, url: str):
            return listing if url == listing.url else None

    resolution = MarketConnectorResolver().resolve(
        "Fashionphile",
        injected_connector=_InjectedConnector(),
    )

    assert resolution.mode.value == "INJECTED"
    assert resolution.connector is not None
    assert resolution.connector.search_products("Chanel")[0].title == "Injected Chanel Wallet"
