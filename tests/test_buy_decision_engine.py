"""Tests for buy decision engine."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from profit_discovery.buy_decision_engine import BuyDecisionEngine, attach_buy_decision_metadata
from profit_discovery.models import BuyDecision, BuyDecisionConfig
from profit_intelligence.discovery_models import DiscoveryScore


def _discovery(overall: float, *, warnings: tuple[str, ...] = ()) -> DiscoveryScore:
    return DiscoveryScore(
        profit_score=overall,
        demand_score=overall,
        brand_score=overall,
        competition_score=overall,
        confidence_score=overall,
        overall_score=overall,
        warnings=warnings,
    )


def test_buy_decision_when_discovery_and_profit_meet_targets() -> None:
    result = PriceResult(
        profit_jpy=Decimal("35000"),
        profit_margin=Decimal("30"),
        roi=Decimal("80"),
        domestic_sale_price_jpy=Decimal("100000"),
        purchase_price_jpy=Decimal("60000"),
        total_cost_jpy=Decimal("82000"),
        marketplace_fee_jpy=Decimal("3000"),
        source_currency="USD",
        exchange_rate=Decimal("150"),
        source_purchase_price=Decimal("400"),
        calculation_status="success",
    )
    discovery = _discovery(85.0)

    decision = BuyDecisionEngine().decide(result, discovery)

    assert decision.decision is BuyDecision.BUY
    assert "Profit exceeds target." in decision.reasons
    assert "Strong discovery score." in decision.reasons
    assert "Healthy margin." in decision.reasons


def test_hold_decision_for_moderate_discovery_score() -> None:
    result = PriceResult(
        profit_jpy=Decimal("7000"),
        profit_margin=Decimal("22"),
        domestic_sale_price_jpy=Decimal("80000"),
        purchase_price_jpy=Decimal("50000"),
        total_cost_jpy=Decimal("71000"),
        marketplace_fee_jpy=Decimal("2000"),
        source_currency="USD",
        exchange_rate=Decimal("150"),
        source_purchase_price=Decimal("333"),
        calculation_status="success",
    )
    discovery = _discovery(65.0)

    decision = BuyDecisionEngine().decide(result, discovery)

    assert decision.decision is BuyDecision.HOLD
    assert any("Moderate discovery score" in reason for reason in decision.reasons)


def test_pass_decision_for_negative_profit() -> None:
    result = PriceResult(
        profit_jpy=Decimal("-2000"),
        profit_margin=Decimal("-5"),
        domestic_sale_price_jpy=Decimal("50000"),
        calculation_status="success",
    )
    discovery = _discovery(90.0)

    decision = BuyDecisionEngine().decide(result, discovery)

    assert decision.decision is BuyDecision.PASS
    assert "Negative profit observed." in decision.reasons


def test_pass_decision_for_high_inventory_risk() -> None:
    result = PriceResult(
        profit_jpy=Decimal("12000"),
        profit_margin=Decimal("25"),
        domestic_sale_price_jpy=Decimal("90000"),
        calculation_status="success",
        metadata={"inventory_risk_score": 85},
    )
    discovery = _discovery(88.0)

    decision = BuyDecisionEngine().decide(result, discovery)

    assert decision.decision is BuyDecision.PASS
    assert "High purchase risk." in decision.reasons


def test_hold_when_discovery_data_is_incomplete() -> None:
    result = PriceResult(
        profit_jpy=Decimal("18000"),
        profit_margin=Decimal("32"),
        domestic_sale_price_jpy=Decimal("120000"),
        purchase_price_jpy=Decimal("70000"),
        total_cost_jpy=Decimal("98000"),
        marketplace_fee_jpy=Decimal("4000"),
        source_currency="USD",
        exchange_rate=Decimal("150"),
        source_purchase_price=Decimal("467"),
        calculation_status="success",
    )
    discovery = _discovery(88.0, warnings=("Demand data unavailable.",))

    decision = BuyDecisionEngine().decide(result, discovery)

    assert decision.decision is BuyDecision.HOLD
    assert "Demand data unavailable." in decision.warnings


def test_attach_buy_decision_metadata() -> None:
    result = PriceResult(
        profit_jpy=Decimal("10000"),
        profit_margin=Decimal("25"),
        domestic_sale_price_jpy=Decimal("80000"),
        calculation_status="success",
    )
    discovery = _discovery(70.0)
    decision = BuyDecisionEngine(config=BuyDecisionConfig()).decide(result, discovery)

    attach_buy_decision_metadata(result, decision)

    assert result.metadata["buy_decision"] == decision.decision.value
    assert result.metadata["buy_reasons"]
