"""Tests for price adjustment calculator."""

from decimal import Decimal

from models.used_item_condition import UsedItemCondition
from used_luxury.price_adjustment import PriceAdjustmentCalculator


def test_excellent_adjustment() -> None:
    result = PriceAdjustmentCalculator().calculate(Decimal("100000"), UsedItemCondition.EXCELLENT)
    assert result.adjustment_rate == -0.10
    assert result.adjusted_price_jpy == 90000.0
    assert result.applied is False


def test_unknown_no_change() -> None:
    result = PriceAdjustmentCalculator().calculate(Decimal("100000"), UsedItemCondition.UNKNOWN)
    assert result.adjusted_price_jpy == 100000.0
    assert result.adjustment_rate == 0.0
    assert result.applied is False


def test_for_parts_large_discount() -> None:
    result = PriceAdjustmentCalculator().calculate(Decimal("100000"), UsedItemCondition.FOR_PARTS)
    assert result.adjusted_price_jpy == 20000.0


def test_negative_price_rejected() -> None:
    result = PriceAdjustmentCalculator().calculate(Decimal("0"), UsedItemCondition.GOOD)
    assert "invalid" in result.reasons[0]


def test_adjustment_has_reason() -> None:
    result = PriceAdjustmentCalculator().calculate(Decimal("50000"), UsedItemCondition.GOOD)
    assert result.reasons
    assert result.confidence is None or isinstance(result.confidence, float)
