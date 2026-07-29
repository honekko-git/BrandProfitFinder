"""
Profit calculation configuration.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from profit_policy.marketplace_configuration import MarketplaceConfiguration


@dataclass
class ProfitConfig:
    """Configurable fees and rates for profit calculation."""

    international_shipping_jpy: Decimal = Decimal("3000")
    customs_duty_rate: Decimal = Decimal("0.10")
    import_tax_rate: Decimal = Decimal("0.10")
    domestic_shipping_jpy: Decimal = Decimal("1000")
    marketplace_fee_rate: Decimal = Decimal("0.10")
    other_costs_jpy: Decimal = Decimal("0")
    exchange_rates: dict[str, Decimal] = field(default_factory=dict)
    ranking_score_profit_margin_weight: Decimal = Decimal("0.4")
    ranking_score_roi_weight: Decimal = Decimal("0.4")
    ranking_score_profit_jpy_weight: Decimal = Decimal("0.2")
    ranking_score_identity_confidence_weight: Decimal = Decimal("0")
    ranking_score_import_cost_weight: Decimal = Decimal("0")
    ranking_score_marketplace_confidence_weight: Decimal = Decimal("0")
    marketplace_configurations: dict[str, MarketplaceConfiguration] = field(default_factory=dict)

    def resolve_marketplace(self, domestic_market: str) -> MarketplaceConfiguration:
        """Return marketplace configuration, falling back to legacy ProfitConfig fields."""
        configured = self.marketplace_configurations.get(domestic_market)
        if configured is not None:
            return configured
        return MarketplaceConfiguration.from_profit_config(domestic_market, self)
