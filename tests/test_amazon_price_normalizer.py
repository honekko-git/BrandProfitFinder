"""Unit tests for marketplace.amazon_price_normalizer."""

from decimal import Decimal

import pytest

from marketplace.amazon_price_normalizer import parse_jpy_price


@pytest.mark.parametrize(
    "value,expected",
    [
        (128000, Decimal("128000")),
        ("128000", Decimal("128000")),
        ("128,000", Decimal("128000")),
        ("￥128,000", Decimal("128000")),
        ("¥128,000", Decimal("128000")),
        ("128,000円", Decimal("128000")),
        (0, None),
        (-100, None),
        ("", None),
        (None, None),
        ("abc", None),
        (12.5, None),
    ],
)
def test_parse_jpy_price(value, expected) -> None:
    assert parse_jpy_price(value) == expected


def test_zero_is_invalid() -> None:
    assert parse_jpy_price(0) is None


def test_points_zero_is_valid() -> None:
    assert parse_jpy_price(0) is None
    assert parse_jpy_price(1) == Decimal("1")
