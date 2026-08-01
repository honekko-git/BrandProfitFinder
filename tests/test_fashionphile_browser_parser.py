"""Tests for Fashionphile browser HTML parsing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.browser_acquisition.fashionphile_acquirer import (
    FashionphileAcquirer,
    parse_fashionphile_html,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_parse_fashionphile_product_cards() -> None:
    html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    listings = parse_fashionphile_html(html)

    assert len(listings) >= 2
    wallet = next(item for item in listings if "Classic Wallet" in item.title)
    assert wallet.external_id == "fp-live-wallet-001"
    assert wallet.price == Decimal("695.00")
    assert wallet.currency == "USD"
    assert wallet.url.startswith("https://www.fashionphile.com/p/")
    assert wallet.brand == "Chanel"
    assert wallet.category == "Wallet"


def test_parse_fashionphile_json_ld() -> None:
    html = (FIXTURES / "fashionphile_json_ld.html").read_text(encoding="utf-8")
    listings = parse_fashionphile_html(html)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.title == "Chanel Classic Wallet Black Caviar"
    assert listing.price == Decimal("710.00")
    assert listing.currency == "USD"
    assert "jsonld" in listing.url


def test_parse_fashionphile_empty_result() -> None:
    html = (FIXTURES / "fashionphile_empty.html").read_text(encoding="utf-8")
    listings = parse_fashionphile_html(html)
    assert listings == []

    result = FashionphileAcquirer().acquire(html=html)
    assert result.status.value == "BLOCKED"
    assert result.blocking_reason == "SELECTOR_NOT_FOUND"
