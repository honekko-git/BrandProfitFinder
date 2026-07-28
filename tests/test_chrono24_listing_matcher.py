"""Chrono24 listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="chrono24",
        listing_id="c24-match-001",
        title="ROLEX Submariner Date 126610LN Black 41mm",
        brand="ROLEX",
        model_number="126610LN",
        sku="",
        price_jpy=Decimal("1980000"),
        listing_url="https://example.invalid/chrono24/c24-match-001",
        source_metadata={
            "source_reference_number": "126610LN",
            "source_case_diameter_mm": 41.0,
            "source_dial_color": "BLACK",
            "source_bracelet_material": "STAINLESS_STEEL",
            "source_negotiation_enabled": True,
        },
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_sku_match() -> None:
    product = Product(name="Watch", brand="", model="", sku="c24-match-001")
    listing = _listing(sku="", brand="", model_number="", title="Unrelated")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_reference_number_match() -> None:
    product = Product(name="Submariner", brand="ROLEX", model="126610LN")
    listing = _listing(model_number="", source_metadata={"source_reference_number": "126610LN"})
    score = ListingMatcher().score(product, listing)
    assert score >= Decimal("28")


def test_negotiation_difference_not_identity() -> None:
    product = Product(name="Submariner", brand="ROLEX", model="126610LN")
    a = _listing(source_metadata={"source_negotiation_enabled": True, "source_reference_number": "126610LN", "source_case_diameter_mm": 41.0, "source_dial_color": "BLACK", "source_bracelet_material": "STAINLESS_STEEL"})
    b = _listing(
        listing_id="c24-match-002",
        source_metadata={"source_negotiation_enabled": False, "source_reference_number": "126610LN", "source_case_diameter_mm": 41.0, "source_dial_color": "BLACK", "source_bracelet_material": "STAINLESS_STEEL"},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)


def test_case_diameter_warning() -> None:
    product = Product(name="ROLEX Submariner 40mm Black", brand="ROLEX", model="126610LN")
    warnings = ListingMatcher().get_comparison_warnings(product, _listing())
    assert any("case diameter" in w for w in warnings)
