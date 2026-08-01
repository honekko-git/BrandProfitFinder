"""Tests for Fashionphile real response mapping."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from marketplace.connectors.live.exceptions import MarketConnectorParseError
from marketplace.connectors.live.fashionphile.parser import parse_fashionphile_response


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_fashionphile_real_fixture_to_market_listing() -> None:
    payload = json.loads((FIXTURES_DIR / "fashionphile_search_normal.json").read_text(encoding="utf-8"))
    listings = parse_fashionphile_response(payload)

    assert listings
    listing = listings[0]
    assert listing.id == "fashionphile-demo-001"
    assert listing.title.startswith("GUCCI")
    assert listing.price == Decimal("980000")
    assert listing.currency == "JPY"
    assert listing.url.startswith("https://")
    assert listing.market_name == "Fashionphile"
    assert listing.source_type == "LIVE"


def test_parse_fashionphile_supplier_products_shape() -> None:
    payload = json.loads((FIXTURES_DIR / "fashionphile" / "fashionphile_products.json").read_text(encoding="utf-8"))
    listings = parse_fashionphile_response({"products": payload["products"]})

    wallet = next(listing for listing in listings if listing.id == "fp-chanel-wallet-001")
    assert wallet.brand == "Chanel"
    assert wallet.price == Decimal("700.0")
    assert wallet.currency == "USD"
    assert "example.invalid" in wallet.url


def test_parse_fashionphile_requires_listing_rows() -> None:
    with pytest.raises(MarketConnectorParseError):
        parse_fashionphile_response({"marketplace": "fashionphile"})
