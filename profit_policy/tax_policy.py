"""Import tax and customs duty policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from profit_policy.money import round_jpy


@dataclass(frozen=True, slots=True)
class TaxPolicy:
    """Flat-rate customs duty and import tax on the import-side base."""

    customs_duty_rate: Decimal = Decimal("0.10")
    import_tax_rate: Decimal = Decimal("0.10")

    def compute_import_charges(self, customs_base_jpy: Decimal) -> tuple[Decimal, Decimal]:
        """
        Return (customs_duty_jpy, import_tax_jpy) for a customs base amount.

        Preserves the existing sequential duty-then-tax formula.
        """
        customs_duty = round_jpy(customs_base_jpy * self.customs_duty_rate)
        import_tax = round_jpy((customs_base_jpy + customs_duty) * self.import_tax_rate)
        return customs_duty, import_tax
