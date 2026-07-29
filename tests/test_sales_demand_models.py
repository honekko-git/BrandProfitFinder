"""Tests for sales demand profile scoring."""

from __future__ import annotations

import pytest

from profit_intelligence.demand import SalesDemandProfile


def test_sales_demand_profile_calculates_high_volume_score() -> None:
    profile = SalesDemandProfile(
        query="Louis Vuitton Wallet",
        period_days=30,
        sold_count=55,
        average_sold_price_jpy=150000.0,
        sell_through_rate=0.85,
        demand_score=0.0,
    )

    score = profile.calculate_demand_score()

    assert 90.0 <= score <= 100.0


def test_sales_demand_profile_applies_sell_through_bonus() -> None:
    base = SalesDemandProfile(
        query="Chanel Wallet",
        period_days=30,
        sold_count=35,
        average_sold_price_jpy=160000.0,
        sell_through_rate=0.4,
        demand_score=0.0,
    )
    boosted = SalesDemandProfile(
        query="Chanel Wallet",
        period_days=30,
        sold_count=35,
        average_sold_price_jpy=160000.0,
        sell_through_rate=0.82,
        demand_score=0.0,
    )

    assert boosted.calculate_demand_score() == pytest.approx(base.calculate_demand_score() + 10.0)


def test_sales_demand_profile_clamps_score_to_range() -> None:
    profile = SalesDemandProfile(
        query="Test Query",
        period_days=30,
        sold_count=200,
        average_sold_price_jpy=100000.0,
        sell_through_rate=0.95,
        demand_score=0.0,
    )

    assert profile.calculate_demand_score() == 100.0


def test_sales_demand_profile_scores_low_volume_below_five() -> None:
    profile = SalesDemandProfile(
        query="Low Demand",
        period_days=30,
        sold_count=3,
        average_sold_price_jpy=50000.0,
        sell_through_rate=0.2,
        demand_score=0.0,
    )

    score = profile.calculate_demand_score()

    assert 0.0 <= score <= 40.0
