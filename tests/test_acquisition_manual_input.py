"""Tests for manual multi-row input."""

from __future__ import annotations

from marketplace.acquisition_workspace.candidate_parser import MAX_MANUAL_ROWS, parse_manual_rows


def test_multiple_valid_rows() -> None:
    rows = [
        {"title": "Chanel Wallet A", "price": "695", "currency": "USD", "url": "https://example.com/a"},
        {"title": "Chanel Wallet B", "price": "820", "currency": "USD", "url": "https://example.com/b"},
    ]
    result = parse_manual_rows(rows)
    assert len(result.candidates) == 2
    assert not result.errors


def test_empty_row_skip() -> None:
    rows = [
        {"title": "", "price": "", "url": ""},
        {"title": "Chanel Wallet", "price": "695", "currency": "USD", "url": "https://example.com/a"},
    ]
    result = parse_manual_rows(rows)
    assert len(result.candidates) == 1


def test_row_level_errors() -> None:
    rows = [{"title": "Missing URL", "price": "695", "currency": "USD", "url": ""}]
    result = parse_manual_rows(rows)
    assert len(result.candidates) == 0
    assert result.skipped_rows == 1
    assert any("row 1" in err for err in result.errors)


def test_maximum_rows_enforced() -> None:
    rows = [
        {
            "title": f"Item {index}",
            "price": "100",
            "currency": "USD",
            "url": f"https://example.com/{index}",
        }
        for index in range(15)
    ]
    result = parse_manual_rows(rows)
    assert len(result.candidates) == MAX_MANUAL_ROWS
