"""Tests for used luxury arbitrage scoring."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.arbitrage.scorer import (
    WEIGHT_DEMAND,
    WEIGHT_PROFIT_DIFFERENCE,
    WEIGHT_PROFIT_MARGIN,
    WEIGHT_TURNOVER,
    ArbitrageScorer,
)


def test_arbitrage_score_uses_weighted_formula() -> None:
    opportunity = _opportunity(
        price_difference=Decimal("25000"),
        profit_margin=Decimal("32.0"),
        demand_score=85.0,
        turnover_score=78.0,
    )

    score = ArbitrageScorer().score(opportunity)

    expected_total = (
        score.profit_difference_score * WEIGHT_PROFIT_DIFFERENCE
        + score.profit_margin_score * WEIGHT_PROFIT_MARGIN
        + score.demand_score * WEIGHT_DEMAND
        + score.turnover_score * WEIGHT_TURNOVER
    )
    assert score.total_score == expected_total


def test_arbitrage_score_clamps_total_to_range() -> None:
    opportunity = _opportunity(
        price_difference=Decimal("50000"),
        profit_margin=Decimal("45.0"),
        demand_score=95.0,
        turnover_score=92.0,
    )

    score = ArbitrageScorer().score(opportunity)

    assert 0.0 <= score.total_score <= 100.0
    assert score.demand_score == 95.0
    assert score.turnover_score == 92.0


def _opportunity(
    *,
    price_difference: Decimal,
    profit_margin: Decimal,
    demand_score: float,
    turnover_score: float,
) -> ArbitrageOpportunity:
    purchase_price = Decimal("100000")
    selling_price = purchase_price + price_difference
    return ArbitrageOpportunity(
        product="Chanel Wallet",
        brand="Chanel",
        category="wallet",
        purchase_source="Fashionphile",
        purchase_url="https://example.invalid/fashionphile/chanel-wallet",
        purchase_price=purchase_price,
        selling_market="Yahoo Auction",
        selling_url="https://auctions.yahoo.co.jp/search/search?p=Chanel+Wallet",
        selling_price=selling_price,
        price_difference=price_difference,
        estimated_profit=Decimal("30000"),
        profit_margin=profit_margin,
        demand_score=demand_score,
        turnover_score=turnover_score,
        arbitrage_score=0.0,
        decision="BUY",
        external_id="score-001",
    )
