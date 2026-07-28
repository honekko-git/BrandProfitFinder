"""Unit tests for marketplace.listing_matcher."""

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher, MatchConfig
from marketplace.listing_validator import validate_listing
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def _product(**kwargs) -> Product:
    defaults = dict(name="Gucci Marmont Bag", brand="Gucci", sku="P3-001", model="GG-MARMONT")
    defaults.update(kwargs)
    return Product(**defaults)


def _listing(**kwargs) -> MarketplaceListing:
    defaults = dict(
        marketplace_name="local",
        title="Gucci Marmont Bag",
        brand="Gucci",
        sku="P3-001",
        model_number="GG-MARMONT",
        jan_code="4901234567890",
        price_jpy=Decimal("100000"),
        listing_url="https://example.com/item",
    )
    defaults.update(kwargs)
    return MarketplaceListing(**defaults)


def test_jan_match_via_sku() -> None:
    matcher = ListingMatcher()
    product = _product(sku="4901234567890")
    listing = _listing(jan_code="4901234567890", sku="OTHER")
    assert matcher.score(product, listing) >= Decimal("40")


def test_sku_exact_match() -> None:
    matcher = ListingMatcher()
    score = matcher.score(_product(), _listing())
    assert score >= Decimal("35")


def test_brand_match() -> None:
    matcher = ListingMatcher()
    score = matcher.score(_product(), _listing(sku="OTHER"))
    assert score >= Decimal("15")


def test_title_match() -> None:
    matcher = ListingMatcher()
    score = matcher.score(_product(), _listing(sku="", brand="", model_number=""))
    assert score > Decimal("0")


def test_case_insensitive_match() -> None:
    matcher = ListingMatcher()
    product = _product(brand="gucci")
    listing = _listing(brand="GUCCI")
    assert matcher.score(product, listing) >= Decimal("15")


def test_whitespace_normalization() -> None:
    matcher = ListingMatcher()
    product = _product(sku=" P3-001 ")
    listing = _listing(sku="P3-001")
    assert matcher.score(product, listing) >= Decimal("35")


def test_symbol_difference() -> None:
    matcher = ListingMatcher()
    product = _product(model="GG-MARMONT")
    listing = _listing(model_number="GG MARMONT")
    assert matcher.score(product, listing) >= Decimal("30")


def test_fullwidth_halfwidth_normalization() -> None:
    matcher = ListingMatcher()
    product = _product(name="Gucci Bag")
    listing = _listing(title="Ｇｕｃｃｉ Bag", sku="", brand="", model_number="")
    assert matcher.score(product, listing) > Decimal("0")


def test_non_matching_product() -> None:
    matcher = ListingMatcher()
    product = _product(name="Unrelated", brand="Other", sku="X", model="Y")
    listing = _listing(title="Different Item", brand="Another", sku="Z", model_number="Q")
    assert matcher.is_match(product, listing, threshold=Decimal("80")) is False


def test_match_and_rank_order() -> None:
    matcher = ListingMatcher()
    product = _product()
    listings = [
        _listing(title="Other Brand Bag", brand="Other", sku="X", model_number=""),
        _listing(),
    ]
    ranked = matcher.match_and_rank(product, listings)
    assert ranked[0].sku == "P3-001"


def test_stable_sort_on_tie() -> None:
    matcher = ListingMatcher(MatchConfig(sku_score=Decimal("0"), model_score=Decimal("0"), jan_score=Decimal("0")))
    product = _product(name="Alpha Item")
    listings = [
        _listing(title="Beta Item", listing_id="B", sku="", brand="", model_number=""),
        _listing(title="Alpha Item", listing_id="A", sku="", brand="", model_number=""),
    ]
    ranked = matcher.match_and_rank(product, listings)
    assert ranked[0].listing_id == "A"


def test_input_list_not_modified() -> None:
    matcher = ListingMatcher()
    listings = [_listing()]
    original_score = listings[0].match_score
    matcher.match_and_rank(_product(), listings)
    assert listings[0].match_score == original_score


def test_exclude_invalid_listings() -> None:
    matcher = ListingMatcher()
    invalid = _listing(title="", price_jpy=Decimal("0"))
    ranked = matcher.match_and_rank(_product(), [invalid, _listing()], exclude_invalid=True)
    assert len(ranked) == 1


def test_threshold_match() -> None:
    matcher = ListingMatcher()
    assert matcher.is_match(_product(), _listing()) is True
