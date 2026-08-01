"""Models for profit validation discovery."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TIER_S_BRANDS: tuple[str, ...] = (
    "Chanel",
    "Louis Vuitton",
    "Hermes",
    "Miu Miu",
)

PRIORITY_CATEGORIES: tuple[str, ...] = (
    "Wallet",
    "Mini Bag",
    "Shoulder Bag",
)


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Configuration for profit validation discovery."""

    brands: tuple[str, ...] = TIER_S_BRANDS
    categories: tuple[str, ...] = PRIORITY_CATEGORIES
    minimum_profit_jpy: Decimal = Decimal("10000")
    minimum_demand_score: float = 60.0

    def is_allowed_brand(self, brand: str) -> bool:
        normalized = brand.strip().lower()
        return normalized in {item.lower() for item in self.brands}

    def is_allowed_category(self, category: str) -> bool:
        normalized = category.strip().lower()
        allowed = {item.lower() for item in self.categories}
        return normalized in allowed or any(token in normalized for token in allowed)


@dataclass(frozen=True, slots=True)
class ValidationScore:
    """Weighted validation score derived from profit and sellability signals."""

    profit_score: float
    margin_score: float
    demand_score: float
    turnover_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class ValidationOpportunity:
    """One overseas-to-domestic profit validation candidate."""

    product: str
    brand: str
    category: str
    purchase_source: str
    purchase_price: Decimal
    purchase_url: str
    domestic_market: str
    domestic_price: Decimal
    domestic_url: str
    estimated_profit: Decimal
    profit_margin: Decimal
    demand_score: float
    turnover_score: float
    validation_score: float
    decision: str
    external_id: str = ""
    recommendation_rank: int | None = None
