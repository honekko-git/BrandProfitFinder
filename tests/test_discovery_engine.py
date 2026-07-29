"""Tests for the profit discovery scoring engine."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from profit_intelligence.discovery_engine import DiscoveryEngine, attach_discovery_score_metadata
from ranking_foundation.discovery_ranking import rank_by_discovery_score


def test_discovery_engine_generates_reasons_and_warnings() -> None:
    result = PriceResult(
        profit_jpy=Decimal("18000"),
        profit_margin=Decimal("30"),
        roi=Decimal("90"),
        calculation_status="success",
        metadata={
            "brand": "gucci",
            "identity_confidence_score": 0.92,
            "listing_count": 1,
        },
    )

    discovery = DiscoveryEngine().score(result)

    assert discovery.overall_score >= 70
    assert discovery.reasons
    assert isinstance(discovery.warnings, tuple)


def test_discovery_engine_warns_when_demand_data_missing() -> None:
    result = PriceResult(
        profit_jpy=Decimal("5000"),
        profit_margin=Decimal("12"),
        roi=Decimal("20"),
        calculation_status="success",
        metadata={"brand": "unknown-label"},
    )

    discovery = DiscoveryEngine().score(result)

    assert "Demand data unavailable." in discovery.warnings


def test_attach_discovery_score_metadata_preserves_profit_fields() -> None:
    result = PriceResult(
        profit_jpy=Decimal("12000"),
        profit_margin=Decimal("22"),
        roi=Decimal("55"),
        calculation_status="success",
        metadata={"brand": "prada", "identity_confidence_score": 0.8},
    )
    before_profit = result.profit_jpy
    before_margin = result.profit_margin
    before_roi = result.roi

    discovery = DiscoveryEngine().score(result)
    attach_discovery_score_metadata(result, discovery)

    assert result.profit_jpy == before_profit
    assert result.profit_margin == before_margin
    assert result.roi == before_roi
    assert result.metadata["discovery_overall_score"] == discovery.overall_score
    assert result.metadata["discovery_reasons"]


def test_rank_by_discovery_score_orders_by_overall_then_profit() -> None:
    first = PriceResult(profit_jpy=Decimal("10000"), calculation_status="success")
    second = PriceResult(profit_jpy=Decimal("20000"), calculation_status="success")
    engine = DiscoveryEngine()
    scores = [
        engine.score(first, metadata={"brand": "gucci", "identity_confidence_score": 0.9, "listing_count": 1}),
        engine.score(second, metadata={"brand": "unknown", "identity_confidence_score": 0.2, "listing_count": 12}),
    ]

    ranked = rank_by_discovery_score([first, second], scores)

    assert ranked[0] is first
