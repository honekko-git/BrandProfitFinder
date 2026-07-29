"""Tests for opportunity ranking order."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.opportunity.ranking import rank_opportunities
from profit_discovery.opportunity.scorer import OpportunityScorer
from supplier.models import SupplierProduct, SupplierType


def test_rank_opportunities_orders_by_total_score_descending() -> None:
    scorer = OpportunityScorer()
    opportunities = [
        scorer.evaluate(_candidate(external_id="low", profit_jpy=3000.0, profit_margin=10.0, roi=15.0)),
        scorer.evaluate(_candidate(external_id="high", profit_jpy=25000.0, profit_margin=40.0, roi=120.0)),
        scorer.evaluate(_candidate(external_id="mid", profit_jpy=12000.0, profit_margin=25.0, roi=60.0)),
    ]

    ranked = rank_opportunities(opportunities)

    assert [item.candidate.supplier_product.external_id for item in ranked] == ["high", "mid", "low"]
    assert [item.recommendation_rank for item in ranked] == [1, 2, 3]
    assert ranked[0].score.total_score >= ranked[1].score.total_score >= ranked[2].score.total_score


def test_rank_opportunities_puts_higher_profit_items_first() -> None:
    scorer = OpportunityScorer()
    low_profit = scorer.evaluate(_candidate(external_id="profit-low", profit_jpy=2000.0))
    high_profit = scorer.evaluate(_candidate(external_id="profit-high", profit_jpy=30000.0))

    ranked = rank_opportunities([low_profit, high_profit])

    assert ranked[0].candidate.supplier_product.external_id == "profit-high"
    assert ranked[0].score.profit_score > ranked[1].score.profit_score


def test_rank_opportunities_does_not_mutate_input_candidates() -> None:
    scorer = OpportunityScorer()
    first = scorer.evaluate(_candidate(external_id="a", profit_jpy=5000.0))
    second = scorer.evaluate(_candidate(external_id="b", profit_jpy=15000.0))

    ranked = rank_opportunities([first, second])

    assert first.candidate is ranked[1].candidate or first.candidate.supplier_product.external_id in {
        item.candidate.supplier_product.external_id for item in ranked
    }
    assert all(item.recommendation_rank is not None for item in ranked)


def _candidate(
    *,
    external_id: str,
    profit_jpy: float,
    profit_margin: float = 25.0,
    roi: float = 50.0,
) -> DiscoveryCandidateResult:
    product = SupplierProduct(
        supplier_name="fashionphile",
        external_id=external_id,
        title="Sample Item",
        brand="Gucci",
        category="bags",
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
            product=Product(name="Sample Item", brand="Gucci", price=500.0, currency="USD"),
            profit_jpy=Decimal(str(profit_jpy)),
            profit_margin=Decimal(str(profit_margin)),
            roi=Decimal(str(roi)),
            calculation_status="success",
        ),
        market_evaluation=MarketEvaluationResult(
            supplier_product_id=external_id,
            domestic_market_price=None,
            matched_keyword="Gucci bag",
            confidence_score=0.8,
        ),
    )
