"""Models for single-route real profit verification."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DataStatus(StrEnum):
    """Truth label for data origin in real profit verification."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    IMPORT = "IMPORT"
    MIXED = "MIXED"
    UNAVAILABLE = "UNAVAILABLE"


REAL_ROUTE_BRANDS: tuple[str, ...] = (
    "Chanel",
    "Louis Vuitton",
)

REAL_ROUTE_CATEGORY = "Wallet"


@dataclass(frozen=True, slots=True)
class EndpointStatus:
    """Configuration status for one external data endpoint."""

    name: str
    configured: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DomesticSoldSummary:
    """Domestic sold-price summary for one keyword."""

    market_name: str
    sample_count: int
    average_price_jpy: Decimal
    median_price_jpy: Decimal
    listing_url: str
    actual_source: str
    fallback_used: bool
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class CostBreakdownDisplay:
    """Human-readable cost breakdown for browser display."""

    purchase_price: str
    exchange_rate: str
    estimated_shipping: str
    estimated_import_cost: str
    domestic_selling_estimate: str
    estimated_profit: str


@dataclass(frozen=True, slots=True)
class RealProfitVerificationResult:
    """One real profit verification row for browser display."""

    product: str
    brand: str
    category: str
    purchase_source: str
    purchase_url: str
    purchase_price: Decimal
    purchase_currency: str
    purchase_price_jpy_estimate: Decimal
    exchange_rate_display: str
    cost_breakdown: CostBreakdownDisplay
    domestic_source: str
    domestic_sold_samples: int
    domestic_average_jpy: Decimal
    domestic_median_jpy: Decimal
    domestic_url: str
    estimated_profit: Decimal
    profit_margin: Decimal
    roi: Decimal
    demand_score: float
    turnover_score: float
    validation_score: float
    decision: str
    requested_mode: str
    actual_purchase_source: str
    actual_domestic_source: str
    purchase_fallback_used: bool
    domestic_fallback_used: bool
    data_status: str
    retrieved_at: str
    verification_complete: bool
    external_id: str = ""
    recommendation_rank: int | None = None
    yahoo_search_queries: str = ""
    yahoo_live_sample_count: int = 0
    yahoo_matched_sample_count: int = 0
    yahoo_matched_sample_titles: str = ""
    yahoo_sold_prices_display: str = ""
    matching_score: float = 0.0
    matching_reliability: str = ""
    yahoo_diagnostics: str = ""
    purchase_subtype: str = ""
    purchase_material: str = ""
    yahoo_rejected_sample_count: int = 0
    yahoo_accepted_comparables: str = ""
    yahoo_rejected_samples: str = ""
    comparable_median_jpy: Decimal = Decimal("0")
    legacy_median_jpy: Decimal = Decimal("0")
    comparable_data_warning: str = ""
