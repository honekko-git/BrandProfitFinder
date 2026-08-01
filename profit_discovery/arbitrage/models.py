"""Models for used luxury market arbitrage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ArbitrageScore:
    """Weighted arbitrage score derived from profit and sellability signals."""

    profit_difference_score: float
    profit_margin_score: float
    demand_score: float
    turnover_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class ArbitrageOpportunity:
    """One overseas-to-domestic used luxury arbitrage opportunity."""

    product: str
    brand: str
    category: str
    purchase_source: str
    purchase_url: str
    purchase_price: Decimal
    selling_market: str
    selling_url: str
    selling_price: Decimal
    price_difference: Decimal
    estimated_profit: Decimal
    profit_margin: Decimal
    demand_score: float
    turnover_score: float
    arbitrage_score: float
    recommendation_rank: int | None = None
    decision: str = "N/A"
    external_id: str = ""
    market_source: str = ""
    condition: str = ""
    listing_url: str = ""
