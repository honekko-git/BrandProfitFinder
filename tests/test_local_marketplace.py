"""Unit tests for marketplace.local_marketplace."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from marketplace.local_marketplace import LocalMarketplace
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import SEARCH_NO_LISTINGS, SEARCH_SUCCESS
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_result
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy
from price_compare.profit_calculator import ProfitCalculator


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="local-yahoo",
        listing_id="L-1",
        title="Gucci Bag",
        brand="Gucci",
        sku="P3-001",
        price_jpy=Decimal("98000"),
        shipping_jpy=Decimal("500"),
        listing_url="https://example.com/item",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def _product() -> Product:
    return Product(name="Gucci Bag", brand="Gucci", sku="P3-001", price=100.0, currency="USD", exchange_rate=100.0)


@pytest.fixture
def marketplace() -> LocalMarketplace:
    return LocalMarketplace(
        listings_by_product_key={
            "P3-001": [
                _listing(),
                _listing(listing_id="L-2", price_jpy=Decimal("102000"), shipping_jpy=Decimal("0")),
                _listing(listing_id="BAD", title="", price_jpy=Decimal("1000")),
            ]
        },
        selection_strategy=PriceSelectionStrategy.HIGHEST,
    )


def test_search_returns_marketplace_search_result(marketplace: LocalMarketplace) -> None:
    result = marketplace.search(_product())
    assert result.product is not None
    assert result.listing_count == 3


def test_search_multiple_candidates(marketplace: LocalMarketplace) -> None:
    result = marketplace.search(_product())
    assert len(result.valid_listings) == 2
    assert result.status == SEARCH_SUCCESS


def test_search_no_candidates() -> None:
    marketplace = LocalMarketplace(listings_by_product_key={})
    result = marketplace.search(_product())
    assert result.status == SEARCH_NO_LISTINGS


def test_invalid_candidates_do_not_stop_processing(marketplace: LocalMarketplace) -> None:
    result = marketplace.search(_product())
    assert len(result.rejected_listings) == 1
    assert result.selected_price_jpy == Decimal("102000")


def test_no_network_access(marketplace: LocalMarketplace) -> None:
    with patch("utils.http.fetch_url") as mock_fetch, patch("utils.http.HttpClient") as mock_client:
        marketplace.search(_product())
        mock_fetch.assert_not_called()
        mock_client.assert_not_called()


def test_same_input_same_output(marketplace: LocalMarketplace) -> None:
    product = _product()
    first = marketplace.search(product)
    second = marketplace.search(product)
    assert first.selected_price_jpy == second.selected_price_jpy
    assert first.listing_count == second.listing_count


def test_prices_from_listings() -> None:
    comparator = PriceComparator()
    listings = [
        _listing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("0")),
        _listing(price_jpy=Decimal("20000"), shipping_jpy=Decimal("0")),
    ]
    prices = comparator.prices_from_listings(listings)
    assert prices == [Decimal("10000"), Decimal("20000")]


def test_select_highest_from_listings() -> None:
    comparator = PriceComparator()
    listings = [
        _listing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("0")),
        _listing(listing_id="L-2", price_jpy=Decimal("20000"), shipping_jpy=Decimal("0")),
    ]
    selected = comparator.select_from_listings(listings, PriceSelectionStrategy.HIGHEST)
    assert selected is not None
    assert selected[1] == Decimal("20000")


def test_select_lowest_from_listings() -> None:
    comparator = PriceComparator()
    listings = [
        _listing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("0")),
        _listing(listing_id="L-2", price_jpy=Decimal("20000"), shipping_jpy=Decimal("0")),
    ]
    selected = comparator.select_from_listings(listings, PriceSelectionStrategy.LOWEST)
    assert selected is not None
    assert selected[1] == Decimal("10000")


def test_select_median_from_listings() -> None:
    comparator = PriceComparator()
    listings = [
        _listing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("0")),
        _listing(listing_id="L-2", price_jpy=Decimal("30000"), shipping_jpy=Decimal("0")),
        _listing(listing_id="L-3", price_jpy=Decimal("20000"), shipping_jpy=Decimal("0")),
    ]
    selected = comparator.select_from_listings(listings, PriceSelectionStrategy.MEDIAN)
    assert selected is not None
    assert selected[1] == Decimal("20000")


def test_select_first_valid_from_listings() -> None:
    comparator = PriceComparator()
    listings = [
        _listing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("0")),
        _listing(listing_id="L-2", price_jpy=Decimal("20000"), shipping_jpy=Decimal("0")),
    ]
    selected = comparator.select_from_listings(listings, PriceSelectionStrategy.FIRST_VALID)
    assert selected is not None
    assert selected[1] == Decimal("10000")


def test_profit_from_search_result(marketplace: LocalMarketplace) -> None:
    result = marketplace.search(_product())
    price_result = calculate_profit_from_search_result(result, ProfitCalculator())
    assert isinstance(price_result, PriceResult)
    assert price_result.calculation_status == CALCULATION_SUCCESS


def test_no_candidates_safe_profit_result() -> None:
    marketplace = LocalMarketplace(listings_by_product_key={})
    search_result = marketplace.search(_product())
    price_result = calculate_profit_from_search_result(search_result, ProfitCalculator())
    assert price_result.calculation_status != CALCULATION_SUCCESS


def test_invalid_listing_does_not_block_valid_profit(marketplace: LocalMarketplace) -> None:
    result = marketplace.search(_product())
    price_result = calculate_profit_from_search_result(result, ProfitCalculator())
    assert price_result.domestic_sale_price_jpy is not None
