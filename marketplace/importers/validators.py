"""Validation helpers for imported market listing rows."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

REQUIRED_FIELDS: tuple[str, ...] = ("title", "brand", "price", "market_name")

CSV_FIELD_NAMES: tuple[str, ...] = (
    "title",
    "brand",
    "category",
    "condition",
    "price",
    "currency",
    "market_name",
    "url",
)


def normalize_row(raw_row: dict[str, str]) -> dict[str, str]:
    """Normalize CSV/manual row keys to canonical field names."""
    normalized: dict[str, str] = {}
    for key, value in raw_row.items():
        normalized[key.strip().lower()] = str(value).strip()
    return normalized


def validate_row(raw_row: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate one import row. Invalid rows should be skipped."""
    row = normalize_row(raw_row)
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if not row.get(field, "").strip():
            errors.append(f"missing required field: {field}")

    price_raw = row.get("price", "")
    if price_raw:
        try:
            parsed = Decimal(price_raw.replace(",", ""))
            if parsed <= 0:
                errors.append("price must be greater than zero")
        except InvalidOperation:
            errors.append(f"invalid price: {price_raw}")

    return len(errors) == 0, errors


def is_header_row(values: list[str]) -> bool:
    """Return True when a CSV row looks like a header line."""
    lowered = {value.strip().lower() for value in values if value.strip()}
    return "title" in lowered and "brand" in lowered and "market_name" in lowered
