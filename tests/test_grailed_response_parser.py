"""Tests for Grailed response parser."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_GRAILED
from marketplace.grailed_exceptions import GrailedParseError, GrailedResponseError
from marketplace.grailed_response_parser import (
    GrailedResponseParser,
    preprocess_grailed_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_normal.json"))
    assert result.valid_count == 1
    listing = result.listings[0]
    assert listing.marketplace_name == MARKETPLACE_GRAILED
    assert listing.source_metadata.get("source_offer_enabled") is True
    assert listing.source_metadata.get("source_seller_transactions") == 124


def test_parse_multiple() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_multiple.json"))
    assert len(result.listings) == 3


def test_empty() -> None:
    assert GrailedResponseParser().parse(_load("grailed_search_empty.json")).listings == []


def test_missing_fields_partial() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_missing_fields.json"))
    assert len(result.listings) == 1


def test_malformed_top_level() -> None:
    with pytest.raises(GrailedParseError):
        GrailedResponseParser().parse(_load("grailed_search_malformed.json"))


def test_duplicate_listing_id() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_duplicate.json"))
    assert len(result.listings) == 1
    assert result.rejected_count >= 1


def test_shipping_unknown() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_shipping_unknown.json"))
    assert result.listings[0].shipping_unknown is True


def test_non_jpy_rejected_by_default() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_non_jpy.json"))
    assert result.listings == []


def test_non_jpy_allowed() -> None:
    result = GrailedResponseParser().parse(
        _load("grailed_search_non_jpy.json"),
        allow_unknown_currency=True,
    )
    assert len(result.listings) == 1


def test_discount_inconsistent() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_discount_inconsistent.json"))
    assert any("inconsistent" in w for w in result.warnings)


def test_original_price_below_current() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_original_price_invalid.json"))
    assert any("original_price" in w for w in result.warnings)


def test_sold_excluded() -> None:
    assert GrailedResponseParser().parse(_load("grailed_search_sold.json")).listings == []


def test_sold_included() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_sold.json"), include_sold=True)
    assert len(result.listings) == 1


def test_offer_enabled_only_filter() -> None:
    payload = _load("grailed_search_normal.json")
    payload["items"][0]["offer"] = {"enabled": False, "minimum_offer": None, "currency": "JPY"}
    result = GrailedResponseParser().parse(payload, include_offer_enabled_only=True)
    assert result.listings == []


def test_discounted_only_filter() -> None:
    payload = _load("grailed_search_normal.json")
    payload["items"][0]["discount"] = {"active": False}
    result = GrailedResponseParser().parse(payload, include_discounted_only=True)
    assert result.listings == []


def test_require_verified_seller() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_seller_unverified.json"))
    assert len(result.listings) == 1
    result_filtered = GrailedResponseParser().parse(
        _load("grailed_search_seller_unverified.json"),
        require_verified_seller=True,
    )
    assert result_filtered.listings == []


def test_invalid_seller_warnings() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_seller_invalid.json"))
    assert len(result.listings) == 1
    assert result.rejected_count == 0


def test_offer_invalid_warning() -> None:
    result = GrailedResponseParser().parse(_load("grailed_search_offer_invalid.json"))
    assert len(result.listings) == 1
    assert any("minimum_offer" in w for w in result.warnings)


def test_used_item_details() -> None:
    listing = GrailedResponseParser().parse(_load("grailed_search_normal.json")).listings[0]
    details = listing.used_item_details
    assert details is not None
    assert details.seller_details.seller_type.value == "PRIVATE_SELLER"
    assert details.condition_raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gently Used", "gently used"),
        ("New / Never Worn", "never worn"),
        ("New with Tags", "new with tags"),
        ("Distressed", "distressed"),
        ("For Parts", "for parts"),
    ],
)
def test_preprocess_condition(raw: str, expected: str) -> None:
    text, _ = preprocess_grailed_condition(raw)
    assert text == expected


def test_validate_payload() -> None:
    with pytest.raises(GrailedResponseError):
        GrailedResponseParser.validate_payload({"items": "bad"})


def test_inventory_invalid_quantity() -> None:
    listing = GrailedResponseParser().parse(_load("grailed_search_inventory_invalid.json")).listings[0]
    assert listing.source_metadata.get("source_inventory_quantity") is None
