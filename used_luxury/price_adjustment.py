"""
Suggested price adjustment for used luxury items.
"""

from decimal import Decimal, ROUND_HALF_UP

from models.used_item_condition import CONDITION_ADJUSTMENT_RATES, UsedItemCondition
from models.used_item_details import PriceAdjustmentResult


class PriceAdjustmentCalculator:
    """Calculate suggested price adjustments without auto-applying them."""

    def calculate(
        self,
        original_price_jpy: Decimal,
        condition: UsedItemCondition,
        *,
        confidence: float | None = None,
    ) -> PriceAdjustmentResult:
        """
        Compute a suggested adjustment based on condition.

        Args:
            original_price_jpy: Original listing price in JPY.
            condition: Normalized condition.
            confidence: Optional confidence in condition normalization.

        Returns:
            PriceAdjustmentResult with applied=False.
        """
        if original_price_jpy <= 0:
            return PriceAdjustmentResult(
                original_price_jpy=float(original_price_jpy),
                reasons=["invalid original price"],
                confidence=0.0,
                applied=False,
            )

        rate = CONDITION_ADJUSTMENT_RATES.get(condition)
        if rate is None or condition == UsedItemCondition.UNKNOWN:
            return PriceAdjustmentResult(
                original_price_jpy=float(original_price_jpy),
                adjustment_rate=0.0,
                adjustment_amount_jpy=0.0,
                adjusted_price_jpy=float(original_price_jpy),
                reasons=["unknown condition; no adjustment suggested"],
                confidence=confidence or 0.0,
                applied=False,
            )

        amount = (original_price_jpy * Decimal(str(abs(rate)))).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        adjusted = original_price_jpy + (amount if rate < 0 else -amount)
        if rate < 0:
            adjusted = original_price_jpy - amount
        adjusted = max(Decimal("0"), adjusted)

        return PriceAdjustmentResult(
            original_price_jpy=float(original_price_jpy),
            adjustment_rate=rate,
            adjustment_amount_jpy=float(-amount if rate < 0 else amount),
            adjusted_price_jpy=float(adjusted),
            reasons=[f"condition {condition.value} suggested rate {rate:.0%}"],
            confidence=confidence,
            applied=False,
        )
