"""Vestiaire listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from models.used_item_details import UsedItemDetails
from models.used_item_condition import UsedItemCondition


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="vestiaire",
        listing_id="vestiaire-match-001",
        title="GUCCI GG Marmont Bag Black",
        brand="GUCCI",
        model_number="447632",
        jan_code="1234567890123",
        sku="",
        price_jpy=Decimal("128000"),
        listing_url="https://example.invalid/vestiaire/vestiaire-match-001",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_sku_match() -> None:
    product = Product(name="Bag", brand="", model="", sku="vestiaire-match-001")
    listing = _listing(sku="", brand="", model_number="", jan_code="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_same_product_different_condition() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="447632")
    a = _listing(used_item_details=UsedItemDetails(condition=UsedItemCondition.GOOD))
    b = _listing(
        listing_id="vestiaire-match-002",
        used_item_details=UsedItemDetails(condition=UsedItemCondition.EXCELLENT),
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_color_warning() -> None:
    product = Product(name="Marmont Bag Red", brand="GUCCI", model="447632")
    warnings = ListingMatcher().get_comparison_warnings(
        product,
        _listing(title="GUCCI GG Marmont Bag Black"),
    )
    assert any("color" in w for w in warnings)
