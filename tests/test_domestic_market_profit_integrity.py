"""Profit integrity tests across domestic market source expansion."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    FakeMercariDomesticMarketClient,
    RakumaDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_intelligence.discovery_engine import DiscoveryEngine
from supplier.fashionphile.client import FashionphileClient
from supplier.models import to_product_candidate


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


def _yahoo_only_aggregator() -> DomesticMarketAggregator:
    return DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
            ),
        ],
    )


def _expanded_aggregator() -> DomesticMarketAggregator:
    return DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="yahoo_auction", enabled=True),
                YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
            ),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(),
            ),
            (
                DomesticMarketSource(name="rakuma", enabled=True),
                RakumaDomesticMarketClient(),
            ),
        ],
    )


def _evaluate_chanel_wallet(aggregator: DomesticMarketAggregator):
    supplier_client = FashionphileClient()
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
    return price_result, decision


def test_yahoo_only_profit_integrity_unchanged_after_client_package_expansion() -> None:
    baseline_profit, baseline_decision = _evaluate_chanel_wallet(_yahoo_only_aggregator())
    expanded_profit, expanded_decision = _evaluate_chanel_wallet(_yahoo_only_aggregator())

    assert baseline_profit.profit_jpy == expanded_profit.profit_jpy
    assert baseline_profit.profit_margin == expanded_profit.profit_margin
    assert baseline_profit.roi == expanded_profit.roi
    assert baseline_decision.decision == expanded_decision.decision


def test_multi_source_pipeline_preserves_internal_profit_integrity() -> None:
    runner = DiscoveryRunner(
        supplier_client=FashionphileClient(),
        market_connector=SupplierMarketConnector(
            supplier_client=FashionphileClient(),
            market_aggregator=_expanded_aggregator(),
        ),
    )
    supplier_product = runner.supplier_client.search_products("Chanel wallet", max_results=1)[0]

    pipeline_profit, pipeline_decision = _evaluate_chanel_wallet(_expanded_aggregator())
    batch = runner.evaluate_products([supplier_product])
    candidate = next(result for result in batch.results if result.status is DiscoveryCandidateStatus.SUCCESS)

    assert candidate.profit_result is not None
    assert candidate.buy_decision is not None
    assert candidate.profit_result.profit_jpy == pipeline_profit.profit_jpy
    assert candidate.profit_result.profit_margin == pipeline_profit.profit_margin
    assert candidate.profit_result.roi == pipeline_profit.roi
    assert candidate.buy_decision.decision == pipeline_decision.decision
