"""Unit tests for Amazon response adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace.amazon_exceptions import AmazonResponseParseError
from marketplace.amazon_response_adapter import adapt_amazon_search_response
from marketplace.amazon_response_parser import AmazonResponseParser

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_adapt_paapi_asin_mapping() -> None:
    adapted = adapt_amazon_search_response(_load("amazon_paapi_search_raw.json"))
    assert adapted["items"][0]["asin"] == "B0TEST1234"


def test_adapt_paapi_price_mapping() -> None:
    adapted = adapt_amazon_search_response(_load("amazon_paapi_search_raw.json"))
    assert adapted["items"][0]["price"] == {"amount": 128000, "currency": "JPY"}


def test_adapt_paapi_brand_mapping() -> None:
    adapted = adapt_amazon_search_response(_load("amazon_paapi_search_raw.json"))
    assert adapted["items"][0]["brand"] == "GUCCI"


def test_adapt_paapi_pagination_metadata() -> None:
    adapted = adapt_amazon_search_response(_load("amazon_paapi_search_raw.json"))
    assert adapted["total_results"] == 3
    assert adapted["next_page_token"] == "2"


def test_adapt_internal_payload_passthrough() -> None:
    payload = _load("amazon_search_normal.json")
    adapted = adapt_amazon_search_response(payload)
    assert adapted == payload


def test_adapted_payload_parses_with_existing_parser() -> None:
    adapted = adapt_amazon_search_response(_load("amazon_paapi_search_raw.json"))
    listings = AmazonResponseParser().parse(adapted, source_query="gucci")
    assert len(listings) == 2
    assert listings[0].listing_id == "B0TEST1234"
    assert listings[0].brand == "GUCCI"


def test_adapt_api_errors_raises_parse_error() -> None:
    raw = {"Errors": [{"Code": "InvalidParameterValue", "Message": "Bad request"}]}
    with pytest.raises(AmazonResponseParseError, match="InvalidParameterValue"):
        adapt_amazon_search_response(raw)


def test_adapt_missing_search_result_raises() -> None:
    with pytest.raises(AmazonResponseParseError, match="missing SearchResult"):
        adapt_amazon_search_response({"status": "ok"})
