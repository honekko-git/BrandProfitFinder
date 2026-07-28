"""
Profit Intelligence data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from profit_intelligence.constants import SCORING_VERSION


@dataclass(frozen=True)
class ScoreComponentResult:
    """Result of a single scoring component."""

    score: float | None
    available: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfitIntelligenceInput:
    """Normalized input for deterministic scoring."""

    profit_amount_jpy: Decimal | None = None
    profit_margin_percent: Decimal | None = None
    domestic_sale_price_jpy: Decimal | None = None
    overseas_purchase_price_jpy: Decimal | None = None
    currency: str | None = None
    shipping_cost_known: bool | None = None
    marketplace_fee_known: bool | None = None
    duties_tax_known: bool | None = None
    sales_last_30_days: int | None = None
    sales_last_72_hours: int | None = None
    asks_count: int | None = None
    bids_count: int | None = None
    inventory_count: int | None = None
    volatility_percent: Decimal | None = None
    lowest_ask: Decimal | None = None
    highest_bid: Decimal | None = None
    last_sale_price: Decimal | None = None
    identifier_match_strength: float | None = None
    title_match_strength: float | None = None
    size_match: bool | None = None
    style_code_present: bool | None = None
    product_id_present: bool | None = None
    jan_present: bool | None = None
    source_count: int | None = None
    listing_count: int | None = None
    rejected_listing_count: int | None = None
    validation_warning_count: int | None = None


@dataclass(frozen=True)
class ProfitIntelligenceResult:
    """Aggregated profit intelligence output."""

    overall_score: float | None
    profit_score: float | None
    velocity_score: float | None
    risk_score: float | None
    confidence_score: float
    recommendation: str
    recommendation_stars: int
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    evaluated_components: tuple[str, ...] = ()
    unavailable_components: tuple[str, ...] = ()
    scoring_version: str = SCORING_VERSION

