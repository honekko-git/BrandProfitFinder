"""Unit tests for marketplace.yahoo_response_parser."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from config.constants import MARKETPLACE_YAHOO
from marketplace.yahoo_response_parser import YahooResponseParser
from models.marketplace_listing import MarketplaceListing

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_success_response() -> None:
    payload = _load("yahoo_item_search_success.json")
    listings = YahooResponseParser().parse(payload, source_query="gucci")
    assert len(listings) == 3


def test_multiple_hits() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert all(isinstance(item, MarketplaceListing) for item in listings)


def test_marketplace_name_yahoo() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert all(item.marketplace_name == MARKETPLACE_YAHOO for item in listings)


def test_title_mapping() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].title == "Gucci Marmont Leather Bag"


def test_decimal_price() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].price_jpy == Decimal("98000")


def test_listing_url() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].listing_url.startswith("https://")


def test_image_url() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].image_url.endswith(".jpg")


def test_seller_name() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].seller_name == "Example Store"


def test_jan_code_string() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    assert listings[0].jan_code == "4901234567890"


def test_jan_leading_zero_preserved() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_success.json"))
    jan_listing = next(item for item in listings if item.jan_code == "0123456789012")
    assert jan_listing.jan_code.startswith("0")


def test_empty_hits() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_empty.json"))
    assert listings == []


def test_missing_hits_key() -> None:
    listings = YahooResponseParser().parse({"totalResultsAvailable": 0})
    assert listings == []


def test_hits_none() -> None:
    listings = YahooResponseParser().parse({"hits": None})
    assert listings == []


def test_hits_invalid_type() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_invalid.json"))
    assert listings == []


def test_partial_fields() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_partial.json"))
    assert len(listings) == 2


def test_missing_title_still_parsed_with_code() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_partial.json"))
    invalid = next(item for item in listings if item.listing_id == "YH-P2")
    assert invalid.title == "YH-P2"


def test_zero_price_parsed() -> None:
    listings = YahooResponseParser().parse(_load("yahoo_item_search_partial.json"))
    zero = next(item for item in listings if item.listing_id == "YH-P2")
    assert zero.price_jpy == Decimal("0")


def test_invalid_price_becomes_zero() -> None:
    payload = {"hits": [{"name": "Bad Price", "code": "X1", "price": "abc", "url": "https://example.com/x"}]}
    listings = YahooResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("0")


def test_payload_not_mutated() -> None:
    payload = _load("yahoo_item_search_success.json")
    original = deepcopy(payload)
    YahooResponseParser().parse(payload)
    assert payload == original


def test_invalid_candidate_does_not_block_valid() -> None:
    payload = {
        "hits": [
            {"name": "Good", "code": "G1", "price": 1000, "url": "https://example.com/g1"},
            {"name": "", "code": "", "price": 1000},
        ]
    }
    listings = YahooResponseParser().parse(payload)
    assert len(listings) == 1
    assert listings[0].listing_id == "G1"
