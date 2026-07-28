"""Tests for Vestiaire response parser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_VESTIAIRE
from marketplace.vestiaire_exceptions import VestiaireParseError, VestiaireResponseError
from marketplace.vestiaire_response_parser import (
    VestiaireResponseParser,
    VestiaireSaleStatus,
    preprocess_vestiaire_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_normal.json"))
    assert len(result.listings) == 1
    assert result.listings[0].marketplace_name == MARKETPLACE_VESTIAIRE
    assert result.listings[0].used_item_details is not None


def test_parse_multiple() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_multiple.json"))
    assert len(result.listings) == 3


def test_empty() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_empty.json"))
    assert result.listings == []


def test_missing_fields_partial() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_missing_fields.json"))
    assert len(result.listings) == 1
    assert result.rejected_count >= 1


def test_malformed_top_level() -> None:
    with pytest.raises(VestiaireParseError):
        VestiaireResponseParser().parse(_load("vestiaire_search_malformed.json"))


def test_duplicate_skipped() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_duplicate.json"))
    assert len(result.listings) == 1
    assert result.rejected_count >= 1


def test_bool_price_rejected() -> None:
    payload = {"items": [{"listing_id": "x", "title": "X", "price": {"amount": True, "currency": "JPY"}, "url": "https://example.invalid/x", "sale_status": "ACTIVE"}]}
    result = VestiaireResponseParser().parse(payload)
    assert result.listings == []


def test_negative_price_rejected() -> None:
    payload = {"items": [{"listing_id": "x", "title": "X", "price": {"amount": -100, "currency": "JPY"}, "url": "https://example.invalid/x", "sale_status": "ACTIVE"}]}
    result = VestiaireResponseParser().parse(payload)
    assert result.listings == []


def test_non_jpy_excluded_by_default() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_non_jpy.json"))
    assert result.listings == []


def test_non_jpy_allowed() -> None:
    result = VestiaireResponseParser().parse(
        _load("vestiaire_search_non_jpy.json"),
        allow_unknown_currency=True,
    )
    assert len(result.listings) == 1
    assert result.listings[0].currency == "USD"


def test_shipping_unknown() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_shipping_unknown.json"))
    assert result.listings[0].shipping_unknown is True
    assert result.listings[0].shipping_jpy is None


def test_shipping_known() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_normal.json"))
    assert result.listings[0].shipping_jpy == Decimal("3500")
    assert result.listings[0].shipping_unknown is False


def test_sold_excluded_by_default() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_sold.json"))
    assert result.listings == []


def test_sold_included() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_sold.json"), include_sold=True)
    assert len(result.listings) == 1
    assert result.listings[0].source_metadata["source_sale_status"] == "SOLD"


def test_inactive_excluded() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_inactive.json"))
    assert result.listings == []


def test_inactive_included() -> None:
    result = VestiaireResponseParser().parse(
        _load("vestiaire_search_inactive.json"),
        include_inactive=True,
    )
    assert len(result.listings) == 1


@pytest.mark.parametrize(
    "raw,expected_substr",
    [
        ("Never worn", "never worn"),
        ("Never used", "never used"),
        ("Very good condition", "very good"),
        ("Good condition", "good"),
        ("Fair condition", "fair"),
        ("Vintage", "vintage"),
        ("Pre-owned", "pre-owned"),
        ("Damaged", "damaged"),
        ("For parts", "for parts"),
    ],
)
def test_preprocess_condition(raw: str, expected_substr: str) -> None:
    assert expected_substr in preprocess_vestiaire_condition(raw)


def test_vintage_not_good() -> None:
    result = VestiaireResponseParser().parse(_load("vestiaire_search_unknown_condition.json"))
    details = result.listings[0].used_item_details
    assert details is not None
    assert details.condition.value == "USED_GENERIC"


def test_validate_payload_error() -> None:
    with pytest.raises(VestiaireResponseError):
        VestiaireResponseParser.validate_payload({"items": "bad"})


def test_sale_status_enum() -> None:
    assert VestiaireSaleStatus.from_value("ACTIVE") == VestiaireSaleStatus.ACTIVE
    assert VestiaireSaleStatus.from_value("unknown-status") == VestiaireSaleStatus.UNKNOWN
