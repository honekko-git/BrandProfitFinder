"""Tests for batch candidate CSV import."""

from __future__ import annotations

from pathlib import Path

from profit_discovery.discovery_validation.batch_profit.candidate_import import (
    load_batch_candidates_from_csv,
    rows_to_candidates,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "batch_profit"


def test_csv_multiple_rows(tmp_path: Path) -> None:
    csv_path = FIXTURES / "candidates_valid.csv"
    result = load_batch_candidates_from_csv(csv_path, limit=20)
    assert len(result.candidates) == 2
    assert result.candidates[0].detected_subtype == "COMPACT_WALLET"
    assert result.candidates[0].detected_material == "Caviar"


def test_invalid_row_is_skipped(tmp_path: Path) -> None:
    csv_path = FIXTURES / "candidates_invalid.csv"
    result = load_batch_candidates_from_csv(csv_path, limit=20)
    assert len(result.candidates) == 1
    assert result.skipped_rows >= 1
    assert result.errors


def test_duplicate_removal() -> None:
    rows = [
        {
            "title": "Chanel Classic Wallet Black Caviar",
            "brand": "Chanel",
            "category": "Wallet",
            "purchase_price": "695",
            "currency": "USD",
            "purchase_url": "https://example.com/a",
            "source": "Fashionphile",
        },
        {
            "title": "Chanel Classic Wallet Black Caviar",
            "brand": "Chanel",
            "category": "Wallet",
            "purchase_price": "695",
            "currency": "USD",
            "purchase_url": "https://example.com/a",
            "source": "Fashionphile",
        },
    ]
    result = rows_to_candidates(rows, limit=20)
    assert len(result.candidates) == 1


def test_subtype_material_auto_detection() -> None:
    rows = [
        {
            "title": "Chanel Classic Wallet Black Caviar",
            "brand": "Chanel",
            "category": "Wallet",
            "purchase_price": "695",
            "currency": "USD",
            "purchase_url": "https://example.com/b",
            "source": "Fashionphile",
        }
    ]
    result = rows_to_candidates(rows)
    item = result.candidates[0]
    assert item.detected_subtype == "COMPACT_WALLET"
    assert item.detected_material == "Caviar"
