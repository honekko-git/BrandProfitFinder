"""StockX listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="stockx",
        listing_id="sx-match-001",
        title="NIKE Dunk Low Black White US 9",
        brand="NIKE",
        model_number="DD1391-100",
        sku="",
        price_jpy=Decimal("24500"),
        listing_url="https://example.invalid/stockx/sx-match-001",
        source_metadata={
            "source_style_code": "DD1391-100",
            "source_size": "US 9",
            "source_size_system": "US_MEN",
            "source_stockx_lowest_ask": 24500,
        },
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_listing_id_not_match_basis() -> None:
    product = Product(name="Unrelated", brand="", model="", sku="sx-match-001")
    listing = _listing(sku="", brand="", model_number="", title="Other Shoe")
    assert ListingMatcher().score(product, listing) == Decimal("0")


def test_style_code_match() -> None:
    product = Product(name="Dunk", brand="NIKE", model="DD1391-100")
    listing = _listing(model_number="", source_metadata={"source_style_code": "DD1391-100"})
    assert ListingMatcher().score(product, listing) >= Decimal("25")


def test_size_mismatch_warning() -> None:
    product = Product(name="NIKE Dunk US 11", brand="NIKE", model="DD1391-100")
    warnings = ListingMatcher().get_comparison_warnings(product, _listing())
    assert any("size" in w for w in warnings)


def test_market_price_not_identity() -> None:
    product = Product(name="Dunk", brand="NIKE", model="DD1391-100")
    a = _listing(source_metadata={"source_style_code": "DD1391-100", "source_stockx_lowest_ask": 24500})
    b = _listing(
        listing_id="sx-match-002",
        source_metadata={"source_style_code": "DD1391-100", "source_stockx_lowest_ask": 30000},
    )
    assert ListingMatcher().score(product, a) == ListingMatcher().score(product, b)
