"""Buy decision engine built on PriceResult and DiscoveryScore."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from profit_intelligence.discovery_models import DiscoveryScore
from profit_intelligence.normalization import dedupe_preserve_order
from profit_policy.money import round_jpy

from profit_discovery.max_pay_calculator import MaxPayCalculator
from profit_discovery.models import BuyDecision, BuyDecisionConfig, BuyDecisionResult


class BuyDecisionEngine:
    """Evaluate whether a profitable product should be purchased."""

    def __init__(
        self,
        *,
        config: BuyDecisionConfig | None = None,
        max_pay_calculator: MaxPayCalculator | None = None,
    ) -> None:
        self.config = config or BuyDecisionConfig()
        self.max_pay_calculator = max_pay_calculator or MaxPayCalculator()

    def decide(
        self,
        result: PriceResult,
        discovery: DiscoveryScore,
    ) -> BuyDecisionResult:
        """Return a buy decision without mutating profit fields on the result."""
        config = self.config
        expected_profit = result.profit_jpy
        target_profit = self._resolve_target_profit(result)
        max_purchase_price = self.max_pay_calculator.calculate(result, target_profit)

        warnings = list(discovery.warnings)
        reasons: list[str] = []
        incomplete_data = self._has_incomplete_data(result, discovery)
        high_risk = self._is_high_risk(result, discovery)

        if expected_profit < 0:
            reasons.append("Negative profit observed.")
            if expected_profit < config.minimum_profit_jpy:
                reasons.append("Profit below minimum.")
            return self._build_result(
                decision=BuyDecision.PASS,
                result=result,
                discovery=discovery,
                target_profit=target_profit,
                max_purchase_price=max_purchase_price,
                reasons=reasons,
                warnings=warnings,
            )

        if high_risk:
            reasons.append("High purchase risk.")
            return self._build_result(
                decision=BuyDecision.PASS,
                result=result,
                discovery=discovery,
                target_profit=target_profit,
                max_purchase_price=max_purchase_price,
                reasons=reasons,
                warnings=warnings,
            )

        if (
            discovery.overall_score >= config.buy_discovery_threshold
            and expected_profit >= target_profit
        ):
            if incomplete_data:
                reasons.append("Promising opportunity, but key discovery data is incomplete.")
                warnings = dedupe_preserve_order([*warnings, "Incomplete discovery data; review before buying."])
                return self._build_result(
                    decision=BuyDecision.HOLD,
                    result=result,
                    discovery=discovery,
                    target_profit=target_profit,
                    max_purchase_price=max_purchase_price,
                    reasons=reasons,
                    warnings=list(warnings),
                )

            reasons.extend(self._buy_reasons(result, discovery, target_profit))
            return self._build_result(
                decision=BuyDecision.BUY,
                result=result,
                discovery=discovery,
                target_profit=target_profit,
                max_purchase_price=max_purchase_price,
                reasons=reasons,
                warnings=warnings,
            )

        if discovery.overall_score >= config.hold_discovery_threshold or incomplete_data:
            reasons.extend(self._hold_reasons(result, discovery, incomplete_data))
            return self._build_result(
                decision=BuyDecision.HOLD,
                result=result,
                discovery=discovery,
                target_profit=target_profit,
                max_purchase_price=max_purchase_price,
                reasons=reasons,
                warnings=warnings,
            )

        reasons.append("Profit below minimum.")
        if discovery.overall_score < config.hold_discovery_threshold:
            reasons.append("Discovery score below hold threshold.")
        return self._build_result(
            decision=BuyDecision.PASS,
            result=result,
            discovery=discovery,
            target_profit=target_profit,
            max_purchase_price=max_purchase_price,
            reasons=reasons,
            warnings=warnings,
        )

    def _resolve_target_profit(self, result: PriceResult) -> Decimal:
        config = self.config
        margin_target = Decimal("0")
        domestic_sale = result.domestic_sale_price_jpy
        if domestic_sale is not None and domestic_sale > 0:
            margin_target = round_jpy(domestic_sale * config.target_margin / Decimal("100"))
        return max(config.minimum_profit_jpy, margin_target)

    def _has_incomplete_data(self, result: PriceResult, discovery: DiscoveryScore) -> bool:
        if not result.is_valid:
            return True
        if result.domestic_sale_price_jpy is None:
            return True
        if discovery.warnings:
            incomplete_markers = (
                "unavailable",
                "incomplete",
                "unknown",
            )
            for warning in discovery.warnings:
                lowered = warning.lower()
                if any(marker in lowered for marker in incomplete_markers):
                    return True
        return False

    def _is_high_risk(self, result: PriceResult, discovery: DiscoveryScore) -> bool:
        inventory_risk = result.metadata.get("inventory_risk_score")
        if inventory_risk is not None:
            try:
                if float(inventory_risk) >= self.config.high_risk_inventory_score:
                    return True
            except (TypeError, ValueError):
                pass

        for warning in discovery.warnings:
            if "negative profit" in warning.lower():
                return True

        return False

    def _buy_reasons(
        self,
        result: PriceResult,
        discovery: DiscoveryScore,
        target_profit: Decimal,
    ) -> list[str]:
        reasons: list[str] = []
        if result.profit_jpy >= target_profit:
            reasons.append("Profit exceeds target.")
        if discovery.overall_score >= self.config.buy_discovery_threshold:
            reasons.append("Strong discovery score.")
        if result.profit_margin is not None and result.profit_margin >= self.config.minimum_margin:
            reasons.append("Healthy margin.")
        return reasons

    def _hold_reasons(
        self,
        result: PriceResult,
        discovery: DiscoveryScore,
        incomplete_data: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if discovery.overall_score >= self.config.hold_discovery_threshold:
            reasons.append("Moderate discovery score warrants monitoring.")
        if incomplete_data:
            reasons.append("Incomplete discovery data.")
        if result.profit_jpy < self._resolve_target_profit(result):
            reasons.append("Profit has not reached target yet.")
        return reasons

    def _build_result(
        self,
        *,
        decision: BuyDecision,
        result: PriceResult,
        discovery: DiscoveryScore,
        target_profit: Decimal,
        max_purchase_price: Decimal | None,
        reasons: list[str],
        warnings: list[str],
    ) -> BuyDecisionResult:
        return BuyDecisionResult(
            decision=decision,
            max_purchase_price_jpy=max_purchase_price,
            target_profit_jpy=target_profit,
            expected_profit_jpy=result.profit_jpy,
            margin_requirement=self.config.minimum_margin,
            reasons=dedupe_preserve_order(reasons),
            warnings=dedupe_preserve_order(warnings),
        )


def attach_buy_decision_metadata(result: PriceResult, decision: BuyDecisionResult) -> None:
    """Attach buy decision fields to result metadata without changing profit numbers."""
    result.metadata.update(
        {
            "buy_decision": decision.decision.value,
            "buy_max_purchase_price_jpy": _decimal_or_none(decision.max_purchase_price_jpy),
            "buy_target_profit_jpy": _decimal_or_none(decision.target_profit_jpy),
            "buy_expected_profit_jpy": _decimal_or_none(decision.expected_profit_jpy),
            "buy_margin_requirement": _decimal_or_none(decision.margin_requirement),
            "buy_reasons": list(decision.reasons),
            "buy_warnings": list(decision.warnings),
        }
    )


def _decimal_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
