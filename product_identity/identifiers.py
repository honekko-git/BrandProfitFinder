"""Structured identifier parsing and validation."""

from __future__ import annotations

from product_identity.enums import IdentifierScope, IdentifierSourceQuality, IdentifierType
from product_identity.models import NormalizedIdentifier
from product_identity.normalization import normalize_code, normalize_gtin_digits


GTIN_LENGTHS = frozenset({8, 12, 13, 14})


def validate_gtin_digits(digits: str | None) -> bool:
    """Return True when digit length is permitted for GTIN family identifiers."""
    if not digits or not digits.isdigit():
        return False
    return len(digits) in GTIN_LENGTHS


def gtin_checksum_valid(digits: str) -> bool:
    """Deterministic GTIN checksum validation."""
    if not digits.isdigit() or len(digits) not in GTIN_LENGTHS:
        return False
    body = digits[:-1]
    check = int(digits[-1])
    total = 0
    reverse = body[::-1]
    for index, char in enumerate(reverse):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    calculated = (10 - (total % 10)) % 10
    return calculated == check


def build_identifier(
    identifier_type: IdentifierType,
    original: object | None,
    *,
    source_field: str,
    source_marketplace: str = "",
    scope: IdentifierScope = IdentifierScope.UNKNOWN,
    source_quality: IdentifierSourceQuality = IdentifierSourceQuality.EXPLICIT,
) -> NormalizedIdentifier | None:
    """Build a normalized identifier or None when absent."""
    if original is None:
        return None
    if isinstance(original, bool):
        return None
    if isinstance(original, int):
        return None
    original_text = str(original).strip()
    if not original_text:
        return None

    if identifier_type in {
        IdentifierType.JAN,
        IdentifierType.EAN,
        IdentifierType.UPC,
        IdentifierType.GTIN,
    }:
        digits = normalize_gtin_digits(original_text)
        if digits is None:
            return NormalizedIdentifier(
                identifier_type=identifier_type,
                original_value=original_text,
                normalized_value=None,
                source_field=source_field,
                source_marketplace=source_marketplace,
                scope=IdentifierScope.GLOBAL,
                source_quality=source_quality,
                is_valid=False,
            )
        is_valid = validate_gtin_digits(digits) and gtin_checksum_valid(digits)
        return NormalizedIdentifier(
            identifier_type=identifier_type,
            original_value=original_text,
            normalized_value=digits if is_valid else None,
            source_field=source_field,
            source_marketplace=source_marketplace,
            scope=IdentifierScope.GLOBAL,
            source_quality=source_quality,
            is_valid=is_valid,
        )

    normalized = normalize_code(original_text)
    if normalized is None:
        return None

    if identifier_type == IdentifierType.SKU:
        scope = IdentifierScope.MARKETPLACE_LOCAL

    return NormalizedIdentifier(
        identifier_type=identifier_type,
        original_value=original_text,
        normalized_value=normalized,
        source_field=source_field,
        source_marketplace=source_marketplace,
        scope=scope,
        source_quality=source_quality,
        is_valid=True,
    )
