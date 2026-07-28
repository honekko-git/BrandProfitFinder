"""Unit tests for models.marketplace_listing."""

from decimal import Decimal

from models.marketplace_listing import MarketplaceListing


def test_create_listing() -> None:
    listing = MarketplaceListing(
        marketplace_name=" local-yahoo ",
        listing_id="Y-1",
        title="Test Bag",
        price_jpy=Decimal("10000"),
    )
    assert listing.marketplace_name == "local-yahoo"
    assert listing.title == "Test Bag"


def test_decimal_prices() -> None:
    listing = MarketplaceListing(price_jpy=Decimal("12345.67"))
    assert listing.price_jpy == Decimal("12345.67")


def test_total_price_calculation() -> None:
    listing = MarketplaceListing(price_jpy=Decimal("10000"), shipping_jpy=Decimal("500"))
    assert listing.compute_total_price_jpy() == Decimal("10500")
    assert listing.total_price_jpy == Decimal("10500")


def test_total_price_without_shipping() -> None:
    listing = MarketplaceListing(price_jpy=Decimal("10000"))
    assert listing.compute_total_price_jpy() == Decimal("10000")


def test_jan_code_leading_zero_preserved() -> None:
    listing = MarketplaceListing(jan_code="0123456789012")
    assert listing.jan_code == "0123456789012"
    assert listing.to_dict()["jan_code"] == "0123456789012"


def test_marketplace_name_normalized() -> None:
    listing = MarketplaceListing(marketplace_name="  Rakuten  ")
    assert listing.marketplace_name == "Rakuten"


def test_to_dict() -> None:
    listing = MarketplaceListing(
        marketplace_name="local",
        title="Item",
        price_jpy=Decimal("1000"),
        listing_url="https://example.com/item",
    )
    data = listing.to_dict()
    assert data["marketplace_name"] == "local"
    assert data["price_jpy"] == 1000.0


def test_input_not_mutated() -> None:
    source = MarketplaceListing(title="Original", price_jpy=Decimal("1000"))
    copied = MarketplaceListing(
        marketplace_name=source.marketplace_name,
        title=source.title,
        price_jpy=source.price_jpy,
    )
    copied.title = "Changed"
    assert source.title == "Original"
