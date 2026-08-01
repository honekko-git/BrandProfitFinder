"""Tests for used luxury profit ranking."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_discovery.profit_ranking import rank_used_luxury_products
from profit_intelligence.demand.models import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_rank_used_luxury_products_orders_by_total_score() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    opportunities = [
        scorer.evaluate(
            _candidate("lower-profit", profit_jpy=12000.0, brand="Coach"),
            _demand_profile("Coach Wallet", sold_count=10, sell_through_rate=0.5),
        ),
        scorer.evaluate(
            _candidate("higher-profit", profit_jpy=28000.0, brand="Chanel"),
            _demand_profile("Chanel Wallet", sold_count=10, sell_through_rate=0.5),
        ),
    ]

    ranked = rank_used_luxury_products(opportunities)

    assert [item.candidate.supplier_product.external_id for item in ranked] == [
        "higher-profit",
        "lower-profit",
    ]
    assert [item.score.recommendation_rank for item in ranked] == [1, 2]


def test_rank_used_luxury_products_prioritizes_high_turnover_with_equal_profit() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    low_turnover = scorer.evaluate(
        _candidate("turnover-low", profit_jpy=18000.0, brand="Chanel"),
        _demand_profile("Chanel Wallet", sold_count=6, sell_through_rate=0.35),
    )
    high_turnover = scorer.evaluate(
        _candidate("turnover-high", profit_jpy=18000.0, brand="Chanel"),
        _demand_profile("Chanel Wallet", sold_count=52, sell_through_rate=0.85),
    )

    ranked = rank_used_luxury_products([low_turnover, high_turnover])

    assert ranked[0].candidate.supplier_product.external_id == "turnover-high"
    assert ranked[0].score.turnover_score > ranked[1].score.turnover_score


def test_rank_used_luxury_products_excludes_non_used_luxury_brands() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    opportunities = [
        scorer.evaluate(
            _candidate("gucci-item", profit_jpy=30000.0, brand="Gucci"),
            _demand_profile("Gucci Wallet", sold_count=40, sell_through_rate=0.8),
        ),
        scorer.evaluate(
            _candidate("chanel-item", profit_jpy=18000.0, brand="Chanel"),
            _demand_profile("Chanel Wallet", sold_count=20, sell_through_rate=0.7),
        ),
    ]

    ranked = rank_used_luxury_products(opportunities)

    assert len(ranked) == 1
    assert ranked[0].candidate.supplier_product.external_id == "chanel-item"


def _candidate(external_id: str, *, profit_jpy: float, brand: str) -> DiscoveryCandidateResult:
    return DiscoveryCandidateResult(
        supplier_product=SupplierProduct(
            supplier_name="fashionphile",
            external_id=external_id,
            title="Sample Item",
            brand=brand,
            category="wallet",
            condition=SupplierType.USED.value,
            purchase_price=500.0,
            currency="USD",
            url=f"https://example.invalid/{external_id}",
            image_urls=[],
            availability="in_stock",
        ),
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=PriceResult(
            product=Product(name="Sample Item", brand=brand, price=500.0, currency="USD"),
            profit_jpy=Decimal(str(profit_jpy)),
            profit_margin=Decimal("30.0"),
            roi=Decimal("55.0"),
            calculation_status="success",
        ),
        market_evaluation=MarketEvaluationResult(
            supplier_product_id=external_id,
            domestic_market_price=None,
            matched_keyword=f"{brand} wallet",
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
