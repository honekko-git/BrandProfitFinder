"""Tests for GOAT response parser."""

import json
from pathlib import Path

import pytest

from config.constants import CURRENCY_JPY, MARKETPLACE_GOAT
from marketplace.goat_exceptions import GoatParseError, GoatResponseError
from marketplace.goat_response_parser import (
    GoatResponseParser,
    normalize_goat_box_condition,
    normalize_goat_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = GoatResponseParser().parse(_load("goat_search_normal.json"))
    assert result.valid_count == 3
    listing = result.listings[0]
    assert listing.marketplace_name == MARKETPLACE_GOAT
    assert listing.source_metadata.get("source_goat_style_code") == "G-DEMO-TOTE-001"
    assert listing.source_metadata.get("source_goat_condition_normalized") == "new"


def test_parse_used_condition() -> None:
    result = GoatResponseParser().parse(_load("goat_search_used.json"))
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata.get("source_goat_condition_normalized") == "used"


def test_parse_missing_box_metadata() -> None:
    result = GoatResponseParser().parse(_load("goat_search_missing_box.json"))
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata.get("source_goat_box_condition") == "damaged"
    assert result.listings[0].source_metadata.get("source_goat_condition_normalized") == "new_with_defects"


def test_missing_optional_fields() -> None:
    payload = {
        "items": [
            {
                "listing_id": "goat-minimal",
                "title": "Minimal Synthetic Listing",
                "price": {"amount": 8000, "currency": "JPY"},
                "sale_status": "ACTIVE",
                "inventory": {"status": "AVAILABLE"},
            }
        ]
    }
    result = GoatResponseParser().parse(payload)
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata.get("source_goat_sku") is None


def test_invalid_title_rejected() -> None:
    result = GoatResponseParser().parse(_load("goat_search_invalid.json"))
    assert len(result.listings) == 1
    assert result.listings[0].listing_id == "goat-valid-control"


def test_invalid_price_rejected() -> None:
    result = GoatResponseParser().parse(_load("goat_search_invalid.json"))
    assert all(item.listing_id != "goat-invalid-price" for item in result.listings)


def test_missing_price_rejected() -> None:
    payload = {
        "items": [
            {
                "listing_id": "goat-no-price",
                "title": "No Price Synthetic Listing",
                "sale_status": "ACTIVE",
                "inventory": {"status": "AVAILABLE"},
            }
        ]
    }
    assert GoatResponseParser().parse(payload).listings == []


def test_non_jpy_excluded_by_default() -> None:
    assert GoatResponseParser().parse(_load("goat_search_usd.json")).listings == []


def test_non_jpy_preserved_with_allow_unknown_currency() -> None:
    result = GoatResponseParser().parse(
        _load("goat_search_usd.json"),
        allow_unknown_currency=True,
    )
    assert len(result.listings) == 1
    assert result.listings[0].currency == "USD"
    assert any("no conversion" in w.lower() for w in result.warnings)


def test_unavailable_excluded() -> None:
    result = GoatResponseParser().parse(_load("goat_search_unavailable.json"))
    assert len(result.listings) == 1
    assert result.listings[0].listing_id == "goat-active-001"


def test_unavailable_included_when_enabled() -> None:
    result = GoatResponseParser().parse(
        _load("goat_search_unavailable.json"),
        include_unavailable=True,
    )
    assert len(result.listings) == 2


def test_duplicate_listing_id() -> None:
    result = GoatResponseParser().parse(_load("goat_search_duplicate.json"))
    assert len(result.listings) == 1


def test_unknown_condition_preserved() -> None:
    condition, warnings = normalize_goat_condition("mystery grade")
    assert condition == "unknown"
    assert warnings


def test_box_condition_preserved() -> None:
    box, _warnings = normalize_goat_box_condition("missing")
    assert box == "missing"


def test_style_code_and_sku_preserved() -> None:
    result = GoatResponseParser().parse(_load("goat_search_normal.json"))
    listing = result.listings[0]
    assert listing.source_metadata.get("source_goat_style_code") == "G-DEMO-TOTE-001"
    assert listing.source_metadata.get("source_goat_sku") == "INTERNAL-GOAT-SKU-001"


def test_metadata_warning_propagation() -> None:
    payload = {
        "items": [
            {
                "listing_id": "goat-warn",
                "title": "Warning Synthetic Listing",
                "price": {"amount": 9000, "currency": "JPY"},
                "sale_status": "ACTIVE",
                "inventory": {"status": "AVAILABLE"},
                "metadata": {"parse_warnings": ["fixture warning example"]},
            }
        ]
    }
    result = GoatResponseParser().parse(payload)
    assert result.listings
    assert "fixture warning example" in result.listings[0].source_metadata.get("goat_parse_warnings", "")


def test_malformed_items_raises() -> None:
    with pytest.raises(GoatParseError):
        GoatResponseParser().parse(_load("goat_search_malformed.json"))


def test_validate_payload() -> None:
    with pytest.raises(GoatResponseError):
        GoatResponseParser.validate_payload({"items": "bad"})


def test_shipping_unknown_not_zero() -> None:
    result = GoatResponseParser().parse(_load("goat_search_normal.json"))
    listing = result.listings[0]
    assert listing.shipping_unknown is True
    assert listing.shipping_jpy is None


def test_fees_unknown_not_zero() -> None:
    result = GoatResponseParser().parse(_load("goat_search_normal.json"))
    listing = result.listings[0]
    assert listing.source_metadata.get("source_goat_fees_known") is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("New", "new"),
        ("New with defects", "new_with_defects"),
        ("Used", "used"),
        (None, "unknown"),
    ],
)
def test_condition_normalization(raw, expected) -> None:
    condition, _warnings = normalize_goat_condition(raw)
    assert condition == expected
