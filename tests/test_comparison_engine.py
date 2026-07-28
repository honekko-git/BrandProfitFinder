"""Tests for comparison engine."""

from decimal import Decimal

from comparison.config import ComparisonConfig
from comparison.engine import ComparisonEngine
from comparison.models import MarketplaceCandidate
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product


def _candidate(
    marketplace: str,
    *,
    profit: Decimal,
    margin: Decimal = Decimal("0.10"),
    currency: str = "JPY",
    price: Decimal = Decimal("10000"),
    order_index: int = 0,
    identity_matched: bool = True,
    jpy_comparable: bool | None = None,
) -> MarketplaceCandidate:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name=marketplace,
        selected_price_jpy=price,
    )
    price_result = PriceResult(
        product=product,
        profit_jpy=profit,
        profit_margin=margin,
        calculation_status=CALCULATION_SUCCESS,
        domestic_sale_price_jpy=price,
        metadata={"source_currency": currency},
    )
    comparable = jpy_comparable if jpy_comparable is not None else currency == "JPY"
    return MarketplaceCandidate(
        marketplace_name=marketplace,
        search_result=search,
        price_result=price_result,
        listing_currency=currency,
        source_price_amount=price,
        jpy_comparable=comparable and price_result.is_valid,
        order_index=order_index,
        identity_matched=identity_matched,
    )


def test_compare_product_selects_highest_profit() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate("stockx", profit=Decimal("1000"), order_index=0),
        _candidate("goat", profit=Decimal("2500"), order_index=1),
    ]
    result = ComparisonEngine().compare_product(
        product,
        candidates,
        expected_marketplaces=["stockx", "goat"],
    )
    assert result.selected_review_marketplace == "goat"
    assert result.selected_review_profit_jpy == Decimal("2500")
    assert result.highest_profit_marketplace == "goat"
    assert result.highest_profit_jpy == Decimal("2500")


def test_mixed_currency_warning() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate("stockx", profit=Decimal("1000"), currency="JPY"),
        _candidate("goat", profit=Decimal("900"), currency="USD", jpy_comparable=False),
    ]
    result = ComparisonEngine().compare_product(product, candidates)
    assert result.currency_consistent is False
    assert any("mixed currencies" in warning for warning in result.warnings)
    assert result.comparable_count == 1
    assert result.selected_review_marketplace == "stockx"
    assert result.highest_profit_marketplace == "stockx"


def test_unknown_currency_not_converted() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate("goat", profit=Decimal("900"), currency="USD", jpy_comparable=False)
    ]
    result = ComparisonEngine().compare_product(product, candidates)
    assert "USD" in result.currencies_observed
    assert any("non-JPY" in warning for warning in result.warnings)
    assert result.selected_review_marketplace is None
    assert result.highest_profit_marketplace is None
    assert "Review required" in result.recommendation


def test_usd_numeric_amount_cannot_win_over_jpy() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate(
            "stockx",
            profit=Decimal("1000"),
            currency="JPY",
            price=Decimal("10000"),
            order_index=0,
        ),
        _candidate(
            "goat",
            profit=Decimal("50000"),
            currency="USD",
            price=Decimal("50000"),
            jpy_comparable=False,
            order_index=1,
        ),
    ]
    result = ComparisonEngine().compare_product(product, candidates)
    assert result.selected_review_marketplace == "stockx"
    assert result.highest_profit_marketplace == "stockx"
    assert result.highest_profit_jpy == Decimal("1000")


def test_identity_mismatch_excluded() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate("stockx", profit=Decimal("5000"), identity_matched=False),
        _candidate("goat", profit=Decimal("1000"), identity_matched=True),
    ]
    result = ComparisonEngine(
        ComparisonConfig(require_identity_match=True)
    ).compare_product(product, candidates)
    assert result.selected_review_marketplace == "goat"


def test_duplicate_marketplace_warning() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    candidates = [
        _candidate("stockx", profit=Decimal("1000"), order_index=0),
        _candidate("stockx", profit=Decimal("1100"), order_index=1),
    ]
    result = ComparisonEngine().compare_product(product, candidates)
    assert any("duplicate marketplace" in warning for warning in result.warnings)


def test_recommendation_is_advisory() -> None:
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    result = ComparisonEngine().compare_product(
        product,
        [_candidate("stockx", profit=Decimal("1000"))],
    )
    assert "Review" in result.recommendation
    assert "guarantee" not in result.recommendation.lower()


def test_selected_review_differs_from_highest_profit_when_intelligence_wins() -> None:
    """Higher completeness alone must not override higher profit without intelligence."""
    product = Product(name="Demo Item", brand="Demo", model="D-1", sku="SKU-1")
    low_profit = _candidate("stockx", profit=Decimal("1000"), order_index=0)
    high_profit = _candidate("goat", profit=Decimal("5000"), order_index=1)
    low_profit.price_result.metadata = {"data_completeness": 99}
    high_profit.price_result.metadata = {"data_completeness": 10}
    result = ComparisonEngine().compare_product(product, [low_profit, high_profit])
    assert result.selected_review_marketplace == "goat"
    assert result.highest_profit_marketplace == "goat"
