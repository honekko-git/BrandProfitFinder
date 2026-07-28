"""Unit tests for marketplace.rakuten_response_parser."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from config.constants import MARKETPLACE_RAKUTEN
from marketplace.rakuten_response_parser import RakutenResponseParser
from models.marketplace_listing import MarketplaceListing

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal_single_item() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_normal.json"))
    assert len(listings) == 1
    assert listings[0].listing_id == "sample-shop:123456"


def test_parse_multiple_items() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_multiple.json"))
    assert len(listings) == 3


def test_empty_items() -> None:
    assert RakutenResponseParser().parse(_load("rakuten_search_empty.json")) == []


def test_missing_items_key() -> None:
    assert RakutenResponseParser().parse({"count": 0}) == []


def test_null_item_skipped() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_malformed.json"))
    assert listings == []


def test_missing_price_skipped() -> None:
    payload = {"Items": [{"itemName": "No Price", "itemCode": "x:1", "itemUrl": "https://example.com/x"}]}
    assert RakutenResponseParser().parse(payload) == []


def test_price_null_skipped() -> None:
    payload = {"Items": [{"itemName": "Null", "itemCode": "x:2", "itemPrice": None, "itemUrl": "https://example.com/x"}]}
    assert RakutenResponseParser().parse(payload) == []


def test_numeric_and_string_prices() -> None:
    payload = {
        "Items": [
            {"itemName": "A", "itemCode": "a:1", "itemPrice": 128000, "itemUrl": "https://example.com/a"},
            {"itemName": "B", "itemCode": "a:2", "itemPrice": "128,000", "itemUrl": "https://example.com/b"},
            {"itemName": "C", "itemCode": "a:3", "itemPrice": "￥128,000", "itemUrl": "https://example.com/c"},
        ]
    }
    listings = RakutenResponseParser().parse(payload)
    assert all(item.price_jpy == Decimal("128000") for item in listings)


def test_zero_and_negative_price_skipped() -> None:
    payload = {
        "Items": [
            {"itemName": "Zero", "itemCode": "z:1", "itemPrice": 0, "itemUrl": "https://example.com/z"},
            {"itemName": "Neg", "itemCode": "z:2", "itemPrice": -100, "itemUrl": "https://example.com/n"},
        ]
    }
    assert RakutenResponseParser().parse(payload) == []


def test_missing_title_uses_item_code() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_missing_fields.json"))
    partial = next(item for item in listings if item.listing_id == "partial-shop:002")
    assert partial.title == "partial-shop:002"


def test_free_shipping_postage_flag_zero() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_normal.json"))
    assert listings[0].shipping_jpy == Decimal("0")
    assert listings[0].shipping_unknown is False


def test_unknown_shipping_postage_flag_one() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "premium-shop:789012")
    assert item.shipping_jpy is None
    assert item.shipping_unknown is True


def test_point_rate() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "premium-shop:789012")
    assert item.point_rate == Decimal("2")


def test_point_rate_zero() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "outlet-shop:345678")
    assert item.point_rate == Decimal("0")


def test_review_fields() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_normal.json"))
    assert listings[0].sold_count == 10
    assert listings[0].seller_rating == Decimal("4.5")


def test_used_condition_from_caption() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_multiple.json"))
    item = next(i for i in listings if i.listing_id == "outlet-shop:345678")
    assert item.condition == "used"


def test_marketplace_name() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_normal.json"))
    assert listings[0].marketplace_name == MARKETPLACE_RAKUTEN


def test_metadata_pagination() -> None:
    meta = RakutenResponseParser().parse_metadata(_load("rakuten_search_multiple.json"))
    assert meta["count"] == 3
    assert meta["page"] == 1
    assert meta["page_count"] == 2
    assert meta["has_next_page"] is True
    assert meta["next_page"] == "2"


def test_no_next_page_on_last_page() -> None:
    meta = RakutenResponseParser().parse_metadata(_load("rakuten_search_normal.json"))
    assert meta["has_next_page"] is False
    assert meta["next_page"] is None


def test_payload_not_mutated() -> None:
    payload = _load("rakuten_search_normal.json")
    original = deepcopy(payload)
    RakutenResponseParser().parse(payload)
    assert payload == original


def test_malformed_skipped_without_failure() -> None:
    listings = RakutenResponseParser().parse(_load("rakuten_search_missing_fields.json"))
    assert len(listings) >= 1
    assert all(isinstance(item, MarketplaceListing) for item in listings)
