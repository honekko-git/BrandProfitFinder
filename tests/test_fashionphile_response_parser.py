"""Tests for Fashionphile response parser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_FASHIONPHILE
from marketplace.fashionphile_exceptions import FashionphileParseError, FashionphileResponseError
from marketplace.fashionphile_response_parser import (
    FashionphileInventoryStatus,
    FashionphileResponseParser,
    FashionphileSaleStatus,
    preprocess_fashionphile_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_normal.json"))
    assert result.valid_count == 1
    assert result.listings[0].marketplace_name == MARKETPLACE_FASHIONPHILE
    assert result.listings[0].used_item_details is not None
    assert result.listings[0].source_metadata.get("source_discount_active") is True


def test_parse_multiple() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_multiple.json"))
    assert len(result.listings) == 3


def test_empty() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_empty.json"))
    assert result.listings == []


def test_missing_fields_partial() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_missing_fields.json"))
    assert len(result.listings) == 1
    assert result.rejected_count >= 1


def test_malformed_top_level() -> None:
    with pytest.raises(FashionphileParseError):
        FashionphileResponseParser().parse(_load("fashionphile_search_malformed.json"))


def test_duplicate_skipped() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_duplicate.json"))
    assert len(result.listings) == 1
    assert result.rejected_count >= 1


def test_bool_price_rejected() -> None:
    payload = {
        "items": [{
            "listing_id": "x",
            "title": "X",
            "price": {"amount": True, "currency": "JPY"},
            "url": "https://example.invalid/x",
            "sale_status": "ACTIVE",
            "inventory": {"status": "IN_STOCK", "quantity": 1},
        }]
    }
    result = FashionphileResponseParser().parse(payload)
    assert result.listings == []


def test_negative_price_rejected() -> None:
    payload = {
        "items": [{
            "listing_id": "x",
            "title": "X",
            "price": {"amount": -100, "currency": "JPY"},
            "url": "https://example.invalid/x",
            "sale_status": "ACTIVE",
            "inventory": {"status": "IN_STOCK", "quantity": 1},
        }]
    }
    result = FashionphileResponseParser().parse(payload)
    assert result.listings == []


def test_non_jpy_excluded_by_default() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_non_jpy.json"))
    assert result.listings == []


def test_non_jpy_allowed() -> None:
    result = FashionphileResponseParser().parse(
        _load("fashionphile_search_non_jpy.json"),
        allow_unknown_currency=True,
    )
    assert len(result.listings) == 1
    assert result.listings[0].currency == "USD"


def test_shipping_unknown() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_shipping_unknown.json"))
    assert result.listings[0].shipping_unknown is True
    assert result.listings[0].shipping_jpy is None


def test_shipping_known() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_multiple.json"))
    assert result.listings[0].shipping_jpy == Decimal("0")
    assert result.listings[0].shipping_unknown is False


def test_original_price_metadata() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_normal.json"))
    assert result.listings[0].source_metadata.get("source_original_price") == 1050000.0


def test_invalid_original_price_warning() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_original_price_invalid.json"))
    assert len(result.listings) == 1
    assert any("original_price" in w for w in result.warnings)


def test_discount_inconsistent_warning() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_discount_inconsistent.json"))
    assert len(result.listings) == 1
    assert any("inconsistent" in w for w in result.warnings)


def test_inventory_invalid_quantity() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_inventory_invalid.json"))
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata.get("source_inventory_quantity") is None


def test_sold_excluded_by_default() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_sold.json"))
    assert result.listings == []


def test_sold_included() -> None:
    result = FashionphileResponseParser().parse(
        _load("fashionphile_search_sold.json"),
        include_sold=True,
    )
    assert len(result.listings) == 1


def test_reserved_excluded_by_default() -> None:
    result = FashionphileResponseParser().parse(_load("fashionphile_search_reserved.json"))
    assert result.listings == []


def test_discounted_only_filter() -> None:
    result = FashionphileResponseParser().parse(
        _load("fashionphile_search_discounted.json"),
        include_discounted_only=True,
    )
    assert len(result.listings) == 1
    assert result.listings[0].listing_id == "fp-disc"


def test_validate_payload() -> None:
    with pytest.raises(FashionphileResponseError):
        FashionphileResponseParser.validate_payload({"items": "bad"})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Giftable", "giftable"),
        ("Shows Wear", "shows wear"),
        ("Final Sale", ""),
        ("Vintage", "vintage"),
        ("As Is", "as is"),
        ("For Parts", "for parts"),
    ],
)
def test_preprocess_condition(raw: str, expected: str) -> None:
    text, warnings = preprocess_fashionphile_condition(raw)
    assert text == expected
    if raw == "Final Sale":
        assert any("return policy" in w for w in warnings)


def test_sale_status_enum() -> None:
    assert FashionphileSaleStatus.from_value("active") == FashionphileSaleStatus.ACTIVE


def test_inventory_status_enum() -> None:
    assert FashionphileInventoryStatus.from_value("in_stock") == FashionphileInventoryStatus.IN_STOCK
