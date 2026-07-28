"""
Price comparison and profit calculation result model.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from models.product import Product

CALCULATION_SUCCESS = "success"
CALCULATION_INVALID_PRICE = "invalid_price"
CALCULATION_INVALID_RATE = "invalid_rate"
CALCULATION_INVALID_DOMESTIC_PRICE = "invalid_domestic_price"
CALCULATION_UNKNOWN_CURRENCY = "unknown_currency"
CALCULATION_ERROR = "error"


@dataclass
class PriceResult:
    """Profit calculation result for one overseas product."""

    product: Product | None = None
    source_store: str = ""
    source_currency: str = ""
    source_original_price: Decimal | None = None
    source_sale_price: Decimal | None = None
    source_purchase_price: Decimal | None = None
    exchange_rate: Decimal | None = None
    purchase_price_jpy: Decimal | None = None
    international_shipping_jpy: Decimal = Decimal("0")
    customs_duty_jpy: Decimal = Decimal("0")
    import_tax_jpy: Decimal = Decimal("0")
    domestic_shipping_jpy: Decimal = Decimal("0")
    marketplace_fee_jpy: Decimal = Decimal("0")
    other_costs_jpy: Decimal = Decimal("0")
    total_cost_jpy: Decimal = Decimal("0")
    domestic_market: str = ""
    domestic_sale_price_jpy: Decimal | None = None
    profit_jpy: Decimal = Decimal("0")
    profit_margin: Decimal = Decimal("0")
    roi: Decimal = Decimal("0")
    is_profitable: bool = False
    ranking_score: Decimal = Decimal("0")
    calculation_status: str = CALCULATION_SUCCESS
    error_message: str = ""
    marketplace: str = ""
    query: str = ""
    price: float | None = None
    currency: str = "JPY"
    url: str = ""
    title: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return True when calculation completed successfully."""
        return self.calculation_status == CALCULATION_SUCCESS

    def to_dict(self) -> dict[str, object]:
        """
        Serialize result to a flat dictionary for Excel export.

        Returns:
            Dictionary of export fields.
        """
        product = self.product
        return {
            "store_name": self.source_store or (product.store_name if product else ""),
            "brand": product.brand if product else "",
            "name": product.name if product else self.title,
            "sku": product.sku if product else "",
            "url": product.url if product else self.url,
            "image_url": product.image_url if product else "",
            "currency": self.source_currency,
            "original_price": _decimal_to_export(self.source_original_price),
            "sale_price": _decimal_to_export(self.source_sale_price),
            "source_purchase_price": _decimal_to_export(self.source_purchase_price),
            "exchange_rate": _decimal_to_export(self.exchange_rate),
            "purchase_price_jpy": _decimal_to_export(self.purchase_price_jpy),
            "international_shipping_jpy": _decimal_to_export(self.international_shipping_jpy),
            "customs_duty_jpy": _decimal_to_export(self.customs_duty_jpy),
            "import_tax_jpy": _decimal_to_export(self.import_tax_jpy),
            "domestic_shipping_jpy": _decimal_to_export(self.domestic_shipping_jpy),
            "marketplace_fee_jpy": _decimal_to_export(self.marketplace_fee_jpy),
            "other_costs_jpy": _decimal_to_export(self.other_costs_jpy),
            "total_cost_jpy": _decimal_to_export(self.total_cost_jpy),
            "domestic_market": self.domestic_market,
            "domestic_sale_price_jpy": _decimal_to_export(self.domestic_sale_price_jpy),
            "profit_jpy": _decimal_to_export(self.profit_jpy),
            "profit_margin": _decimal_to_export(self.profit_margin),
            "roi": _decimal_to_export(self.roi),
            "is_profitable": self.is_profitable,
            "ranking_score": _decimal_to_export(self.ranking_score),
            "calculation_status": self.calculation_status,
            "error_message": self.error_message,
        }


def _decimal_to_export(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
