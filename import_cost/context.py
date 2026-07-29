"""Import cost calculation inputs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ImportCostContext:
    """Encapsulates all inputs required for import cost calculation."""

    source_purchase: Decimal
    currency: str
    exchange_rate: Decimal
    domestic_sale_jpy: Decimal
    domestic_market: str = "manual"
    payment_fee_jpy: Decimal = Decimal("0")
    insurance_jpy: Decimal = Decimal("0")
    packaging_jpy: Decimal = Decimal("0")

    @classmethod
    def create(
        cls,
        *,
        source_purchase: Decimal,
        currency: str,
        exchange_rate: Decimal,
        domestic_sale_jpy: Decimal,
        domestic_market: str = "manual",
        payment_fee_jpy: Decimal | None = None,
        insurance_jpy: Decimal | None = None,
        packaging_jpy: Decimal | None = None,
    ) -> ImportCostContext:
        """Build a validated import cost context."""
        return cls(
            source_purchase=source_purchase,
            currency=currency.strip().upper() or "USD",
            exchange_rate=exchange_rate,
            domestic_sale_jpy=domestic_sale_jpy,
            domestic_market=domestic_market,
            payment_fee_jpy=payment_fee_jpy or Decimal("0"),
            insurance_jpy=insurance_jpy or Decimal("0"),
            packaging_jpy=packaging_jpy or Decimal("0"),
        )

    @property
    def optional_costs_jpy(self) -> Decimal:
        """Return explicitly provided ancillary import costs."""
        return self.payment_fee_jpy + self.insurance_jpy + self.packaging_jpy
