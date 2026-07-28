"""Unit tests for marketplace.listing_validator."""

from decimal import Decimal

from marketplace.listing_validator import validate_listing, validate_listings
from models.marketplace_listing import MarketplaceListing


def _valid_listing(**overrides) -> MarketplaceListing:
    base = dict(
        marketplace_name="local",
        title="Valid Item",
        price_jpy=Decimal("10000"),
        shipping_jpy=Decimal("500"),
        listing_url="https://example.com/item",
    )
    base.update(overrides)
    return MarketplaceListing(**base)


def test_valid_listing() -> None:
    valid, reason = validate_listing(_valid_listing())
    assert valid is True
    assert reason == ""


def test_missing_title() -> None:
    valid, reason = validate_listing(_valid_listing(title=""))
    assert valid is False
    assert "title" in reason


def test_missing_marketplace_name() -> None:
    valid, reason = validate_listing(_valid_listing(marketplace_name=""))
    assert valid is False


def test_zero_price() -> None:
    valid, reason = validate_listing(_valid_listing(price_jpy=Decimal("0")))
    assert valid is False


def test_negative_price() -> None:
    valid, reason = validate_listing(_valid_listing(price_jpy=Decimal("-1")))
    assert valid is False


def test_negative_shipping() -> None:
    valid, reason = validate_listing(_valid_listing(shipping_jpy=Decimal("-100")))
    assert valid is False


def test_invalid_url() -> None:
    valid, reason = validate_listing(_valid_listing(listing_url="not-a-url"))
    assert valid is False


def test_invalid_seller_rating() -> None:
    valid, reason = validate_listing(_valid_listing(seller_rating=Decimal("6")))
    assert valid is False


def test_negative_sold_count() -> None:
    valid, reason = validate_listing(_valid_listing(sold_count=-1))
    assert valid is False


def test_batch_continues_after_invalid() -> None:
    valid, rejected = validate_listings(
        [
            _valid_listing(title=""),
            _valid_listing(listing_id="OK"),
        ]
    )
    assert len(valid) == 1
    assert len(rejected) == 1
