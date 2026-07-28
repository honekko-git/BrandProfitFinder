"""
Amazon price normalization helpers.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_JPY_PRICE_PATTERN = re.compile(r"[^\d\-]")


def parse_jpy_price(value: Any) -> Decimal | None:
    """
    Parse a JPY price value into a positive Decimal.

    Supports integer, numeric string, comma-separated, and yen-symbol formats.

    Args:
        value: Raw price value.

    Returns:
        Positive JPY amount or None when invalid.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return _validate_amount(Decimal(str(value)))

    if isinstance(value, float):
        if not value.is_integer():
            return None
        return _validate_amount(Decimal(str(int(value))))

    if isinstance(value, Decimal):
        return _validate_amount(value)

    text = str(value).strip()
    if not text:
        return None

    cleaned = _JPY_PRICE_PATTERN.sub("", text)
    if not cleaned or cleaned == "-":
        return None

    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None

    return _validate_amount(amount)


def _validate_amount(amount: Decimal) -> Decimal | None:
    if amount <= 0:
        return None
    return amount.quantize(Decimal("1"))
