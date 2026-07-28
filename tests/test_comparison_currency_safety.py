"""Currency safety regression tests for cross-marketplace comparison."""

from decimal import Decimal

import pytest

from comparison.currency_safety import (
    authoritative_jpy_sale_price,
    is_jpy_comparable_currency,
    is_jpy_comparable_listing,
    listing_source_price_amount,
    normalize_currency_code,
    resolve_listing_currency,
)
from comparison.engine import ComparisonEngine
from comparison.models import MarketplaceCandidate
from comparison.service import _build_price_result
from main import build_phase3_calculator, build_phase3_products
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, CALCULATION_UNKNOWN_CURRENCY, PriceResult
from models.product import Product


def _listing(currency: str, amount: Decimal) -> MarketplaceListing:
    return MarketplaceListing(
        marketplace_name="demo",
        listing_id="L-1",
        title="Demo",
        price_jpy=amount,
        currency=currency,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("jpy", "JPY"),
        (" USD ", "USD"),
        ("", None),
        (None, None),
        ("???", "???"),
    ],
)
def test_normalize_currency_code(raw: object | None, expected: str | None) -> None:
    assert normalize_currency_code(raw) == expected


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP"])
def test_non_jpy_listing_not_jpy_comparable(currency: str) -> None:
    listing = _listing(currency, Decimal("500"))
    assert is_jpy_comparable_listing(listing) is False
    assert authoritative_jpy_sale_price(listing) is None


def test_jpy_listing_is_comparable() -> None:
    listing = _listing("JPY", Decimal("10000"))
    assert is_jpy_comparable_listing(listing) is True
    assert authoritative_jpy_sale_price(listing) == Decimal("10000")


def test_unknown_currency_not_assumed_jpy() -> None:
    listing = MarketplaceListing(
        marketplace_name="demo",
        listing_id="L-2",
        title="Demo",
        price_jpy=Decimal("100"),
        currency="",
    )
    assert resolve_listing_currency(listing) is None
    assert is_jpy_comparable_listing(listing) is False


def test_listing_source_amount_preserved_without_conversion() -> None:
    listing = _listing("USD", Decimal("500"))
    assert listing_source_price_amount(listing) == Decimal("500")


def test_build_price_result_rejects_non_jpy_without_conversion() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    listing = _listing("USD", Decimal("500"))
    search = MarketplaceSearchResult(product=product, marketplace_name="goat")
    calculator = build_phase3_calculator()
    result = _build_price_result(product, listing, search, "goat", calculator)
    assert result.calculation_status == CALCULATION_UNKNOWN_CURRENCY
    assert result.profit_jpy == Decimal("0")
    assert result.is_valid is False


def test_build_price_result_uses_jpy_authoritative_price() -> None:
    product = build_phase3_products()[0]
    listing = _listing("JPY", Decimal("10000"))
    search = MarketplaceSearchResult(product=product, marketplace_name="stockx")
    calculator = build_phase3_calculator()
    result = _build_price_result(product, listing, search, "stockx", calculator)
    assert result.calculation_status == CALCULATION_SUCCESS
    assert result.is_valid is True


def _candidate(
    marketplace: str,
    *,
    profit: Decimal,
    currency: str,
    jpy_comparable: bool,
    price: Decimal,
) -> MarketplaceCandidate:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name=marketplace,
        selected_price_jpy=price,
    )
    status = CALCULATION_SUCCESS if jpy_comparable else CALCULATION_UNKNOWN_CURRENCY
    price_result = PriceResult(
        product=product,
        profit_jpy=profit if jpy_comparable else Decimal("0"),
        profit_margin=Decimal("0.1") if jpy_comparable else Decimal("0"),
        calculation_status=status,
        domestic_sale_price_jpy=price if jpy_comparable else None,
        metadata={"source_currency": currency, "source_price_amount": str(price)},
    )
    return MarketplaceCandidate(
        marketplace_name=marketplace,
        search_result=search,
        price_result=price_result,
        listing_currency=currency,
        source_price_amount=price,
        jpy_comparable=jpy_comparable,
    )


@pytest.mark.parametrize("currency", ["EUR", "GBP", "USD"])
def test_engine_mixed_currency_only_jpy_eligible(currency: str) -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    candidates = [
        _candidate(
            "stockx",
            profit=Decimal("1000"),
            currency="JPY",
            jpy_comparable=True,
            price=Decimal("10000"),
        ),
        _candidate(
            "goat",
            profit=Decimal("50000"),
            currency=currency,
            jpy_comparable=False,
            price=Decimal("50000"),
        ),
    ]
    result = ComparisonEngine().compare_product(product, candidates)
    assert result.comparable_count == 1
    assert result.selected_review_marketplace == "stockx"
    assert result.highest_profit_marketplace == "stockx"
    assert result.selected_review_profit_jpy == Decimal("1000")
    non_jpy = [c for c in result.candidates if c.listing_currency != "JPY"]
    assert all(not c.is_comparable for c in non_jpy)
    assert all(c.comparable_profit_jpy is None for c in non_jpy)


def test_is_jpy_comparable_currency_explicit_only() -> None:
    assert is_jpy_comparable_currency("JPY") is True
    assert is_jpy_comparable_currency("USD") is False
    assert is_jpy_comparable_currency(None) is False
