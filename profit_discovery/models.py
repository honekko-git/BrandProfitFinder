"""Buy decision models for profit discovery."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class BuyDecision(StrEnum):
    """Purchase recommendation for one evaluated product."""

    BUY = "BUY"
    HOLD = "HOLD"
    PASS = "PASS"


@dataclass(frozen=True, slots=True)
class BuyDecisionConfig:
    """Configurable thresholds for buy decision evaluation."""

    minimum_profit_jpy: Decimal = Decimal("5000")
    minimum_margin: Decimal = Decimal("20")
    target_margin: Decimal = Decimal("30")
    buy_discovery_threshold: float = 80.0
    hold_discovery_threshold: float = 60.0
    high_risk_inventory_score: float = 70.0


@dataclass(frozen=True, slots=True)
class BuyDecisionResult:
    """Explainable buy / hold / pass recommendation."""

    decision: BuyDecision
    max_purchase_price_jpy: Decimal | None
    target_profit_jpy: Decimal
    expected_profit_jpy: Decimal
    margin_requirement: Decimal
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
