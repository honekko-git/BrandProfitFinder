"""Unit tests for models.marketplace_search_result."""

from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import (
    SEARCH_NO_LISTINGS,
    SEARCH_SUCCESS,
    MarketplaceSearchResult,
)
from models.product import Product


def test_create_search_result() -> None:
    product = Product(name="Bag", sku="SKU-1")
    listing = MarketplaceListing(title="Bag", price_jpy=Decimal("10000"), marketplace_name="local")
    result = MarketplaceSearchResult(
        product=product,
        query="Bag",
        marketplace_name="local",
        listings=[listing],
        valid_listings=[listing],
        selected_listing=listing,
        selected_price_jpy=Decimal("10000"),
        status=SEARCH_SUCCESS,
    )
    assert result.product is product
    assert result.selected_price_jpy == Decimal("10000")


def test_zero_listings() -> None:
    result = MarketplaceSearchResult(status=SEARCH_NO_LISTINGS, error_message="none")
    assert result.listing_count == 0
    assert result.has_valid_listings is False


def test_valid_and_rejected_separation() -> None:
    valid = MarketplaceListing(title="Good", price_jpy=Decimal("1000"), marketplace_name="local", is_valid=True)
    rejected = MarketplaceListing(title="Bad", price_jpy=Decimal("0"), marketplace_name="local", is_valid=False)
    result = MarketplaceSearchResult(valid_listings=[valid], rejected_listings=[rejected])
    assert len(result.valid_listings) == 1
    assert len(result.rejected_listings) == 1


def test_selected_listing_and_price() -> None:
    listing = MarketplaceListing(title="Item", price_jpy=Decimal("5000"), marketplace_name="local")
    result = MarketplaceSearchResult(selected_listing=listing, selected_price_jpy=Decimal("5000"))
    assert result.selected_listing is listing


def test_error_state() -> None:
    result = MarketplaceSearchResult(status=SEARCH_NO_LISTINGS, error_message="no data")
    assert result.error_message == "no data"
