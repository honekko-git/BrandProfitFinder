"""Grailed listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="grailed",
        listing_id="grailed-match-001",
        title="RICK OWENS Ramones Black EU 42",
        brand="RICK OWENS",
        model_number="DRKSHDW-RAMONES",
        sku="",
        price_jpy=Decimal("98000"),
        listing_url="https://example.invalid/grailed/grailed-match-001",
        source_metadata={
            "source_offer_enabled": True,
            "source_minimum_offer": 85000.0,
            "source_inventory_status": "IN_STOCK",
        },
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_sku_match() -> None:
    product = Product(name="Sneakers", brand="", model="", sku="grailed-match-001")
    listing = _listing(sku="", brand="", model_number="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_offer_difference_not_identity() -> None:
    product = Product(name="Ramones", brand="RICK OWENS", model="DRKSHDW-RAMONES")
    a = _listing(source_metadata={"source_offer_enabled": True, "source_minimum_offer": 85000.0})
    b = _listing(
        listing_id="grailed-match-002",
        source_metadata={"source_offer_enabled": False, "source_minimum_offer": None},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_inventory_difference_not_identity() -> None:
    product = Product(name="Ramones", brand="RICK OWENS", model="DRKSHDW-RAMONES")
    a = _listing(source_metadata={"source_inventory_status": "IN_STOCK"})
    b = _listing(
        listing_id="grailed-match-003",
        source_metadata={"source_inventory_status": "SOLD"},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_color_warning() -> None:
    product = Product(name="Ramones White", brand="RICK OWENS", model="DRKSHDW-RAMONES")
    warnings = ListingMatcher().get_comparison_warnings(
        product,
        _listing(title="RICK OWENS Ramones Black EU 42"),
    )
    assert any("color" in w for w in warnings)
