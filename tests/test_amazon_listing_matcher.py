"""Amazon-specific listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="amazon_jp",
        listing_id="B0TEST1234",
        title="GUCCI GG Marmont Wallet Black",
        brand="GUCCI",
        model_number="456126",
        jan_code="1234567890123",
        sku="B0TEST1234",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
        listing_url="https://www.amazon.co.jp/dp/B0TEST1234",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_brand_match() -> None:
    product = Product(name="Wallet", brand="GUCCI", model="456126")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("15")


def test_model_exact_match() -> None:
    product = Product(name="Other", brand="GUCCI", model="456126")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("30")


def test_jan_exact_match() -> None:
    product = Product(name="Other", brand="Other", model="1234567890123")
    score = ListingMatcher().score(product, _listing())
    assert score >= Decimal("40")


def test_title_similarity() -> None:
    product = Product(name="GG Marmont Wallet", brand="GUCCI", model="999")
    score = ListingMatcher().score(product, _listing())
    assert score > Decimal("0")


def test_different_product_lower_score() -> None:
    product = Product(name="Completely Different Shoes", brand="Prada", model="OTHER")
    score = ListingMatcher().score(product, _listing())
    low = ListingMatcher().score(Product(name="GG Marmont Wallet", brand="GUCCI", model="456126"), _listing())
    assert score < low


def test_color_variant_still_matches_brand_and_model() -> None:
    product = Product(name="GG Marmont Wallet Red", brand="GUCCI", model="456126")
    score = ListingMatcher().score(product, _listing(title="GUCCI GG Marmont Wallet Black"))
    assert score >= Decimal("45")


def test_size_variant_still_matches_model() -> None:
    product = Product(name="Loafer Size 42", brand="Prada", model="PRD-LOAFER")
    listing = _listing(title="Prada Loafer Size 41", brand="Prada", model_number="PRD-LOAFER")
    score = ListingMatcher().score(product, listing)
    assert score >= Decimal("30")


def test_insufficient_info_low_score() -> None:
    product = Product(name="", brand="", model="")
    score = ListingMatcher().score(product, _listing())
    assert score == Decimal("0")
