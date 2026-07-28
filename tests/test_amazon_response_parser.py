"""Unit tests for marketplace.amazon_response_parser."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_AMAZON_JP
from marketplace.amazon_response_parser import AmazonResponseParser
from models.marketplace_listing import MarketplaceListing

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal_single_item() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_normal.json"))
    assert len(listings) == 1
    assert listings[0].listing_id == "B0TEST1234"


def test_parse_multiple_items() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_multiple.json"))
    assert len(listings) == 3


def test_empty_items() -> None:
    assert AmazonResponseParser().parse(_load("amazon_search_empty.json")) == []


def test_missing_items_key() -> None:
    assert AmazonResponseParser().parse({"total_results": 0}) == []


def test_null_item_skipped() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_malformed.json"))
    assert len(listings) == 0


def test_missing_price_skipped() -> None:
    payload = {"items": [{"asin": "X1", "title": "No Price"}]}
    assert AmazonResponseParser().parse(payload) == []


def test_price_null_skipped() -> None:
    payload = {"items": [{"asin": "X2", "title": "Null Price", "price": {"amount": None, "currency": "JPY"}}]}
    assert AmazonResponseParser().parse(payload) == []


def test_numeric_price() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_normal.json"))
    assert listings[0].price_jpy == Decimal("128000")


def test_string_price() -> None:
    payload = {"items": [{"asin": "S1", "title": "String Price", "price": {"amount": "99000", "currency": "JPY"}, "detail_page_url": "https://example.com/s1"}]}
    listings = AmazonResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("99000")


def test_comma_price() -> None:
    payload = {"items": [{"asin": "S2", "title": "Comma Price", "price": {"amount": "128,000", "currency": "JPY"}, "detail_page_url": "https://example.com/s2"}]}
    listings = AmazonResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("128000")


def test_yen_symbol_price() -> None:
    payload = {"items": [{"asin": "S3", "title": "Yen Price", "price": {"amount": "￥128,000", "currency": "JPY"}, "detail_page_url": "https://example.com/s3"}]}
    listings = AmazonResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("128000")


def test_zero_price_skipped() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_missing_fields.json"))
    assert all(item.listing_id != "B0PARTIAL4" for item in listings)


def test_negative_price_skipped() -> None:
    payload = {"items": [{"asin": "NEG", "title": "Negative", "price": {"amount": -100, "currency": "JPY"}, "detail_page_url": "https://example.com/neg"}]}
    assert AmazonResponseParser().parse(payload) == []


def test_non_jpy_skipped() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_missing_fields.json"))
    assert all(item.listing_id != "B0PARTIAL5" for item in listings)


def test_missing_title_uses_asin() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_missing_fields.json"))
    partial = next(item for item in listings if item.listing_id == "B0PARTIAL2")
    assert partial.title == "B0PARTIAL2"


def test_missing_asin_with_title() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_missing_fields.json"))
    no_asin = next(item for item in listings if item.title == "No ASIN Item")
    assert no_asin.listing_id == "No ASIN Item"


def test_free_shipping() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_normal.json"))
    assert listings[0].shipping_jpy == Decimal("0")
    assert listings[0].shipping_unknown is False


def test_missing_shipping_unknown() -> None:
    payload = {"items": [{"asin": "SH1", "title": "No Shipping", "price": {"amount": 1000, "currency": "JPY"}, "detail_page_url": "https://example.com/sh1"}]}
    listings = AmazonResponseParser().parse(payload)
    assert listings[0].shipping_jpy is None
    assert listings[0].shipping_unknown is True


def test_missing_seller() -> None:
    payload = {"items": [{"asin": "SE1", "title": "No Seller", "price": {"amount": 1000, "currency": "JPY"}, "detail_page_url": "https://example.com/se1"}]}
    listings = AmazonResponseParser().parse(payload)
    assert listings[0].seller_name == ""


def test_points_zero() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "B0TEST2002")
    assert item.points_jpy == Decimal("0")


def test_points_missing() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "B0TEST2003")
    assert item.points_jpy is None


def test_prime_true_false() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_multiple.json"))
    prime = next(i for i in listings if i.listing_id == "B0TEST2001")
    non_prime = next(i for i in listings if i.listing_id == "B0TEST2002")
    assert prime.is_prime is True
    assert non_prime.is_prime is False


def test_marketplace_name() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_normal.json"))
    assert listings[0].marketplace_name == MARKETPLACE_AMAZON_JP


def test_malformed_item_skipped_without_failure() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_missing_fields.json"))
    assert len(listings) >= 1


def test_payload_not_mutated() -> None:
    payload = _load("amazon_search_normal.json")
    original = deepcopy(payload)
    AmazonResponseParser().parse(payload)
    assert payload == original


def test_metadata_total_results() -> None:
    total, token = AmazonResponseParser().parse_metadata(_load("amazon_search_multiple.json"))
    assert total == 3
    assert token == "page-2-token"


def test_metadata_missing_total_results() -> None:
    total, token = AmazonResponseParser().parse_metadata({"items": []})
    assert total is None
    assert token is None


def test_all_results_are_marketplace_listing() -> None:
    listings = AmazonResponseParser().parse(_load("amazon_search_multiple.json"))
    assert all(isinstance(item, MarketplaceListing) for item in listings)
