"""Fashionphile listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from models.used_item_condition import UsedItemCondition
from models.used_item_details import UsedItemDetails


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="fashionphile",
        listing_id="fp-match-001",
        title="GUCCI GG Marmont Bag Black",
        brand="GUCCI",
        model_number="GG-MARMONT",
        jan_code="1234567890123",
        sku="",
        price_jpy=Decimal("980000"),
        listing_url="https://example.invalid/fashionphile/fp-match-001",
        source_metadata={
            "source_discount_active": True,
            "source_inventory_status": "IN_STOCK",
        },
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_sku_match() -> None:
    product = Product(name="Bag", brand="", model="", sku="fp-match-001")
    listing = _listing(sku="", brand="", model_number="", jan_code="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_same_product_different_discount() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="GG-MARMONT")
    a = _listing(source_metadata={"source_discount_active": True})
    b = _listing(
        listing_id="fp-match-002",
        source_metadata={"source_discount_active": False},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_color_warning() -> None:
    product = Product(name="Marmont Bag Red", brand="GUCCI", model="GG-MARMONT")
    warnings = ListingMatcher().get_comparison_warnings(
        product,
        _listing(title="GUCCI GG Marmont Bag Black"),
    )
    assert any("color" in w for w in warnings)


def test_inventory_difference_not_identity() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="GG-MARMONT")
    a = _listing(source_metadata={"source_inventory_status": "IN_STOCK"})
    b = _listing(
        listing_id="fp-match-003",
        source_metadata={"source_inventory_status": "LOW_STOCK"},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)
