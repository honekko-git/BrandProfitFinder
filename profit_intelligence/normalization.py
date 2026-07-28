"""
Safe normalization helpers for profit intelligence scoring.
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any


def dedupe_preserve_order(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def piecewise_linear_score(value: float, thresholds: tuple[tuple[float, float], ...]) -> float:
    """Map a numeric value to 0-100 using piecewise linear interpolation."""
    if not thresholds:
        return 0.0
    if value <= thresholds[0][0]:
        return thresholds[0][1]
    for index in range(1, len(thresholds)):
        prev_x, prev_y = thresholds[index - 1]
        curr_x, curr_y = thresholds[index]
        if value <= curr_x:
            if curr_x == prev_x:
                return curr_y
            ratio = (value - prev_x) / (curr_x - prev_x)
            return clamp_score(prev_y + ratio * (curr_y - prev_y))
    return thresholds[-1][1]


def normalize_optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return None
        return parsed if parsed.is_finite() else None
    return None


def normalize_optional_int(value: Any, *, allow_zero: bool = True) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value < 0:
            return None
        if value == 0 and not allow_zero:
            return None
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        iv = int(value)
        if iv < 0:
            return None
        return iv
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            return None
        iv = int(value)
        if iv < 0:
            return None
        return iv
    return None


def normalize_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        fv = float(value)
        return fv if math.isfinite(fv) else None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            fv = float(text)
        except ValueError:
            return None
        return fv if math.isfinite(fv) else None
    return None


def decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
