"""Tests for supplier discovery batch runner."""

from __future__ import annotations

from decimal import Decimal

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import (
    DiscoveryCandidateResult,
    DiscoveryCandidateStatus,
    DiscoveryRunner,
    rank_discovery_results,
)
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.models import BuyDecision, BuyDecisionResult
from profit_intelligence.discovery_models import DiscoveryScore
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType


def _runner() -> DiscoveryRunner:
    supplier_client = FashionphileClient()
    market_connector = SupplierMarketConnector(
        supplier_client=supplier_client,
        market_client=FakeYahooAuctionClient(),
    )
    return DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=market_connector,
    )


def test_discovery_runner_evaluates_multiple_supplier_products() -> None:
    supplier_client = FashionphileClient()
    products = supplier_client.search_products("", max_results=3)

    batch = _runner().evaluate_products(products)

    assert batch.total_products == 3
    assert batch.evaluated_products == 3
    assert len(batch.results) == 3


def test_discovery_runner_isolates_market_failures() -> None:
    products = [
        FashionphileClient().search_products("Chanel wallet", max_results=1)[0],
        SupplierProduct(
            supplier_name="fashionphile",
            external_id="no-market-001",
            title="Unknown Luxury Item",
            brand="UnknownBrand",
            category="misc",
            condition=SupplierType.USED.value,
            purchase_price=100.0,
            currency="USD",
            url="https://example.invalid/unknown",
            image_urls=[],
            availability="in_stock",
        ),
        FashionphileClient().search_products("Louis Vuitton", max_results=1)[0],
    ]

    batch = _runner().evaluate_products(products)

    statuses = [result.status for result in batch.results]
    assert DiscoveryCandidateStatus.NO_MARKET_DATA in statuses
    assert statuses.count(DiscoveryCandidateStatus.SUCCESS) >= 2


def test_rank_discovery_results_puts_buy_first() -> None:
    results = [
        _candidate(decision=BuyDecision.PASS, overall=90.0, profit=50000.0),
        _candidate(decision=BuyDecision.BUY, overall=70.0, profit=10000.0),
        _candidate(decision=BuyDecision.HOLD, overall=80.0, profit=20000.0),
    ]

    ranked = rank_discovery_results(results)

    assert ranked[0].buy_decision is not None
    assert ranked[0].buy_decision.decision is BuyDecision.BUY


def test_rank_discovery_results_sorts_by_profit_within_same_decision() -> None:
    results = [
        _candidate(decision=BuyDecision.HOLD, overall=75.0, profit=15000.0),
        _candidate(decision=BuyDecision.HOLD, overall=75.0, profit=30000.0),
        _candidate(decision=BuyDecision.HOLD, overall=75.0, profit=22000.0),
    ]

    ranked = rank_discovery_results(results)

    profits = [float(result.profit_result.profit_jpy) for result in ranked]
    assert profits == sorted(profits, reverse=True)


def test_full_fashionphile_discovery_runner_flow() -> None:
    runner = _runner()
    products = runner.supplier_client.search_products("Chanel wallet", max_results=1)

    batch = runner.evaluate_products(products)
    ranked = rank_discovery_results(list(batch.results))

    assert batch.total_products == 1
    assert ranked[0].status is DiscoveryCandidateStatus.SUCCESS
    assert ranked[0].market_evaluation is not None
    assert ranked[0].profit_result is not None
    assert ranked[0].discovery_score is not None
    assert ranked[0].buy_decision is not None
    assert ranked[0].profit_result.profit_jpy > 0
    assert ranked[0].buy_decision.decision in {
        BuyDecision.BUY,
        BuyDecision.HOLD,
        BuyDecision.PASS,
    }


def _candidate(
    *,
    decision: BuyDecision,
    overall: float,
    profit: float,
) -> DiscoveryCandidateResult:
    from models.price_result import PriceResult
    from models.product import Product

    product = SupplierProduct(
        supplier_name="fashionphile",
        external_id=f"fp-{decision.value.lower()}",
        title="Sample Item",
        brand="Gucci",
        category="bags",
        condition=SupplierType.USED.value,
        purchase_price=500.0,
        currency="USD",
        url="https://example.invalid/sample",
        image_urls=[],
        availability="in_stock",
    )
    profit_result = PriceResult(
        product=Product(name="Sample Item", brand="Gucci", price=500.0, currency="USD"),
        profit_jpy=Decimal(str(profit)),
        calculation_status="success",
    )
    discovery_score = DiscoveryScore(
        profit_score=overall,
        demand_score=overall,
        brand_score=overall,
        competition_score=overall,
        confidence_score=overall,
        overall_score=overall,
    )
    buy_decision = BuyDecisionResult(
        decision=decision,
        max_purchase_price_jpy=Decimal("100000"),
        target_profit_jpy=Decimal("10000"),
        expected_profit_jpy=Decimal(str(profit)),
        margin_requirement=Decimal("20"),
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=profit_result,
        discovery_score=discovery_score,
        buy_decision=buy_decision,
    )
