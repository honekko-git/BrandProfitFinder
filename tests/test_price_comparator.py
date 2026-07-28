"""Unit tests for price_compare.price_comparator."""

from decimal import Decimal

from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy


def test_select_highest() -> None:
    comparator = PriceComparator()
    selected = comparator.select_price([100, 250, 180], PriceSelectionStrategy.HIGHEST)
    assert selected == Decimal("250")


def test_select_lowest() -> None:
    comparator = PriceComparator()
    selected = comparator.select_price([100, 250, 180], PriceSelectionStrategy.LOWEST)
    assert selected == Decimal("100")


def test_select_median() -> None:
    comparator = PriceComparator()
    selected = comparator.select_price([100, 250, 180], PriceSelectionStrategy.MEDIAN)
    assert selected == Decimal("180")


def test_select_first_valid() -> None:
    comparator = PriceComparator()
    selected = comparator.select_price([None, 0, 150, 200], PriceSelectionStrategy.FIRST_VALID)
    assert selected == Decimal("150")


def test_excludes_none() -> None:
    comparator = PriceComparator()
    assert comparator.filter_valid_prices([None, 100, None]) == [Decimal("100")]


def test_excludes_zero_and_negative() -> None:
    comparator = PriceComparator()
    assert comparator.filter_valid_prices([0, -5, 100]) == [Decimal("100")]


def test_excludes_invalid_values() -> None:
    comparator = PriceComparator()
    assert comparator.filter_valid_prices(["bad", 100]) == [Decimal("100")]


def test_no_valid_prices_returns_none() -> None:
    comparator = PriceComparator()
    assert comparator.select_price([None, 0, -1]) is None


def test_select_from_mapping() -> None:
    comparator = PriceComparator()
    selected = comparator.select_from_mapping(
        {"yahoo": 90000, "rakuten": 95000},
        PriceSelectionStrategy.HIGHEST,
    )
    assert selected == ("rakuten", Decimal("95000"))
