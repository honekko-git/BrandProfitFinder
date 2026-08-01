"""Tests for acquisition CSV import."""

from __future__ import annotations

from pathlib import Path

from marketplace.acquisition_workspace.candidate_parser import csv_rows_to_parsed, read_acquisition_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "batch_profit"


def test_valid_csv_rows(tmp_path: Path) -> None:
    rows, errors = read_acquisition_csv(FIXTURES / "candidates_valid.csv")
    parsed, row_errors, skipped = csv_rows_to_parsed(rows)
    assert not errors
    assert len(parsed) == 2
    assert parsed[0].title.startswith("Chanel")
    assert parsed[0].purchase_price > 0


def test_utf8_bom_csv(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(
        b"\xef\xbb\xbftitle,purchase_price,currency,purchase_url\n"
        b"Chanel Wallet,695,USD,https://example.com/a\n"
    )
    rows, _ = read_acquisition_csv(path)
    parsed, _, skipped = csv_rows_to_parsed(rows)
    assert len(parsed) == 1
    assert parsed[0].currency == "USD"


def test_invalid_row_skip_without_stopping_batch(tmp_path: Path) -> None:
    path = tmp_path / "mixed.csv"
    path.write_text(
        "title,purchase_price,currency,purchase_url\n"
        "Good Item,695,USD,https://example.com/good\n"
        ",695,USD,https://example.com/bad-title\n"
        "Bad Price,,USD,https://example.com/bad-price\n",
        encoding="utf-8",
    )
    rows, _ = read_acquisition_csv(path)
    parsed, errors, skipped = csv_rows_to_parsed(rows)
    assert len(parsed) == 1
    assert skipped >= 2
    assert any("missing title" in err for err in errors)


def test_optional_brand_warning() -> None:
    rows = [{"title": "Chanel Wallet", "purchase_price": "695", "currency": "USD", "purchase_url": "https://example.com/x"}]
    parsed, _, _ = csv_rows_to_parsed(rows)
    assert parsed[0].brand == ""
    assert "brand not provided" in parsed[0].warnings


def test_unsupported_currency_still_parsed() -> None:
    rows = [{"title": "Item", "purchase_price": "100", "currency": "CNY", "purchase_url": "https://example.com/x"}]
    parsed, _, _ = csv_rows_to_parsed(rows)
    assert parsed[0].currency == "CNY"
