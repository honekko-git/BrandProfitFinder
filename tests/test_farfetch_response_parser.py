"""Tests for Farfetch response parser."""

import json
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_FARFETCH
from marketplace.farfetch_exceptions import FarfetchParseError, FarfetchResponseError
from marketplace.farfetch_response_parser import (
    FarfetchResponseParser,
    preprocess_farfetch_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = FarfetchResponseParser().parse(_load("farfetch_search_normal.json"))
    assert result.valid_count == 3
    listing = result.listings[0]
    assert listing.marketplace_name == MARKETPLACE_FARFETCH
    assert listing.source_metadata.get("source_style_code") == "447632-DTD1T-1000"
    assert listing.source_metadata.get("source_product_id") == "farfetch-product-demo-001"


def test_parse_multiple() -> None:
    assert len(FarfetchResponseParser().parse(_load("farfetch_search_multiple.json")).listings) == 3


def test_empty() -> None:
    assert FarfetchResponseParser().parse(_load("farfetch_search_empty.json")).listings == []


def test_malformed_top_level() -> None:
    with pytest.raises(FarfetchParseError):
        FarfetchResponseParser().parse(_load("farfetch_search_malformed.json"))


def test_missing_fields_rejected() -> None:
    result = FarfetchResponseParser().parse(_load("farfetch_search_missing_fields.json"))
    assert result.listings == []
    assert result.rejected_count >= 1


def test_duplicate_listing_id() -> None:
    result = FarfetchResponseParser().parse(_load("farfetch_search_duplicate.json"))
    assert len(result.listings) == 1


def test_non_jpy_excluded_by_default() -> None:
    result = FarfetchResponseParser().parse(_load("farfetch_search_non_jpy.json"))
    assert result.listings == []


def test_non_jpy_allowed() -> None:
    result = FarfetchResponseParser().parse(
        _load("farfetch_search_non_jpy.json"),
        allow_unknown_currency=True,
    )
    assert len(result.listings) == 1


def test_shipping_unknown_kept() -> None:
    listing = FarfetchResponseParser().parse(_load("farfetch_search_shipping_unknown.json")).listings[0]
    assert listing.shipping_unknown is True
    assert listing.shipping_jpy is None


def test_require_known_shipping_filter() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_shipping_unknown.json"),
        require_known_shipping=True,
    ).listings == []


def test_duties_unknown_metadata() -> None:
    meta = FarfetchResponseParser().parse(_load("farfetch_search_duties_unknown.json")).listings[0].source_metadata
    assert meta.get("source_duties_known") is not True


def test_duties_included() -> None:
    meta = FarfetchResponseParser().parse(_load("farfetch_search_duties_included.json")).listings[0].source_metadata
    assert meta.get("source_duties_included") is True


def test_sold_excluded_by_default() -> None:
    assert FarfetchResponseParser().parse(_load("farfetch_search_sold.json")).listings == []


def test_sold_included() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_sold.json"),
        include_sold=True,
    ).listings


def test_discounted_only_filter() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_full_price.json"),
        include_discounted_only=True,
    ).listings == []


def test_full_price_only_filter() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_discounted.json"),
        include_full_price_only=True,
    ).listings == []


def test_low_stock_filter() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_low_stock.json"),
        include_low_stock=False,
    ).listings == []


def test_final_sale_filter() -> None:
    assert FarfetchResponseParser().parse(_load("farfetch_search_final_sale.json")).listings == []


def test_partner_boutique_filter() -> None:
    assert FarfetchResponseParser().parse(
        _load("farfetch_search_partner_boutique.json"),
        include_partner_boutiques=False,
    ).listings == []


def test_variant_counts() -> None:
    meta = FarfetchResponseParser().parse(_load("farfetch_search_variant_multiple.json")).listings[0].source_metadata
    assert meta.get("source_variant_count") == 2
    assert meta.get("source_available_variant_count") == 2


def test_product_id_missing_still_valid() -> None:
    assert FarfetchResponseParser().parse(_load("farfetch_search_product_id_missing.json")).listings


def test_style_code_missing_still_valid() -> None:
    assert FarfetchResponseParser().parse(_load("farfetch_search_style_code_missing.json")).listings


def test_discount_inconsistent_warning() -> None:
    result = FarfetchResponseParser().parse(_load("farfetch_search_discount_inconsistent.json"))
    assert result.listings
    assert any("inconsistent" in w for w in result.warnings)


def test_validate_payload() -> None:
    with pytest.raises(FarfetchResponseError):
        FarfetchResponseParser.validate_payload({"items": "bad"})


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ("New Season", "season"),
        ("Display Item", "display"),
        ("Shop Worn", "shop worn"),
        ("Pre-Owned", "pre-owned"),
    ],
)
def test_preprocess_condition(raw: str, fragment: str) -> None:
    text, warnings = preprocess_farfetch_condition(raw)
    assert fragment in text or any(fragment in w.lower() for w in warnings)
