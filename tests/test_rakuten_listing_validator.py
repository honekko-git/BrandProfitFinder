"""Rakuten-specific listing validator tests."""

from decimal import Decimal

from marketplace.listing_validator import validate_listing
from models.marketplace_listing import MarketplaceListing


def _rakuten_listing(**overrides) -> MarketplaceListing:
    base = dict(
        marketplace_name="rakuten",
        listing_id="sample-shop:123456",
        title="GUCCI Wallet",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
        listing_url="https://item.rakuten.co.jp/sample-shop/123456/",
        currency="JPY",
    )
    base.update(overrides)
    return MarketplaceListing(**base)


def test_valid_rakuten_listing() -> None:
    valid, reason = validate_listing(_rakuten_listing())
    assert valid is True
    assert reason == ""


def test_missing_title_invalid() -> None:
    valid, reason = validate_listing(
        MarketplaceListing(
            marketplace_name="rakuten",
            listing_id="sample-shop:123456",
            title="",
            price_jpy=Decimal("128000"),
            listing_url="https://item.rakuten.co.jp/sample-shop/123456/",
        )
    )
    assert valid is False


def test_missing_price_invalid() -> None:
    valid, reason = validate_listing(
        MarketplaceListing(
            marketplace_name="rakuten",
            listing_id="sample-shop:123456",
            title="GUCCI Wallet",
            price_jpy=Decimal("0"),
            listing_url="https://item.rakuten.co.jp/sample-shop/123456/",
        )
    )
    assert valid is False


def test_missing_url_and_item_code_invalid() -> None:
    valid, reason = validate_listing(
        MarketplaceListing(
            marketplace_name="rakuten",
            listing_id="",
            title="GUCCI Wallet",
            price_jpy=Decimal("128000"),
            listing_url="",
        )
    )
    assert valid is False
    assert "itemCode" in reason


def test_item_code_without_url_valid() -> None:
    valid, reason = validate_listing(
        MarketplaceListing(
            marketplace_name="rakuten",
            listing_id="sample-shop:123456",
            title="GUCCI Wallet",
            price_jpy=Decimal("128000"),
            listing_url="",
        )
    )
    assert valid is True
