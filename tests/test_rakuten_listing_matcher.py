"""Rakuten-specific listing matcher tests."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="rakuten",
        listing_id="sample-shop:123456",
        title="GUCCI GG Marmont Wallet Black",
        brand="",
        model_number="",
        jan_code="",
        sku="sample-shop:123456",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
        listing_url="https://item.rakuten.co.jp/sample-shop/123456/",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_model_match_via_title_overlap_and_brand_in_title() -> None:
    product = Product(name="GG Marmont Wallet", brand="GUCCI", model="456126")
    score = ListingMatcher().score(product, _listing(model_number="456126"))
    assert score >= Decimal("30")


def test_jan_match() -> None:
    product = Product(name="Other", brand="Other", model="1234567890123")
    score = ListingMatcher().score(product, _listing(jan_code="1234567890123"))
    assert score >= Decimal("40")


def test_title_similarity() -> None:
    product = Product(name="GG Marmont Wallet Black", brand="GUCCI", model="999")
    score = ListingMatcher().score(product, _listing())
    assert score > Decimal("0")


def test_different_product_lower_score() -> None:
    product = Product(name="Completely Different Shoes", brand="Prada", model="OTHER")
    score = ListingMatcher().score(product, _listing())
    reference = ListingMatcher().score(Product(name="GG Marmont Wallet", brand="GUCCI", model="456126"), _listing())
    assert score < reference


def test_color_variant() -> None:
    product = Product(name="GG Marmont Wallet Red", brand="GUCCI", model="456126")
    score = ListingMatcher().score(
        product,
        _listing(title="GUCCI GG Marmont Wallet Black", model_number="456126"),
    )
    assert score >= Decimal("30")


def test_size_variant() -> None:
    product = Product(name="Loafer Size 42", brand="Prada", model="PRD-LOAFER")
    listing = _listing(title="Prada Loafer Size 41", model_number="PRD-LOAFER")
    score = ListingMatcher().score(product, listing)
    assert score >= Decimal("30")


def test_insufficient_info() -> None:
    product = Product(name="", brand="", model="")
    score = ListingMatcher().score(product, _listing())
    assert score == Decimal("0")


def test_item_code_not_matched_to_overseas_sku() -> None:
    product = Product(name="Bag", brand="GUCCI", sku="P3-001")
    score = ListingMatcher().score(product, _listing(sku="sample-shop:123456"))
    assert score < Decimal("35")
