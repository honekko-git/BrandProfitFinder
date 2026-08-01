"""Pipeline tests for Yahoo Auction HTTP transport through profit calculation."""

from __future__ import annotations

from decimal import Decimal

import httpx

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketClientResolver,
    DomesticMarketRuntimeConfig,
    DomesticMarketSource,
    TransportMode,
    YahooAuctionHTTPTransport,
    YahooAuctionLiveDomesticMarketClient,
)
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate


def _fixture_matching_payload() -> dict[str, object]:
    return {
        "items": [
            {"title": "Chanel Classic Wallet Black Caviar", "sold_price": 155000},
            {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
            {"title": "Chanel Long Wallet Quilted", "sold_price": 165000},
            {"title": "Chanel Wallet Lambskin", "sold_price": 158000},
            {"title": "Chanel Compact Wallet", "sold_price": 162000},
        ]
    }


def _http_transport() -> YahooAuctionHTTPTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture_matching_payload())

    return YahooAuctionHTTPTransport(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
            timeout_seconds=10,
            retry_count=1,
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
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


def _evaluate_with_http_transport():
    supplier_client = FashionphileClient()
    resolution = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
        ),
    ).resolve_yahoo_auction(injected_transport=_http_transport())
    assert resolution.client is not None

    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                resolution.client,
            ),
        ],
    )
    connector = SupplierMarketConnector(
        supplier_client=supplier_client,
        market_aggregator=aggregator,
    )
    supplier_product = supplier_client.search_products("Chanel wallet", max_results=1)[0]
    evaluation = connector.evaluate_product(supplier_product)

    candidate = to_product_candidate(supplier_product)
    product = _candidate_to_product(candidate)
    calculator = ProfitCalculator()
    price_result = calculator.calculate(
        product,
        Decimal(str(int(evaluation.domestic_market_price.average_price_jpy))),  # type: ignore[union-attr]
        domestic_market="yahoo_auction",
    )
    price_result.metadata.update(
        {
            "brand": supplier_product.brand.lower(),
            "identity_confidence_score": 0.85,
            "listing_count": evaluation.metadata.get("sample_count", 1),
            "market_signal_confidence_score": evaluation.confidence_score,
        }
    )
    discovery = DiscoveryEngine().score(price_result)
    decision = BuyDecisionEngine().decide(price_result, discovery)
    return evaluation, price_result, decision


def test_yahoo_http_pipeline_preserves_profit_integrity() -> None:
    baseline_resolution = DomesticMarketClientResolver().resolve_yahoo_auction()
    assert baseline_resolution.client is not None

    supplier_client = FashionphileClient()
    supplier_product = supplier_client.search_products("Chanel wallet", max_results=1)[0]
    baseline_connector = SupplierMarketConnector(
        supplier_client=supplier_client,
        market_aggregator=DomesticMarketAggregator(
            clients=[
                (
                    DomesticMarketSource(name="yahoo_auction", enabled=True),
                    baseline_resolution.client,
                ),
            ],
        ),
    )
    baseline_evaluation = baseline_connector.evaluate_product(supplier_product)

    http_evaluation, http_profit, http_decision = _evaluate_with_http_transport()
    direct_client = YahooAuctionLiveDomesticMarketClient(transport=_http_transport())
    direct_prices = direct_client.search_sold_items("Chanel wallet", max_results=20)

    assert direct_prices == [155000, 160000, 165000, 158000, 162000]
    assert http_evaluation.domestic_market_price is not None
    assert baseline_evaluation.domestic_market_price is not None
    assert http_evaluation.domestic_market_price.average_price_jpy == baseline_evaluation.domestic_market_price.average_price_jpy

    baseline_candidate = to_product_candidate(supplier_product)
    baseline_product = _candidate_to_product(baseline_candidate)
    baseline_profit = ProfitCalculator().calculate(
        baseline_product,
        Decimal(str(int(baseline_evaluation.domestic_market_price.average_price_jpy))),  # type: ignore[union-attr]
        domestic_market="yahoo_auction",
    )
    baseline_discovery = DiscoveryEngine().score(baseline_profit)
    baseline_decision = BuyDecisionEngine().decide(baseline_profit, baseline_discovery)

    assert http_profit.profit_jpy == baseline_profit.profit_jpy
    assert http_profit.profit_margin == baseline_profit.profit_margin
    assert http_profit.roi == baseline_profit.roi
    assert http_decision.decision == baseline_decision.decision


def test_yahoo_http_pipeline_falls_back_to_fixture_on_transport_error() -> None:
    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server down"})

    failing_transport = YahooAuctionHTTPTransport(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
            retry_count=1,
        ),
        client=httpx.Client(transport=httpx.MockTransport(failing_handler)),
    )
    resolution = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
            retry_count=1,
        ),
    ).resolve_yahoo_auction(injected_transport=failing_transport)
    assert resolution.client is not None

    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)
    assert prices == [155000, 160000, 165000, 158000, 162000]


def test_yahoo_http_pipeline_runs_discovery_runner() -> None:
    resolution = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
        ),
    ).resolve_yahoo_auction(injected_transport=_http_transport())
    assert resolution.client is not None

    runner = DiscoveryRunner(
        supplier_client=FashionphileClient(),
        market_connector=SupplierMarketConnector(
            supplier_client=FashionphileClient(),
            market_aggregator=DomesticMarketAggregator(
                clients=[
                    (
                        DomesticMarketSource(name="yahoo_auction", enabled=True),
                        resolution.client,
                    ),
                ],
            ),
        ),
    )
    supplier_product = runner.supplier_client.search_products("Chanel wallet", max_results=1)[0]
    _, pipeline_profit, pipeline_decision = _evaluate_with_http_transport()

    batch = runner.evaluate_products([supplier_product])
    candidate = next(result for result in batch.results if result.status is DiscoveryCandidateStatus.SUCCESS)

    assert candidate.profit_result is not None
    assert candidate.buy_decision is not None
    assert candidate.profit_result.profit_jpy == pipeline_profit.profit_jpy
    assert candidate.profit_result.profit_margin == pipeline_profit.profit_margin
    assert candidate.profit_result.roi == pipeline_profit.roi
    assert candidate.buy_decision.decision == pipeline_decision.decision
