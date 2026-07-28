"""Unit tests for marketplace.yahoo_auction_response_parser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_YAHOO_AUCTION
from marketplace.yahoo_auction_exceptions import YahooAuctionResponseError
from marketplace.yahoo_auction_response_parser import YahooAuctionResponseParser

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal_single_item() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_normal.json"))
    assert len(listings) == 1
    assert listings[0].listing_id == "test-auction-001"
    assert listings[0].marketplace_name == MARKETPLACE_YAHOO_AUCTION


def test_parse_multiple_items() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_multiple.json"))
    assert len(listings) == 3


def test_empty_items() -> None:
    assert YahooAuctionResponseParser().parse(_load("yahoo_auction_search_empty.json")) == []


def test_missing_items_key() -> None:
    assert YahooAuctionResponseParser().parse({"total_results": 0}) == []


def test_null_item_skipped() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_malformed.json"))
    assert listings == []


def test_missing_title_with_auction_id() -> None:
    payload = {
        "items": [
            {
                "auction_id": "id-only",
                "current_price": 10000,
                "listing_status": "active",
                "url": "https://example.invalid/auction/id-only",
            }
        ]
    }
    listings = YahooAuctionResponseParser().parse(payload)
    assert len(listings) == 1
    assert listings[0].title == "id-only"


def test_missing_all_prices_skipped() -> None:
    payload = {
        "items": [
            {
                "auction_id": "no-price",
                "title": "No Price",
                "listing_status": "active",
                "url": "https://example.invalid/auction/no-price",
            }
        ]
    }
    assert YahooAuctionResponseParser().parse(payload) == []


def test_numeric_price() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_normal.json"))
    assert listings[0].price_jpy == Decimal("108000")


def test_string_price() -> None:
    payload = {
        "items": [
            {
                "auction_id": "str-price",
                "title": "String Price",
                "current_price": "99000",
                "listing_status": "active",
                "url": "https://example.invalid/auction/str-price",
            }
        ]
    }
    listings = YahooAuctionResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("99000")


def test_comma_price() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_missing_fields.json"))
    assert any(item.price_jpy == Decimal("45000") for item in listings)


def test_yen_symbol_price() -> None:
    payload = {
        "items": [
            {
                "auction_id": "yen-price",
                "title": "Yen Price",
                "current_price": "￥128,000",
                "listing_status": "active",
                "url": "https://example.invalid/auction/yen-price",
            }
        ]
    }
    listings = YahooAuctionResponseParser().parse(payload)
    assert listings[0].price_jpy == Decimal("128000")


def test_zero_price_skipped() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_missing_fields.json"))
    assert all(item.listing_id != "test-auction-partial-2" for item in listings)


def test_negative_price_skipped() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_malformed.json"))
    assert listings == []


def test_active_buy_now_price_preferred() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_normal.json"))
    assert listings[0].price_jpy == Decimal("108000")
    assert listings[0].source_metadata["price_source"] == "buy_now_price"


def test_active_current_price_when_no_buy_now() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_active.json"))
    current_only = next(item for item in listings if item.listing_id == "test-auction-active-001")
    assert current_only.price_jpy == Decimal("88000")
    assert current_only.source_metadata["price_source"] == "current_price"
    assert current_only.source_metadata["price_is_provisional"] is True


def test_sold_winning_price() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_sold.json"))
    sold = next(item for item in listings if item.listing_id == "test-auction-sold-001")
    assert sold.price_jpy == Decimal("95000")
    assert sold.source_metadata["price_source"] == "winning_price"


def test_sold_without_winning_price_skipped() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_sold.json"))
    assert all(item.listing_id != "test-auction-sold-002" for item in listings)


def test_free_shipping() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_multiple.json"))
    free = next(item for item in listings if item.listing_id == "test-auction-101")
    assert free.shipping_jpy == Decimal("0")
    assert free.shipping_unknown is False


def test_explicit_shipping() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_multiple.json"))
    paid = next(item for item in listings if item.listing_id == "test-auction-102")
    assert paid.shipping_jpy == Decimal("800")
    assert paid.shipping_unknown is False


def test_unknown_shipping() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_normal.json"))
    assert listings[0].shipping_jpy is None
    assert listings[0].shipping_unknown is True


def test_condition_conversion() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_active.json"))
    buy_now = next(item for item in listings if item.listing_id == "test-auction-active-002")
    assert buy_now.condition == "new"


def test_status_conversion() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_sold.json"))
    sold = next(item for item in listings if item.listing_id == "test-auction-sold-001")
    assert sold.source_metadata["listing_status"] == "sold"
    assert sold.availability == "sold"


def test_auction_type_conversion() -> None:
    listings = YahooAuctionResponseParser().parse(_load("yahoo_auction_search_normal.json"))
    assert listings[0].source_metadata["auction_type"] == "auction_with_buy_now"


def test_malformed_item_skipped() -> None:
    payload = {"items": ["bad", {"auction_id": "x", "current_price": -1, "listing_status": "active"}]}
    assert YahooAuctionResponseParser().parse(payload) == []


def test_page_metadata() -> None:
    meta = YahooAuctionResponseParser().parse_metadata(_load("yahoo_auction_search_multiple.json"))
    assert meta["page"] == 1
    assert meta["page_count"] == 2
    assert meta["has_next_page"] is True
    assert meta["next_page"] == "2"


def test_no_next_page_on_last_page() -> None:
    meta = YahooAuctionResponseParser().parse_metadata(_load("yahoo_auction_search_normal.json"))
    assert meta["has_next_page"] is False
    assert meta["next_page"] is None


def test_validate_payload_invalid_items_type() -> None:
    with pytest.raises(YahooAuctionResponseError, match="items must be a list"):
        YahooAuctionResponseParser.validate_payload({"items": "bad"})
