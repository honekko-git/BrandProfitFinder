"""Tests for CSV market listing importer."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.importers.csv_importer import CSVImporter


def test_csv_importer_loads_headered_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "market_listings.csv"
    csv_path.write_text(
        "title,brand,category,condition,price,currency,market_name,url\n"
        "CHANEL Wallet,CHANEL,Wallet,Used,50000,JPY,Fashionphile,https://example.invalid/chanel-wallet\n",
        encoding="utf-8",
    )

    importer = CSVImporter()
    rows = importer.load_csv(csv_path)

    assert len(rows) == 1
    assert rows[0]["title"] == "CHANEL Wallet"
    assert rows[0]["brand"] == "CHANEL"


def test_csv_importer_validates_required_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "market_listings.csv"
    csv_path.write_text(
        "title,brand,category,condition,price,currency,market_name,url\n"
        ",CHANEL,Wallet,Used,50000,JPY,Fashionphile,https://example.invalid/missing-title\n"
        "Valid Wallet,CHANEL,Wallet,Used,abc,JPY,Fashionphile,https://example.invalid/bad-price\n",
        encoding="utf-8",
    )

    importer = CSVImporter()
    importer.load_csv(csv_path)
    valid_rows = importer.validate_rows()
    result = importer.to_market_listings()

    assert valid_rows == []
    assert result.listings == []
    assert result.skipped_rows == 0
    assert importer.errors


def test_csv_importer_converts_rows_to_market_listings(tmp_path: Path) -> None:
    csv_path = tmp_path / "market_listings.csv"
    csv_path.write_text(
        "CHANEL Wallet,CHANEL,Wallet,Used,50000,JPY,Fashionphile,https://example.invalid/chanel-wallet\n",
        encoding="utf-8",
    )

    importer = CSVImporter()
    importer.load_csv(csv_path)
    importer.validate_rows()
    result = importer.to_market_listings()

    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.title == "CHANEL Wallet"
    assert listing.brand == "CHANEL"
    assert listing.price == Decimal("50000")
    assert listing.currency == "JPY"
    assert listing.market_name == "Fashionphile"
    assert listing.source_type == "IMPORT"
