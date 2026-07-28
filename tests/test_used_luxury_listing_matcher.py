"""Tests for used luxury listing matcher behavior."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.authentication_info import AuthenticationInfo, AuthenticationStatus
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from models.used_item_details import UsedItemDetails
from models.used_item_condition import UsedItemCondition


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="used_demo",
        listing_id="used-match-001",
        title="GUCCI GG Marmont Bag Black",
        brand="GUCCI",
        model_number="447632",
        jan_code="1234567890123",
        sku="",
        price_jpy=Decimal("128000"),
        listing_url="https://example.invalid/used/used-match-001",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_same_product_different_condition() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="447632")
    good = _listing(used_item_details=UsedItemDetails(condition=UsedItemCondition.GOOD))
    excellent = _listing(
        listing_id="used-match-002",
        used_item_details=UsedItemDetails(condition=UsedItemCondition.EXCELLENT),
    )
    matcher = ListingMatcher()
    assert matcher.score(product, good) == matcher.score(product, excellent)


def test_auth_status_not_used_for_sku_match() -> None:
    product = Product(name="Bag", brand="", model="", sku="used-match-001")
    listing = _listing(
        sku="",
        brand="",
        model_number="",
        jan_code="",
        title="Unrelated",
        used_item_details=UsedItemDetails(
            authentication=AuthenticationInfo(status=AuthenticationStatus.AUTHENTICATED)
        ),
    )
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_jan_match_priority() -> None:
    product = Product(name="Other", brand="Other", model="1234567890123")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("40")


def test_model_match() -> None:
    product = Product(name="Other", brand="GUCCI", model="447632")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("30")


def test_color_mismatch_warning() -> None:
    product = Product(name="Marmont Bag Red", brand="GUCCI", model="447632")
    listing = _listing(title="GUCCI GG Marmont Bag Black")
    warnings = ListingMatcher().get_comparison_warnings(product, listing)
    assert any("color" in w for w in warnings)


def test_size_mismatch_warning() -> None:
    product = Product(name="Loafer Size 42", brand="Prada", model="PRD-1")
    listing = _listing(title="Prada Loafer Size 41", brand="Prada", model_number="PRD-1")
    warnings = ListingMatcher().get_comparison_warnings(product, listing)
    assert any("size" in w for w in warnings)


def test_different_accessories_same_match_score() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="447632")
    with_acc = _listing(used_item_details=UsedItemDetails())
    without_acc = _listing(
        listing_id="used-match-003",
        used_item_details=UsedItemDetails(condition=UsedItemCondition.FOR_PARTS),
    )
    assert ListingMatcher().score(product, with_acc) == ListingMatcher().score(product, without_acc)
