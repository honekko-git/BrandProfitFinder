"""Tests for market connector models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.connectors.models import MarketListing


def test_market_listing_creation() -> None:
    created_at = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    listing = MarketListing(
        id="listing-001",
        title="Chanel Classic Wallet",
        brand="Chanel",
        category="wallet",
        condition="used",
        price=Decimal("150000"),
        currency="JPY",
        market_name="Fashionphile",
        url="https://example.invalid/fashionphile/listing-001",
        source_type="FIXTURE",
        created_at=created_at,
    )

    assert listing.id == "listing-001"
    assert listing.title == "Chanel Classic Wallet"
    assert listing.market_name == "Fashionphile"
    assert listing.source_type == "FIXTURE"
    assert listing.created_at == created_at
