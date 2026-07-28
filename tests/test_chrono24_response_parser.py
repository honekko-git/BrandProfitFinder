"""Tests for Chrono24 response parser."""

import json
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_CHRONO24
from marketplace.chrono24_exceptions import Chrono24ParseError, Chrono24ResponseError
from marketplace.chrono24_response_parser import (
    Chrono24ResponseParser,
    preprocess_chrono24_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_normal() -> None:
    result = Chrono24ResponseParser().parse(_load("chrono24_search_normal.json"))
    assert result.valid_count == 1
    listing = result.listings[0]
    assert listing.marketplace_name == MARKETPLACE_CHRONO24
    assert listing.source_metadata.get("source_reference_number") == "126610LN"
    assert listing.source_metadata.get("source_case_diameter_mm") == 41.0


def test_parse_multiple() -> None:
    assert len(Chrono24ResponseParser().parse(_load("chrono24_search_multiple.json")).listings) == 3


def test_empty() -> None:
    assert Chrono24ResponseParser().parse(_load("chrono24_search_empty.json")).listings == []


def test_malformed_top_level() -> None:
    with pytest.raises(Chrono24ParseError):
        Chrono24ResponseParser().parse(_load("chrono24_search_malformed.json"))


def test_watch_details_invalid() -> None:
    result = Chrono24ResponseParser().parse(_load("chrono24_search_watch_details_invalid.json"))
    assert len(result.listings) == 1
    assert any("case_diameter" in w or "production_year" in w or "movement" in w for w in result.warnings)


def test_trusted_seller_filter() -> None:
    assert Chrono24ResponseParser().parse(_load("chrono24_search_untrusted_seller.json")).listings
    filtered = Chrono24ResponseParser().parse(
        _load("chrono24_search_untrusted_seller.json"),
        require_trusted_seller=True,
    )
    assert filtered.listings == []


def test_private_seller_excluded() -> None:
    result = Chrono24ResponseParser().parse(
        _load("chrono24_search_private_seller.json"),
        include_private_sellers=False,
    )
    assert result.listings == []


def test_negotiable_only() -> None:
    payload = _load("chrono24_search_normal.json")
    payload["items"][0]["negotiation"] = {"enabled": False}
    assert Chrono24ResponseParser().parse(payload, include_negotiable_only=True).listings == []


def test_modified_condition() -> None:
    listing = Chrono24ResponseParser().parse(_load("chrono24_search_modified.json")).listings[0]
    assert listing.used_item_details is not None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Unworn", "unworn"),
        ("Modified", "modified"),
        ("Customized", "customized"),
        ("Very Good", "very good"),
    ],
)
def test_preprocess_condition(raw: str, expected: str) -> None:
    text, _ = preprocess_chrono24_condition(raw)
    assert text == expected


def test_validate_payload() -> None:
    with pytest.raises(Chrono24ResponseError):
        Chrono24ResponseParser.validate_payload({"items": "bad"})
