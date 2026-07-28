"""Amazon-specific listing validator tests."""

from decimal import Decimal

from marketplace.listing_validator import validate_listing
from models.marketplace_listing import MarketplaceListing


def _amazon_listing(**overrides) -> MarketplaceListing:
    base = dict(
        marketplace_name="amazon_jp",
        listing_id="B0TEST1234",
        title="GUCCI Wallet",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
        listing_url="https://www.amazon.co.jp/dp/B0TEST1234",
        currency="JPY",
    )
    base.update(overrides)
    return MarketplaceListing(**base)


def test_valid_amazon_listing() -> None:
    valid, reason = validate_listing(_amazon_listing())
    assert valid is True
    assert reason == ""


def test_missing_title_invalid() -> None:
    valid, reason = validate_listing(_amazon_listing(title=""))
    assert valid is False


def test_missing_price_invalid() -> None:
    valid, reason = validate_listing(_amazon_listing(price_jpy=Decimal("0")))
    assert valid is False


def test_missing_url_and_asin_invalid() -> None:
    valid, reason = validate_listing(_amazon_listing(listing_url="", listing_id=""))
    assert valid is False
    assert "URL or ASIN" in reason


def test_asin_without_url_valid() -> None:
    valid, reason = validate_listing(_amazon_listing(listing_url=""))
    assert valid is True


def test_url_without_asin_valid() -> None:
    valid, reason = validate_listing(_amazon_listing(listing_id=""))
    assert valid is True
