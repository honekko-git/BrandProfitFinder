"""Tests for opportunity score generation and weighting."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.opportunity.scorer import (
    WEIGHT_MARGIN,
    WEIGHT_MARKET_CONFIDENCE,
    WEIGHT_PROFIT,
    WEIGHT_ROI,
    WEIGHT_SUPPLIER,
    OpportunityScorer,
)
from supplier.models import SupplierProduct, SupplierType


def test_opportunity_scorer_builds_component_scores() -> None:
    candidate = _candidate(
        profit_jpy=15000.0,
        profit_margin=35.0,
        roi=80.0,
        market_confidence=0.8,
        supplier_name="fashionphile",
    )

    score = OpportunityScorer().score(candidate)

    assert 0.0 <= score.profit_score <= 100.0
    assert 0.0 <= score.margin_score <= 100.0
    assert 0.0 <= score.roi_score <= 100.0
    assert score.market_confidence_score == 80.0
    assert score.supplier_score == 90.0
    assert 0.0 <= score.total_score <= 100.0


def test_opportunity_total_score_uses_weighted_formula() -> None:
    candidate = _candidate(
        profit_jpy=15000.0,
        profit_margin=35.0,
        roi=80.0,
        market_confidence=0.5,
        supplier_name="fashionphile",
    )
    score = OpportunityScorer().score(candidate)

    expected_total = (
        score.profit_score * WEIGHT_PROFIT
        + score.margin_score * WEIGHT_MARGIN
        + score.roi_score * WEIGHT_ROI
        + score.market_confidence_score * WEIGHT_MARKET_CONFIDENCE
        + score.supplier_score * WEIGHT_SUPPLIER
    )

    assert score.total_score == expected_total


def test_opportunity_scorer_uses_supplier_reliability_defaults() -> None:
    fashionphile = OpportunityScorer().score(_candidate(supplier_name="fashionphile"))
    therealreal = OpportunityScorer().score(_candidate(supplier_name="therealreal"))
    vestiaire = OpportunityScorer().score(_candidate(supplier_name="vestiaire"))
    unknown = OpportunityScorer().score(_candidate(supplier_name="unknown-supplier"))

    assert fashionphile.supplier_score == 90.0
    assert therealreal.supplier_score == 85.0
    assert vestiaire.supplier_score == 85.0
    assert unknown.supplier_score == 50.0


def test_opportunity_scorer_returns_zero_scores_for_failed_candidates() -> None:
    candidate = DiscoveryCandidateResult(
        supplier_product=_supplier_product("failed-001"),
        status=DiscoveryCandidateStatus.NO_MARKET_DATA,
    )

    score = OpportunityScorer().score(candidate)

    assert score.profit_score == 0.0
    assert score.margin_score == 0.0
    assert score.roi_score == 0.0
    assert score.market_confidence_score == 0.0
    assert score.total_score >= 0.0


def _candidate(
    *,
    profit_jpy: float = 10000.0,
    profit_margin: float = 25.0,
    roi: float = 50.0,
    market_confidence: float = 0.8,
    supplier_name: str = "fashionphile",
) -> DiscoveryCandidateResult:
    product = _supplier_product("sample-001", supplier_name=supplier_name)
    profit_result = PriceResult(
        product=Product(name="Sample Item", brand="Gucci", price=500.0, currency="USD"),
        profit_jpy=Decimal(str(profit_jpy)),
        profit_margin=Decimal(str(profit_margin)),
        roi=Decimal(str(roi)),
        calculation_status="success",
    )
    market_evaluation = MarketEvaluationResult(
        supplier_product_id=product.external_id,
        domestic_market_price=None,
        matched_keyword="Gucci bag",
        confidence_score=market_confidence,
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=profit_result,
        market_evaluation=market_evaluation,
    )


def _supplier_product(external_id: str, *, supplier_name: str = "fashionphile") -> SupplierProduct:
    return SupplierProduct(
        supplier_name=supplier_name,
        external_id=external_id,
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
