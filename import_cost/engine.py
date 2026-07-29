"""Import cost calculation engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from import_cost.context import ImportCostContext
from profit_policy.marketplace_configuration import MarketplaceConfiguration
from profit_policy.money import round_jpy


@dataclass(frozen=True, slots=True)
class ImportCostBreakdown:
    """Computed import and selling cost components."""

    purchase_cost_jpy: Decimal
    international_shipping_jpy: Decimal
    domestic_shipping_jpy: Decimal
    customs_duty_jpy: Decimal
    import_tax_jpy: Decimal
    marketplace_fee_jpy: Decimal
    payment_fee_jpy: Decimal
    insurance_jpy: Decimal
    packaging_jpy: Decimal
    other_costs_jpy: Decimal
    total_cost_jpy: Decimal

    @property
    def reported_other_costs_jpy(self) -> Decimal:
        """Return legacy other_costs field including optional ancillary costs."""
        return self.other_costs_jpy + self.payment_fee_jpy + self.insurance_jpy + self.packaging_jpy


class ImportCostEngine:
    """Calculate import-side and marketplace selling costs from policy inputs."""

    def calculate(
        self,
        context: ImportCostContext,
        marketplace_config: MarketplaceConfiguration,
    ) -> ImportCostBreakdown:
        """
        Compute import cost breakdown for one product sale scenario.

        Does not mutate context or marketplace configuration.
        """
        shipping_policy = marketplace_config.shipping_policy
        tax_policy = marketplace_config.tax_policy
        fee_policy = marketplace_config.fee_policy

        purchase_cost_jpy = _convert_to_jpy(
            context.source_purchase,
            context.currency,
            context.exchange_rate,
        )
        international_shipping_jpy = shipping_policy.international_cost()
        customs_base = purchase_cost_jpy + international_shipping_jpy
        customs_duty_jpy, import_tax_jpy = tax_policy.compute_import_charges(customs_base)
        domestic_shipping_jpy = shipping_policy.domestic_cost()
        marketplace_fee_jpy = fee_policy.compute_fee(context.domestic_sale_jpy)
        payment_fee_jpy = round_jpy(context.payment_fee_jpy)
        insurance_jpy = round_jpy(context.insurance_jpy)
        packaging_jpy = round_jpy(context.packaging_jpy)
        other_costs_jpy = marketplace_config.other_costs_jpy

        total_cost_jpy = (
            purchase_cost_jpy
            + international_shipping_jpy
            + customs_duty_jpy
            + import_tax_jpy
            + domestic_shipping_jpy
            + other_costs_jpy
            + payment_fee_jpy
            + insurance_jpy
            + packaging_jpy
        )

        return ImportCostBreakdown(
            purchase_cost_jpy=purchase_cost_jpy,
            international_shipping_jpy=international_shipping_jpy,
            domestic_shipping_jpy=domestic_shipping_jpy,
            customs_duty_jpy=customs_duty_jpy,
            import_tax_jpy=import_tax_jpy,
            marketplace_fee_jpy=marketplace_fee_jpy,
            payment_fee_jpy=payment_fee_jpy,
            insurance_jpy=insurance_jpy,
            packaging_jpy=packaging_jpy,
            other_costs_jpy=other_costs_jpy,
            total_cost_jpy=total_cost_jpy,
        )


def _convert_to_jpy(amount: Decimal, currency: str, exchange_rate: Decimal) -> Decimal:
    if currency == "JPY":
        return round_jpy(amount)
    return round_jpy(amount * exchange_rate)
