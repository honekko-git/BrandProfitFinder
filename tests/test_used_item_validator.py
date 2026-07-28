"""Tests for used item details validation."""

from decimal import Decimal

from marketplace.listing_validator import validate_listing
from models.authentication_info import AuthenticationInfo, AuthenticationStatus
from models.marketplace_listing import MarketplaceListing
from models.used_item_details import ConditionScoreResult, UsedItemDetails
from used_luxury.used_item_validator import validate_used_item_details


def _listing(**kwargs) -> MarketplaceListing:
    base = dict(
        marketplace_name="used_demo",
        listing_id="used-1",
        title="Test Bag",
        price_jpy=Decimal("100000"),
        listing_url="https://example.invalid/used/used-1",
    )
    base.update(kwargs)
    return MarketplaceListing(**base)


def test_no_used_details_valid() -> None:
    valid, reason = validate_listing(_listing())
    assert valid is True


def test_used_details_valid() -> None:
    details = UsedItemDetails(condition_confidence=0.9, data_completeness=0.8)
    valid, reason = validate_listing(_listing(used_item_details=details))
    assert valid is True


def test_invalid_confidence() -> None:
    details = UsedItemDetails(condition_confidence=1.5)
    valid, reason = validate_used_item_details(details)
    assert valid is False


def test_invalid_score() -> None:
    details = UsedItemDetails(condition_score=ConditionScoreResult(score=150))
    valid, reason = validate_used_item_details(details)
    assert valid is False


def test_invalid_completeness() -> None:
    details = UsedItemDetails(data_completeness=2.0)
    valid, reason = validate_used_item_details(details)
    assert valid is False


def test_invalid_return_period() -> None:
    from models.seller_info import ReturnPolicy

    details = UsedItemDetails(return_policy=ReturnPolicy(return_period_days=-1))
    valid, reason = validate_used_item_details(details)
    assert valid is False


def test_authenticated_without_platform_invalid() -> None:
    details = UsedItemDetails(
        authentication=AuthenticationInfo(status=AuthenticationStatus.AUTHENTICATED)
    )
    valid, reason = validate_used_item_details(details)
    assert valid is False


def test_existing_marketplace_still_valid() -> None:
    listing = MarketplaceListing(
        marketplace_name="amazon_jp",
        listing_id="B0TEST",
        title="Item",
        price_jpy=Decimal("10000"),
        listing_url="https://www.amazon.co.jp/dp/B0TEST",
    )
    valid, _ = validate_listing(listing)
    assert valid is True
