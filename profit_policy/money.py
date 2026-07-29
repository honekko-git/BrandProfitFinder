"""Shared monetary rounding helpers for profit and import cost policies.

Example::

    from decimal import Decimal
    from profit_policy.money import round_jpy

    amount = round_jpy(Decimal("1234.6"))  # Decimal("1235")
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def round_jpy(amount: Decimal) -> Decimal:
    """Round a JPY amount to the nearest whole yen."""
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
