"""Tests for structured identifier handling."""

from product_identity.enums import IdentifierType
from product_identity.identifiers import build_identifier, gtin_checksum_valid, validate_gtin_digits


def test_valid_gtin_checksum() -> None:
    assert gtin_checksum_valid("4006381333931") is True
    assert gtin_checksum_valid("123") is False


def test_build_identifier_malformed_jan() -> None:
    item = build_identifier(IdentifierType.JAN, "123", source_field="jan")
    assert item is not None
    assert item.is_valid is False
    assert item.normalized_value is None


def test_build_identifier_valid_jan() -> None:
    item = build_identifier(IdentifierType.JAN, "4006381333931", source_field="jan")
    assert item is not None
    assert item.is_valid is True
    assert item.normalized_value == "4006381333931"


def test_build_identifier_rejects_boolean() -> None:
    assert build_identifier(IdentifierType.JAN, True, source_field="jan") is None


def test_build_identifier_rejects_integer() -> None:
    assert build_identifier(IdentifierType.JAN, 4006381333931, source_field="jan") is None
