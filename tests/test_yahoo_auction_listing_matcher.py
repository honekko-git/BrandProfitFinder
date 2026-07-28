"""Yahoo Auction-specific listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="yahoo_auction",
        listing_id="test-auction-001",
        title="GUCCI GG Marmont Wallet Black",
        brand="GUCCI",
        model_number="428726",
        jan_code="1234567890123",
        sku="",
        price_jpy=Decimal("108000"),
        shipping_jpy=None,
        listing_url="https://example.invalid/auction/test-auction-001",
        source_metadata={"auction_id": "test-auction-001", "seller_id": "test-seller"},
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_jan_exact_match() -> None:
    product = Product(name="Other", brand="Other", model="1234567890123")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("40")


def test_model_exact_match() -> None:
    product = Product(name="Other", brand="GUCCI", model="428726")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("30")


def test_brand_match() -> None:
    product = Product(name="Wallet", brand="GUCCI", model="999")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("15")


def test_title_similarity() -> None:
    product = Product(name="GG Marmont Wallet", brand="GUCCI", model="999")
    score = ListingMatcher().score(product, _listing())
    assert score > Decimal("0")


def test_different_product_lower_score() -> None:
    product = Product(name="Completely Different Shoes", brand="Prada", model="OTHER")
    score = ListingMatcher().score(product, _listing())
    low = ListingMatcher().score(Product(name="GG Marmont Wallet", brand="GUCCI", model="428726"), _listing())
    assert score < low


def test_color_variant_still_matches_brand_and_model() -> None:
    product = Product(name="GG Marmont Wallet Red", brand="GUCCI", model="428726")
    score = ListingMatcher().score(product, _listing(title="GUCCI GG Marmont Wallet Black"))
    assert score >= Decimal("45")


def test_size_variant_still_matches_model() -> None:
    product = Product(name="Loafer Size 42", brand="Prada", model="PRD-LOAFER")
    listing = _listing(title="Prada Loafer Size 41", brand="Prada", model_number="PRD-LOAFER")
    score = ListingMatcher().score(product, listing)
    assert score >= Decimal("30")


def test_auction_id_not_used_as_sku_match() -> None:
    product = Product(name="Wallet", brand="", model="", sku="test-auction-001")
    listing = _listing(
        sku="",
        listing_id="test-auction-001",
        brand="",
        model_number="",
        jan_code="",
        title="Unrelated Title",
    )
    score = ListingMatcher().score(product, listing)
    assert score == Decimal("0")
