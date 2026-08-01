"""Pipeline tests for discovery CLI live market runtime activation."""

from __future__ import annotations

from decimal import Decimal

import httpx

from marketplace.domestic_market import FakeYahooAuctionTransport
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    build_domestic_market_runtime_config,
    run_discovery_command,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus
from profit_discovery.market_connector import SupplierMarketConnector
from profit_intelligence.discovery_engine import DiscoveryEngine
from price_compare.profit_calculator import ProfitCalculator
from models.product import Product
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate


def _fixture_matching_transport() -> FakeYahooAuctionTransport:
    return FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet Black Caviar", "sold_price": 155000},
            {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
            {"title": "Chanel Long Wallet Quilted", "sold_price": 165000},
            {"title": "Chanel Wallet Lambskin", "sold_price": 158000},
            {"title": "Chanel Compact Wallet", "sold_price": 162000},
        ]
    )


def _candidate_to_product(candidate: dict[str, object], *, exchange_rate: float = 150.0) -> Product:
    return Product(
        name=str(candidate["name"]),
        brand=str(candidate["brand"]),
        price=float(candidate["purchase_price"]),
        currency=str(candidate["currency"]),
        store_name=str(candidate["source"]),
        url=str(candidate.get("url") or ""),
        model=str(candidate.get("model_number") or ""),
        exchange_rate=exchange_rate,
    )


def _evaluate_fixture_baseline():
    fixture_runner = build_default_discovery_runner()
    supplier_client = FashionphileClient()
    supplier_product = supplier_client.search_products("Chanel wallet", max_results=1)[0]
    connector = fixture_runner.discovery_runner.market_connector
    evaluation = connector.evaluate_product(supplier_product)

    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate)
    profit = ProfitCalculator().calculate(
        product,
        Decimal(str(int(evaluation.domestic_market_price.average_price_jpy))),  # type: ignore[union-attr]
        domestic_market="yahoo_auction",
    )
    discovery = DiscoveryEngine().score(profit)
    decision = BuyDecisionEngine().decide(profit, discovery)
    return profit, decision


def test_live_market_runtime_pipeline_preserves_profit_integrity() -> None:
    transport = _fixture_matching_transport()
    live_runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )

    baseline_profit, baseline_decision = _evaluate_fixture_baseline()

    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=live_runner,
        injected_transport=transport,
    )
    candidate = next(
        item for item in result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )

    assert candidate.profit_result is not None
    assert candidate.buy_decision is not None
    assert candidate.profit_result.profit_jpy == baseline_profit.profit_jpy
    assert candidate.profit_result.profit_margin == baseline_profit.profit_margin
    assert candidate.profit_result.roi == baseline_profit.roi
    assert candidate.buy_decision.decision == baseline_decision.decision


def test_live_market_runtime_pipeline_uses_resolver_live_client() -> None:
    transport = _fixture_matching_transport()
    live_runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )
    connector = live_runner.discovery_runner.market_connector
    assert isinstance(connector, SupplierMarketConnector)
    assert connector.market_aggregator is not None

    client = connector.market_aggregator.clients[0][1]
    prices = client.search_sold_items("Chanel wallet", max_results=20)

    assert prices == [155000, 160000, 165000, 158000, 162000]


def test_live_market_runtime_pipeline_http_transport_path(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "cli-test-key")
    monkeypatch.setattr(
        "config.settings.YAHOO_AUCTION_DATA_SOURCE",
        "https://example.invalid/yahoo-auction/sold",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {"title": "Chanel Classic Wallet Black Caviar", "sold_price": 155000},
                    {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
                    {"title": "Chanel Long Wallet Quilted", "sold_price": 165000},
                    {"title": "Chanel Wallet Lambskin", "sold_price": 158000},
                    {"title": "Chanel Compact Wallet", "sold_price": 162000},
                ]
            },
        )

    from marketplace.domestic_market.yahoo_auction import YahooAuctionHTTPTransport

    http_transport = YahooAuctionHTTPTransport(
        config=build_domestic_market_runtime_config(live_market=True),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    live_runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=http_transport,
    )

    baseline_profit, baseline_decision = _evaluate_fixture_baseline()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=live_runner,
        injected_transport=http_transport,
    )
    candidate = next(
        item for item in result.ranked_candidates if item.status is DiscoveryCandidateStatus.SUCCESS
    )

    assert candidate.profit_result is not None
    assert candidate.buy_decision is not None
    assert candidate.profit_result.profit_jpy == baseline_profit.profit_jpy
    assert candidate.profit_result.profit_margin == baseline_profit.profit_margin
    assert candidate.profit_result.roi == baseline_profit.roi
    assert candidate.buy_decision.decision == baseline_decision.decision
