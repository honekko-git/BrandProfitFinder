"""Marketplace-specific profit configuration bundle."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from profit_policy.currency_policy import CurrencyPolicy
from profit_policy.fee_policy import FeePolicy
from profit_policy.shipping_policy import ShippingPolicy
from profit_policy.tax_policy import TaxPolicy

if TYPE_CHECKING:
    from price_compare.profit_config import ProfitConfig


@dataclass(frozen=True, slots=True)
class MarketplaceConfiguration:
    """Marketplace-specific fee, shipping, tax, and currency settings."""

    marketplace_id: str
    fee_policy: FeePolicy
    shipping_policy: ShippingPolicy
    tax_policy: TaxPolicy
    currency_policy: CurrencyPolicy
    other_costs_jpy: Decimal = Decimal("0")

    @classmethod
    def from_profit_config(cls, marketplace_id: str, config: ProfitConfig) -> MarketplaceConfiguration:
        """Build marketplace configuration from legacy ProfitConfig fields."""
        return cls(
            marketplace_id=marketplace_id,
            fee_policy=FeePolicy(fee_rate=config.marketplace_fee_rate),
            shipping_policy=ShippingPolicy(
                international_shipping_jpy=config.international_shipping_jpy,
                domestic_shipping_jpy=config.domestic_shipping_jpy,
            ),
            tax_policy=TaxPolicy(
                customs_duty_rate=config.customs_duty_rate,
                import_tax_rate=config.import_tax_rate,
            ),
            currency_policy=CurrencyPolicy(exchange_rates=dict(config.exchange_rates)),
            other_costs_jpy=config.other_costs_jpy,
        )

    @classmethod
    def default(cls, marketplace_id: str = "manual") -> MarketplaceConfiguration:
        """Return default marketplace configuration."""
        from price_compare.profit_config import ProfitConfig

        return cls.from_profit_config(marketplace_id, ProfitConfig())
