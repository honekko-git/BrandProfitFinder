"""Shipping cost policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ShippingPolicy:
    """Flat import-side and domestic outbound shipping costs."""

    international_shipping_jpy: Decimal = Decimal("3000")
    domestic_shipping_jpy: Decimal = Decimal("1000")

    def international_cost(self) -> Decimal:
        """Return configured international shipping cost in JPY."""
        return self.international_shipping_jpy

    def domestic_cost(self) -> Decimal:
        """Return configured domestic shipping cost in JPY."""
        return self.domestic_shipping_jpy
