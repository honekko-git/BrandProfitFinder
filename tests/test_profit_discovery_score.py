"""Tests for discovery profit score normalization."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from profit_intelligence.discovery_engine import DiscoveryEngine, DiscoveryWeights
from profit_intelligence.scorers.profit_scorer import DiscoveryProfitScorer


def test_discovery_profit_scorer_high_profit_high_margin() -> None:
    result = PriceResult(
        profit_jpy=Decimal("20000"),
        profit_margin=Decimal("35"),
        roi=Decimal("120"),
        calculation_status="success",
    )

    component = DiscoveryProfitScorer().score(result)

    assert component.score >= 70
    assert any("High" in reason or "Strong" in reason for reason in component.reasons)


def test_weighted_overall_score_is_deterministic() -> None:
    engine = DiscoveryEngine(weights=DiscoveryWeights())
    overall = engine._weighted_overall(
        profit=80.0,
        demand=60.0,
        brand=100.0,
        competition=70.0,
        confidence=90.0,
    )

    assert overall == 78.5


def test_discovery_engine_returns_all_component_scores() -> None:
    result = PriceResult(
        profit_jpy=Decimal("15000"),
        profit_margin=Decimal("25"),
        roi=Decimal("80"),
        calculation_status="success",
        metadata={
            "brand": "gucci",
            "identity_confidence_score": 0.9,
            "sales_last_30_days": 40,
            "listing_count": 2,
        },
    )

    discovery = DiscoveryEngine().score(result)

    assert 0 <= discovery.profit_score <= 100
    assert 0 <= discovery.demand_score <= 100
    assert 0 <= discovery.brand_score <= 100
    assert 0 <= discovery.competition_score <= 100
    assert 0 <= discovery.confidence_score <= 100
    assert 0 <= discovery.overall_score <= 100
