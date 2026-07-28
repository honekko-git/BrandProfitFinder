"""Tests for StockX response parser."""

import json
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_STOCKX
from marketplace.stockx_exceptions import StockXParseError, StockXResponseError
from marketplace.stockx_response_parser import StockXResponseParser, preprocess_stockx_condition

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = StockXResponseParser().parse(_load("stockx_search_normal.json"))
    assert result.valid_count == 3
    listing = result.listings[0]
    assert listing.marketplace_name == MARKETPLACE_STOCKX
    assert listing.source_metadata.get("source_stockx_style_code") == "DD1391-100"
    assert listing.source_metadata.get("source_stockx_price_source") == "LOWEST_ASK"


def test_parse_multiple() -> None:
    assert len(StockXResponseParser().parse(_load("stockx_search_multiple.json")).listings) == 3


def test_empty() -> None:
    assert StockXResponseParser().parse(_load("stockx_search_empty.json")).listings == []


def test_malformed_top_level() -> None:
    with pytest.raises(StockXParseError):
        StockXResponseParser().parse(_load("stockx_search_malformed.json"))


def test_missing_fields_rejected() -> None:
    result = StockXResponseParser().parse(_load("stockx_search_missing_fields.json"))
    assert result.listings == []


def test_duplicate_listing_id() -> None:
    result = StockXResponseParser().parse(_load("stockx_search_duplicate.json"))
    assert len(result.listings) == 1


def test_non_jpy_excluded() -> None:
    assert StockXResponseParser().parse(_load("stockx_search_non_jpy.json")).listings == []


def test_lowest_ask_unknown_filtered() -> None:
    assert StockXResponseParser().parse(_load("stockx_search_lowest_ask_unknown.json")).listings == []


def test_sold_excluded() -> None:
    assert StockXResponseParser().parse(_load("stockx_search_sold.json")).listings == []


def test_low_liquidity_filter() -> None:
    filtered = StockXResponseParser().parse(
        _load("stockx_search_low_liquidity.json"),
        include_low_liquidity=False,
    )
    assert filtered.listings == []


def test_last_sale_price_source_warning() -> None:
    result = StockXResponseParser().parse(
        _load("stockx_search_normal.json"),
        preferred_price_source="LAST_SALE",
    )
    assert result.listings
    assert any("last sale" in w.lower() for w in result.warnings)


def test_validate_payload() -> None:
    with pytest.raises(StockXResponseError):
        StockXResponseParser.validate_payload({"items": "bad"})


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ("Deadstock", "deadstock"),
        ("New with Defects", "defects"),
        ("Pre-Owned", "pre-owned"),
        ("For Parts", "parts"),
    ],
)
def test_preprocess_condition(raw: str, fragment: str) -> None:
    key, _, warnings = preprocess_stockx_condition(raw)
    assert fragment in key or any(fragment in w for w in warnings)
