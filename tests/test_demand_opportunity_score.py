"""Tests for demand-integrated opportunity scoring."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.opportunity.demand_scorer import (
    WEIGHT_DEMAND,
    WEIGHT_MARGIN,
    WEIGHT_MARKET_CONFIDENCE,
    WEIGHT_PROFIT,
    WEIGHT_ROI,
    WEIGHT_SUPPLIER,
    DemandIntegratedOpportunityScorer,
)
from profit_intelligence.demand import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_demand_integrated_score_uses_weighted_formula() -> None:
    candidate = _candidate(external_id="demand-001", profit_jpy=15000.0)
    demand = _demand_profile(query="Chanel Wallet", sold_count=35, sell_through_rate=0.75)

    score = DemandIntegratedOpportunityScorer().score(candidate, demand)

    expected_total = (
        score.profit_score * WEIGHT_PROFIT
        + score.margin_score * WEIGHT_MARGIN
        + score.roi_score * WEIGHT_ROI
        + score.market_confidence_score * WEIGHT_MARKET_CONFIDENCE
        + score.supplier_score * WEIGHT_SUPPLIER
        + score.demand_score * WEIGHT_DEMAND
    )
    assert score.total_score == expected_total


def test_demand_integrated_score_applies_demand_weight() -> None:
    candidate = _candidate(external_id="demand-002", profit_jpy=12000.0)
    low_demand = _demand_profile(query="Coach Wallet", sold_count=4, sell_through_rate=0.3)
    high_demand = _demand_profile(query="Louis Vuitton Wallet", sold_count=52, sell_through_rate=0.82)
    scorer = DemandIntegratedOpportunityScorer()

    low_score = scorer.score(candidate, low_demand)
    high_score = scorer.score(candidate, high_demand)

    assert high_score.demand_score > low_score.demand_score
    assert high_score.total_score > low_score.total_score


def test_demand_integrated_score_clamps_total_to_range() -> None:
    candidate = _candidate(external_id="demand-003", profit_jpy=50000.0)
    demand = _demand_profile(query="Hermes Bag", sold_count=100, sell_through_rate=0.95)

    score = DemandIntegratedOpportunityScorer().score(candidate, demand)

    assert 0.0 <= score.total_score <= 100.0
    assert score.demand_score == demand.demand_score


def _candidate(*, external_id: str, profit_jpy: float) -> DiscoveryCandidateResult:
    product = SupplierProduct(
        supplier_name="fashionphile",
        external_id=external_id,
        title="Sample Item",
        brand="Chanel",
        category="wallets",
        condition=SupplierType.USED.value,
        purchase_price=500.0,
        currency="USD",
        url=f"https://example.invalid/{external_id}",
        image_urls=[],
        availability="in_stock",
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=PriceResult(
            product=Product(name="Sample Item", brand="Chanel", price=500.0, currency="USD"),
            profit_jpy=Decimal(str(profit_jpy)),
            profit_margin=Decimal("30.0"),
            roi=Decimal("55.0"),
            calculation_status="success",
        ),
        market_evaluation=MarketEvaluationResult(
            supplier_product_id=external_id,
            domestic_market_price=None,
            matched_keyword="Chanel wallet",
            confidence_score=0.8,
        ),
    )


def _demand_profile(*, query: str, sold_count: int, sell_through_rate: float) -> SalesDemandProfile:
    profile = SalesDemandProfile(
        query=query,
        period_days=30,
        sold_count=sold_count,
        average_sold_price_jpy=150000.0,
        sell_through_rate=sell_through_rate,
        demand_score=0.0,
    )
    return SalesDemandProfile(
        query=profile.query,
        period_days=profile.period_days,
        sold_count=profile.sold_count,
        average_sold_price_jpy=profile.average_sold_price_jpy,
        sell_through_rate=profile.sell_through_rate,
        demand_score=profile.calculate_demand_score(),
    )
