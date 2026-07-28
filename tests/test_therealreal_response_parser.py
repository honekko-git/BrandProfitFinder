"""Tests for The RealReal response parser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_THEREALREAL
from marketplace.therealreal_exceptions import TheRealRealParseError, TheRealRealResponseError
from marketplace.therealreal_response_parser import (
    TheRealRealResponseParser,
    preprocess_therealreal_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_normal.json"))
    assert result.valid_count == 1
    assert result.listings[0].marketplace_name == MARKETPLACE_THEREALREAL
    assert result.listings[0].source_metadata.get("source_final_sale") is False


def test_parse_multiple() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_multiple.json"))
    assert len(result.listings) == 3


def test_empty() -> None:
    assert TheRealRealResponseParser().parse(_load("therealreal_search_empty.json")).listings == []


def test_missing_fields_partial() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_missing_fields.json"))
    assert len(result.listings) == 1


def test_malformed_top_level() -> None:
    with pytest.raises(TheRealRealParseError):
        TheRealRealResponseParser().parse(_load("therealreal_search_malformed.json"))


def test_final_sale_excluded_when_disabled() -> None:
    result = TheRealRealResponseParser().parse(
        _load("therealreal_search_final_sale.json"),
        include_final_sale=False,
    )
    assert result.listings == []


def test_final_sale_included_by_default() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_final_sale.json"))
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata.get("source_final_sale") is True


def test_return_conflict_warning() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_return_conflict.json"))
    assert len(result.listings) == 1
    assert any("conflicts" in w for w in result.warnings)


def test_shipping_unknown() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_shipping_unknown.json"))
    assert result.listings[0].shipping_unknown is True


def test_discount_inconsistent() -> None:
    result = TheRealRealResponseParser().parse(_load("therealreal_search_discount_inconsistent.json"))
    assert any("inconsistent" in w for w in result.warnings)


def test_sold_excluded() -> None:
    assert TheRealRealResponseParser().parse(_load("therealreal_search_sold.json")).listings == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pristine", "pristine"),
        ("Moderate Wear", "moderate wear"),
        ("Final Sale", ""),
        ("Heavy Wear", "heavy wear"),
    ],
)
def test_preprocess_condition(raw: str, expected: str) -> None:
    text, _ = preprocess_therealreal_condition(raw)
    assert text == expected


def test_validate_payload() -> None:
    with pytest.raises(TheRealRealResponseError):
        TheRealRealResponseParser.validate_payload({"items": "bad"})
