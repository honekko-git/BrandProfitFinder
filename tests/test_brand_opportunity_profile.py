"""Tests for BrandOpportunityProfile score calculation."""

from __future__ import annotations

from profit_discovery.brand_catalog import BrandOpportunityProfile


def test_brand_opportunity_profile_calculates_weighted_score() -> None:
    profile = BrandOpportunityProfile(
        name="Chanel",
        profit_score=90.0,
        demand_score=80.0,
        turnover_score=70.0,
        risk_score=20.0,
        capital_level="HIGH",
    )

    score = profile.calculate_opportunity_score()

    expected = 90.0 * 0.30 + 80.0 * 0.30 + 70.0 * 0.20 + 80.0 * 0.20
    assert score == round(expected, 2)


def test_brand_opportunity_profile_clamps_component_scores() -> None:
    profile = BrandOpportunityProfile(
        name="Test Brand",
        profit_score=150.0,
        demand_score=-10.0,
        turnover_score=50.0,
        risk_score=120.0,
        capital_level="B",
    )

    score = profile.calculate_opportunity_score()

    assert 0.0 <= score <= 100.0


def test_brand_opportunity_profile_lower_risk_increases_score() -> None:
    low_risk = BrandOpportunityProfile(
        name="Low Risk",
        profit_score=80.0,
        demand_score=80.0,
        turnover_score=80.0,
        risk_score=10.0,
        capital_level="A",
    )
    high_risk = BrandOpportunityProfile(
        name="High Risk",
        profit_score=80.0,
        demand_score=80.0,
        turnover_score=80.0,
        risk_score=60.0,
        capital_level="A",
    )

    assert low_risk.calculate_opportunity_score() > high_risk.calculate_opportunity_score()
