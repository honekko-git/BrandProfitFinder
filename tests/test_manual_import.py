"""Tests for manual market listing import."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketplace.importers.manual_importer import ManualImporter


def test_manual_importer_creates_market_listing() -> None:
    listing = ManualImporter().create_listing(
        title="CHANEL Classic Wallet",
        brand="Chanel",
        category="Wallet",
        condition="Used",
        price="50000",
        currency="JPY",
        market_name="Fashionphile",
        url="https://example.invalid/chanel-manual",
    )

    assert listing.title == "CHANEL Classic Wallet"
    assert listing.brand == "Chanel"
    assert listing.price == Decimal("50000")
    assert listing.market_name == "Fashionphile"
    assert listing.source_type == "IMPORT"
    assert listing.url == "https://example.invalid/chanel-manual"


def test_manual_importer_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError):
        ManualImporter().create_listing(
            title="",
            brand="Chanel",
            price="50000",
            market_name="Fashionphile",
        )
