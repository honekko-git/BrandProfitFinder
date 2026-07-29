"""Marketplace fee policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from profit_policy.money import round_jpy


@dataclass(frozen=True, slots=True)
class FeePolicy:
    """Compute marketplace selling fees from domestic sale price."""

    fee_rate: Decimal = Decimal("0.10")

    def compute_fee(self, domestic_sale_jpy: Decimal) -> Decimal:
        """Return marketplace fee in JPY using the configured flat rate."""
        return round_jpy(domestic_sale_jpy * self.fee_rate)
