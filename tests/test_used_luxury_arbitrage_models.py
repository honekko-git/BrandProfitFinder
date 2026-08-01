"""Tests for used luxury arbitrage models."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.arbitrage.models import ArbitrageOpportunity, ArbitrageScore


def test_arbitrage_opportunity_creation() -> None:
    opportunity = ArbitrageOpportunity(
        product="Chanel Wallet",
        brand="Chanel",
        category="wallet",
        purchase_source="Fashionphile",
        purchase_url="https://example.invalid/fashionphile/chanel-wallet",
        purchase_price=Decimal("120000"),
        selling_market="Yahoo Auction",
        selling_url="https://auctions.yahoo.co.jp/search/search?p=Chanel+Wallet",
        selling_price=Decimal("180000"),
        price_difference=Decimal("60000"),
        estimated_profit=Decimal("35000"),
        profit_margin=Decimal("29.2"),
        demand_score=88.0,
        turnover_score=76.5,
        arbitrage_score=82.4,
        recommendation_rank=1,
        decision="BUY",
        external_id="arb-001",
    )

    assert opportunity.product == "Chanel Wallet"
    assert opportunity.brand == "Chanel"
    assert opportunity.purchase_source == "Fashionphile"
    assert opportunity.selling_market == "Yahoo Auction"
    assert opportunity.recommendation_rank == 1


def test_arbitrage_opportunity_profit_calculation_fields() -> None:
    purchase_price = Decimal("100000")
    selling_price = Decimal("160000")
    estimated_profit = Decimal("42000")

    opportunity = ArbitrageOpportunity(
        product="Louis Vuitton Bag",
        brand="Louis Vuitton",
        category="bag",
        purchase_source="The RealReal",
        purchase_url="https://example.invalid/therealreal/lv-bag",
        purchase_price=purchase_price,
        selling_market="Mercari",
        selling_url="https://jp.mercari.com/search?keyword=Louis+Vuitton+Bag",
        selling_price=selling_price,
        price_difference=selling_price - purchase_price,
        estimated_profit=estimated_profit,
        profit_margin=Decimal("26.3"),
        demand_score=80.0,
        turnover_score=70.0,
        arbitrage_score=75.0,
        decision="BUY",
        external_id="arb-002",
    )

    assert opportunity.price_difference == Decimal("60000")
    assert opportunity.estimated_profit == estimated_profit
    assert opportunity.profit_margin == Decimal("26.3")


def test_arbitrage_score_creation() -> None:
    score = ArbitrageScore(
        profit_difference_score=85.0,
        profit_margin_score=70.0,
        demand_score=80.0,
        turnover_score=75.0,
        total_score=79.5,
    )

    assert score.total_score == 79.5
    assert score.profit_difference_score == 85.0
