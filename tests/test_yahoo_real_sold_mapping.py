"""Tests for Yahoo real sold response mapping."""

from __future__ import annotations

import json
from pathlib import Path

from marketplace.domestic_market.yahoo_auction.parser import parse_sold_items, to_market_price_data
from profit_discovery.discovery_validation.yahoo_sold_mapper import (
    normalize_yahoo_sold_payload,
    summarize_sold_prices,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_normalize_yahoo_connector_fixture_to_sold_prices() -> None:
    payload = json.loads((FIXTURES_DIR / "yahoo_auction" / "chanel_wallet.json").read_text(encoding="utf-8"))
    normalized = normalize_yahoo_sold_payload(payload)

    assert len(normalized) == 5
    assert normalized[0]["sold_price"] == 155000
    summary = summarize_sold_prices(normalized)
    assert summary["sample_count"] == 5
    assert summary["average_price_jpy"] == 160000.0
    assert summary["median_price_jpy"] == 160000.0


def test_normalize_yahoo_http_transport_shape() -> None:
    payload = {
        "items": [
            {"title": "Chanel Wallet", "sold_price": 155000, "url": "https://example.invalid/1"},
            {"title": "Chanel Wallet 2", "winning_price": 160000, "url": "https://example.invalid/2"},
        ]
    }
    normalized = normalize_yahoo_sold_payload(payload)
    parsed = parse_sold_items(normalized)
    summary = to_market_price_data(parsed, product_keyword="Chanel wallet")

    assert summary["sample_count"] == 2
    assert summary["average_price_jpy"] == 157500.0
    assert summary["median_price_jpy"] == 157500.0
