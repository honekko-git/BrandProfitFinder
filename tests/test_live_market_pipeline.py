"""Pipeline tests for live domestic market resolver integration."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketClientResolver,
    DomesticMarketRuntimeConfig,
    DomesticMarketSource,
)
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


def _evaluate_with_resolver(config: DomesticMarketRuntimeConfig | None = None):
    supplier_client = FashionphileClient()
    resolution = DomesticMarketClientResolver(config=config).resolve_yahoo_auction()
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
    return price_result, decision


def test_live_market_pipeline_preserves_profit_margin_roi_and_decision() -> None:
    baseline_profit, baseline_decision = _evaluate_with_resolver(
        DomesticMarketRuntimeConfig.default(),
    )
    resolver_profit, resolver_decision = _evaluate_with_resolver(
        DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-key",
        ),
    )

    assert baseline_profit.profit_jpy == resolver_profit.profit_jpy
    assert baseline_profit.profit_margin == resolver_profit.profit_margin
    assert baseline_profit.roi == resolver_profit.roi
    assert baseline_decision.decision == resolver_decision.decision


def test_live_market_pipeline_runs_discovery_runner_with_resolver_client() -> None:
    resolution = DomesticMarketClientResolver().resolve_yahoo_auction()
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
    pipeline_profit, pipeline_decision = _evaluate_with_resolver()

    batch = runner.evaluate_products([supplier_product])
    candidate = next(result for result in batch.results if result.status is DiscoveryCandidateStatus.SUCCESS)

    assert candidate.profit_result is not None
    assert candidate.buy_decision is not None
    assert candidate.profit_result.profit_jpy == pipeline_profit.profit_jpy
    assert candidate.profit_result.profit_margin == pipeline_profit.profit_margin
    assert candidate.profit_result.roi == pipeline_profit.roi
    assert candidate.buy_decision.decision == pipeline_decision.decision
