"""
Product data model.

Represents one product collected from any supported overseas store.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from config.settings import DEFAULT_EXCHANGE_RATE


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _convert_to_jpy(amount: float, currency: str, exchange_rate: float) -> float:
    """
    Convert an amount to JPY using the configured exchange rate.

    Args:
        amount: Source amount.
        currency: ISO currency code.
        exchange_rate: Rate to JPY for non-JPY currencies.

    Returns:
        Amount in JPY.
    """
    if currency.upper() == "JPY":
        return round(amount, 2)
    effective_rate = exchange_rate if exchange_rate > 0 else DEFAULT_EXCHANGE_RATE
    return round(amount * effective_rate, 2)


@dataclass
class Product:
    """Application product model used by scanners and exporters."""

    name: str = ""
    brand: str = ""
    model: str = ""
    sku: str = ""
    category: str = ""
    gender: str = ""

    price: float = 0.0
    original_price: float | None = None
    sale_price: float | None = None
    currency: str = "USD"
    shipping_cost: float = 0.0
    tax_cost: float = 0.0
    fee_cost: float = 0.0
    exchange_rate: float = 0.0
    landed_cost: float = 0.0

    rakuten_price: float | None = None
    yahoo_price: float | None = None
    mercari_price: float | None = None
    ebay_price: float | None = None

    profit: float = 0.0
    roi: float = 0.0
    margin: float = 0.0

    store_name: str = ""
    country: str = ""
    url: str = ""
    image_url: str = ""

    in_stock: bool = True
    scraped_at: datetime = field(default_factory=_utc_now)
    last_updated: datetime = field(default_factory=_utc_now)

    def calculate_landed_cost(self) -> float:
        """
        Compute landed cost in JPY including fees and shipping.

        Returns:
            Total landed cost in JPY.
        """
        rate = self.exchange_rate if self.exchange_rate > 0 else DEFAULT_EXCHANGE_RATE
        base_jpy = _convert_to_jpy(self.price, self.currency, rate)
        fee_jpy = _convert_to_jpy(self.fee_cost, self.currency, rate)
        shipping_jpy = _convert_to_jpy(self.shipping_cost, self.currency, rate)
        tax_jpy = _convert_to_jpy(self.tax_cost, self.currency, rate)
        self.landed_cost = round(base_jpy + fee_jpy + shipping_jpy + tax_jpy, 2)
        self.last_updated = _utc_now()
        return self.landed_cost

    def calculate_profit(self, japanese_price: float | None = None) -> float:
        """
        Calculate expected profit against a Japanese marketplace price.

        Args:
            japanese_price: Override price in JPY. Uses best available JP price when None.

        Returns:
            Expected profit in JPY.
        """
        if self.landed_cost <= 0:
            self.calculate_landed_cost()

        jp_price = japanese_price or self.best_japanese_price()
        if jp_price is None or jp_price <= 0:
            self.profit = 0.0
            self.roi = 0.0
            self.margin = 0.0
            return 0.0

        self.profit = round(jp_price - self.landed_cost, 2)
        self.roi = round((self.profit / self.landed_cost) * 100, 2) if self.landed_cost else 0.0
        self.margin = round((self.profit / jp_price) * 100, 2) if jp_price else 0.0
        self.last_updated = _utc_now()
        return self.profit

    def best_japanese_price(self) -> float | None:
        """
        Return the lowest available Japanese marketplace price.

        Returns:
            Minimum non-null Japanese price or None.
        """
        prices = [
            price
            for price in (
                self.rakuten_price,
                self.yahoo_price,
                self.mercari_price,
                self.ebay_price,
            )
            if price is not None and price > 0
        ]
        return min(prices) if prices else None

    def to_dict(self) -> dict[str, object]:
        """
        Serialize product to a flat dictionary for Excel export.

        Returns:
            Dictionary of product fields.
        """
        return {
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "sku": self.sku,
            "category": self.category,
            "gender": self.gender,
            "price": self.price,
            "original_price": self.original_price,
            "sale_price": self.sale_price,
            "currency": self.currency,
            "shipping_cost": self.shipping_cost,
            "tax_cost": self.tax_cost,
            "fee_cost": self.fee_cost,
            "exchange_rate": self.exchange_rate,
            "landed_cost": self.landed_cost,
            "rakuten_price": self.rakuten_price,
            "yahoo_price": self.yahoo_price,
            "mercari_price": self.mercari_price,
            "ebay_price": self.ebay_price,
            "profit": self.profit,
            "roi": self.roi,
            "margin": self.margin,
            "store_name": self.store_name,
            "country": self.country,
            "url": self.url,
            "image_url": self.image_url,
            "in_stock": self.in_stock,
            "scraped_at": self.scraped_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }
