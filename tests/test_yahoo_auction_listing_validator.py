"""Yahoo Auction-specific listing validator tests."""

from decimal import Decimal

from marketplace.listing_validator import validate_listing
from models.marketplace_listing import MarketplaceListing


def _listing(**overrides) -> MarketplaceListing:
    base = dict(
        marketplace_name="yahoo_auction",
        listing_id="test-auction-001",
        title="GUCCI Wallet",
        price_jpy=Decimal("108000"),
        shipping_jpy=None,
        shipping_unknown=True,
        listing_url="https://example.invalid/auction/test-auction-001",
        currency="JPY",
    )
    base.update(overrides)
    return MarketplaceListing(**base)


def test_valid_yahoo_auction_listing() -> None:
    valid, reason = validate_listing(_listing())
    assert valid is True
    assert reason == ""


def test_missing_title_invalid() -> None:
    valid, reason = validate_listing(_listing(title=""))
    assert valid is False


def test_missing_price_invalid() -> None:
    valid, reason = validate_listing(_listing(price_jpy=Decimal("0")))
    assert valid is False


def test_missing_url_and_auction_id_invalid() -> None:
    valid, reason = validate_listing(_listing(listing_url="", listing_id=""))
    assert valid is False
    assert "auction_id" in reason


def test_auction_id_without_url_valid() -> None:
    valid, reason = validate_listing(_listing(listing_url=""))
    assert valid is True


def test_url_without_auction_id_valid() -> None:
    valid, reason = validate_listing(_listing(listing_id=""))
    assert valid is True
