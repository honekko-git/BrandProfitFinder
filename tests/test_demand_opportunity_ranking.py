"""Tests for demand-integrated opportunity ranking."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.opportunity.demand_ranking import rank_demand_integrated_opportunities
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_intelligence.demand import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_rank_demand_integrated_opportunities_orders_by_total_score() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    opportunities = [
        scorer.evaluate(
            _candidate("low-demand", profit_jpy=20000.0),
            _demand_profile("Coach Wallet", sold_count=6, sell_through_rate=0.4),
        ),
        scorer.evaluate(
            _candidate("high-demand", profit_jpy=20000.0),
            _demand_profile("Louis Vuitton Wallet", sold_count=52, sell_through_rate=0.82),
        ),
    ]

    ranked = rank_demand_integrated_opportunities(opportunities)

    assert [item.candidate.supplier_product.external_id for item in ranked] == [
        "high-demand",
        "low-demand",
    ]
    assert [item.recommendation_rank for item in ranked] == [1, 2]


def test_rank_demand_integrated_opportunities_puts_high_demand_first_with_equal_profit() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    low = scorer.evaluate(
        _candidate("profit-same-a", profit_jpy=18000.0),
        _demand_profile("Coach Wallet", sold_count=8, sell_through_rate=0.45),
    )
    high = scorer.evaluate(
        _candidate("profit-same-b", profit_jpy=18000.0),
        _demand_profile("Chanel Wallet", sold_count=35, sell_through_rate=0.75),
    )

    ranked = rank_demand_integrated_opportunities([low, high])

    assert ranked[0].candidate.supplier_product.external_id == "profit-same-b"
    assert ranked[0].score.demand_score > ranked[1].score.demand_score


def _candidate(external_id: str, *, profit_jpy: float) -> DiscoveryCandidateResult:
    return DiscoveryCandidateResult(
        supplier_product=SupplierProduct(
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
        ),
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


def _demand_profile(query: str, *, sold_count: int, sell_through_rate: float) -> SalesDemandProfile:
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
