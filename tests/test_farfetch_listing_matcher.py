"""Farfetch listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="farfetch",
        listing_id="ff-match-001",
        title="GUCCI GG Marmont Small Shoulder Bag Black",
        brand="GUCCI",
        model_number="447632",
        sku="",
        price_jpy=Decimal("298000"),
        listing_url="https://example.invalid/farfetch/ff-match-001",
        source_metadata={
            "source_style_code": "447632-DTD1T-1000",
            "source_product_id": "ff-product-001",
            "source_variant_id": "ff-variant-001",
            "source_material": "leather",
            "source_gender": "women",
            "source_boutique_type": "PARTNER_BOUTIQUE",
        },
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_match_basis() -> None:
    product = Product(name="Bag", brand="", model="", sku="ff-match-001")
    listing = _listing(sku="", brand="", model_number="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_product_id_not_match_basis() -> None:
    product = Product(name="Alpha Product", brand="", model="", sku="ff-product-001")
    listing = _listing(
        brand="",
        model_number="",
        title="Beta Listing",
        source_metadata={"source_product_id": "ff-product-001"},
    )
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_style_code_match() -> None:
    product = Product(name="Marmont", brand="GUCCI", model="447632-DTD1T-1000")
    listing = _listing(model_number="", source_metadata={"source_style_code": "447632-DTD1T-1000"})
    score = ListingMatcher().score(product, listing)
    assert score >= Decimal("25")


def test_boutique_difference_not_identity() -> None:
    product = Product(name="Marmont", brand="GUCCI", model="447632")
    a = _listing(source_metadata={"source_style_code": "447632-DTD1T-1000", "source_boutique_type": "PARTNER_BOUTIQUE"})
    b = _listing(
        listing_id="ff-match-002",
        source_metadata={"source_style_code": "447632-DTD1T-1000", "source_boutique_type": "PLATFORM_INVENTORY"},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_color_warning() -> None:
    product = Product(name="GUCCI Marmont Red", brand="GUCCI", model="447632")
    warnings = ListingMatcher().get_comparison_warnings(product, _listing())
    assert any("color" in w for w in warnings)
