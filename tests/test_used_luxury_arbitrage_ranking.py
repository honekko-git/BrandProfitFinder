"""Tests for used luxury arbitrage ranking."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.arbitrage import create_arbitrage_ranking
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_intelligence.demand.models import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_create_arbitrage_ranking_orders_by_arbitrage_score() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    opportunities = [
        scorer.evaluate(
            _candidate("lower-profit", profit_jpy=12000.0, purchase_jpy=90000, sale_jpy=130000),
            _demand_profile("Coach Wallet", sold_count=8, sell_through_rate=0.4),
        ),
        scorer.evaluate(
            _candidate("higher-profit", profit_jpy=32000.0, purchase_jpy=100000, sale_jpy=180000),
            _demand_profile("Chanel Wallet", sold_count=40, sell_through_rate=0.8),
        ),
    ]

    ranked = create_arbitrage_ranking(opportunities)

    assert [item.external_id for item in ranked] == ["higher-profit", "lower-profit"]
    assert [item.recommendation_rank for item in ranked] == [1, 2]


def test_create_arbitrage_ranking_prioritizes_demand_with_similar_profit() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    low_demand = scorer.evaluate(
        _candidate("demand-low", profit_jpy=18000.0, purchase_jpy=95000, sale_jpy=150000),
        _demand_profile("Chanel Wallet", sold_count=6, sell_through_rate=0.35),
    )
    high_demand = scorer.evaluate(
        _candidate("demand-high", profit_jpy=18000.0, purchase_jpy=95000, sale_jpy=150000),
        _demand_profile("Chanel Wallet", sold_count=52, sell_through_rate=0.85),
    )

    ranked = create_arbitrage_ranking([low_demand, high_demand])

    assert ranked[0].external_id == "demand-high"
    assert ranked[0].demand_score > ranked[1].demand_score


def test_create_arbitrage_ranking_excludes_new_products() -> None:
    scorer = DemandIntegratedOpportunityScorer()
    opportunities = [
        scorer.evaluate(
            _candidate("new-item", profit_jpy=30000.0, purchase_jpy=90000, sale_jpy=170000, condition="NEW"),
            _demand_profile("Chanel Wallet", sold_count=30, sell_through_rate=0.7),
        ),
        scorer.evaluate(
            _candidate("used-item", profit_jpy=18000.0, purchase_jpy=95000, sale_jpy=150000),
            _demand_profile("Chanel Wallet", sold_count=20, sell_through_rate=0.7),
        ),
    ]

    ranked = create_arbitrage_ranking(opportunities)

    assert len(ranked) == 1
    assert ranked[0].external_id == "used-item"


def _candidate(
    external_id: str,
    *,
    profit_jpy: float,
    purchase_jpy: int,
    sale_jpy: int,
    condition: str = SupplierType.USED.value,
) -> DiscoveryCandidateResult:
    return DiscoveryCandidateResult(
        supplier_product=SupplierProduct(
            supplier_name="fashionphile",
            external_id=external_id,
            title="Sample Item",
            brand="Chanel",
            category="wallet",
            condition=condition,
            purchase_price=500.0,
            currency="USD",
            url=f"https://example.invalid/{external_id}",
            image_urls=[],
            availability="in_stock",
        ),
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=PriceResult(
            product=Product(name="Sample Item", brand="Chanel", price=500.0, currency="USD"),
            purchase_price_jpy=Decimal(str(purchase_jpy)),
            domestic_sale_price_jpy=Decimal(str(sale_jpy)),
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
            metadata={"sources": ["yahoo_auction", "mercari"]},
        ),
        buy_decision=None,
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
