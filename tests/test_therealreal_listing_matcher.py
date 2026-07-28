"""The RealReal listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="therealreal",
        listing_id="trr-match-001",
        title="GUCCI GG Marmont Bag Black",
        brand="GUCCI",
        model_number="GG-MARMONT",
        sku="",
        price_jpy=Decimal("168000"),
        listing_url="https://example.invalid/therealreal/trr-match-001",
        source_metadata={"source_final_sale": False},
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_sku_match() -> None:
    product = Product(name="Bag", brand="", model="", sku="trr-match-001")
    listing = _listing(sku="", brand="", model_number="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_final_sale_difference_not_identity() -> None:
    product = Product(name="Marmont Bag", brand="GUCCI", model="GG-MARMONT")
    a = _listing(source_metadata={"source_final_sale": False})
    b = _listing(listing_id="trr-match-002", source_metadata={"source_final_sale": True})
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_color_warning() -> None:
    product = Product(name="Marmont Bag Red", brand="GUCCI", model="GG-MARMONT")
    warnings = ListingMatcher().get_comparison_warnings(
        product,
        _listing(title="GUCCI GG Marmont Bag Black"),
    )
    assert any("color" in w for w in warnings)
