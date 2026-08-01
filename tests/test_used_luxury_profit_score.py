"""Tests for used luxury profit scoring."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.profit_ranking.scorer import (
    WEIGHT_DEMAND,
    WEIGHT_PROFIT,
    WEIGHT_RISK,
    WEIGHT_TURNOVER,
    UsedLuxuryProfitScorer,
)
from profit_intelligence.demand.models import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_used_luxury_profit_score_uses_weighted_formula() -> None:
    candidate = _candidate(external_id="luxury-001", profit_jpy=18000.0, brand="Chanel")
    demand = _demand_profile(query="Chanel Wallet", sold_count=35, sell_through_rate=0.75)

    score = UsedLuxuryProfitScorer().score(candidate, demand)

    expected_total = (
        score.profit_score * WEIGHT_PROFIT
        + score.demand_score * WEIGHT_DEMAND
        + score.turnover_score * WEIGHT_TURNOVER
        + score.risk_score * WEIGHT_RISK
    )
    assert score.total_score == expected_total


def test_used_luxury_profit_score_risk_prefers_lower_brand_risk() -> None:
    demand = _demand_profile(query="Chanel Wallet", sold_count=20, sell_through_rate=0.7)
    scorer = UsedLuxuryProfitScorer()

    low_risk = scorer.score(
        _candidate(external_id="luxury-low-risk", profit_jpy=15000.0, brand="Chanel"),
        demand,
    )
    high_risk = scorer.score(
        _candidate(external_id="luxury-high-risk", profit_jpy=15000.0, brand="Fendi"),
        demand,
    )

    assert low_risk.risk_score > high_risk.risk_score
    assert low_risk.total_score > high_risk.total_score


def test_used_luxury_profit_score_inventory_risk_lowers_risk_score() -> None:
    demand = _demand_profile(query="Chanel Wallet", sold_count=20, sell_through_rate=0.7)
    scorer = UsedLuxuryProfitScorer()
    base = scorer.score(
        _candidate(external_id="luxury-base", profit_jpy=15000.0, brand="Chanel"),
        demand,
    )
    risky = scorer.score(
        _candidate(
            external_id="luxury-risky",
            profit_jpy=15000.0,
            brand="Chanel",
            inventory_risk_score=85.0,
        ),
        demand,
    )

    assert risky.risk_score < base.risk_score


def _candidate(
    *,
    external_id: str,
    profit_jpy: float,
    brand: str,
    inventory_risk_score: float | None = None,
) -> DiscoveryCandidateResult:
    metadata: dict[str, float] = {}
    if inventory_risk_score is not None:
        metadata["inventory_risk_score"] = inventory_risk_score
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
            metadata=metadata,
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
