"""Data models for controlled browser acquisition."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AcquisitionStatus(StrEnum):
    """Outcome status for one acquisition attempt."""

    LIVE = "LIVE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ReliabilityLevel(StrEnum):
    """Reliability of domestic sold-price estimate."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class AcquiredListing:
    """One purchase-side listing acquired from a public browser page."""

    external_id: str
    title: str
    brand: str
    category: str
    condition: str
    price: Decimal
    currency: str
    url: str
    retrieved_at: str
    source: str
    raw_title: str
    acquisition_status: AcquisitionStatus
    image_url: str = ""


@dataclass(frozen=True, slots=True)
class YahooSoldSample:
    """One Yahoo Auction sold-price or live-auction sample."""

    title: str
    sold_price_jpy: int
    retrieved_at: str
    source: str
    sold_at: str = ""
    condition: str = ""
    url: str = ""
    buyout_price_jpy: int | None = None
    bid_count: int | None = None
    auction_status: str = ""
    seller: str = ""
    image_url: str = ""


@dataclass(frozen=True, slots=True)
class DomesticEstimate:
    """Domestic sold-price estimate from matched Yahoo samples."""

    sample_count: int
    minimum_jpy: int
    maximum_jpy: int
    average_jpy: Decimal
    median_jpy: Decimal
    trimmed_average_jpy: Decimal | None
    reliability: ReliabilityLevel
    listing_url: str
    matched_samples: tuple[YahooSoldSample, ...] = ()


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    """Result from one side of browser acquisition."""

    status: AcquisitionStatus
    listings: tuple[AcquiredListing, ...] = ()
    samples: tuple[YahooSoldSample, ...] = ()
    blocking_reason: str = ""
    detail: str = ""
    search_query: str = ""
    source: str = ""


@dataclass(frozen=True, slots=True)
class ControlledLiveVerificationResult:
    """One controlled live profit verification row."""

    product: str
    brand: str
    category: str
    fashionphile_url: str
    purchase_price: Decimal
    purchase_currency: str
    purchase_price_jpy_estimate: Decimal
    exchange_rate_display: str
    yahoo_search_terms: str
    yahoo_sold_samples: int
    yahoo_matched_samples: int
    matching_score: float
    matching_reliability: str
    median_selling_price_jpy: Decimal
    average_selling_price_jpy: Decimal
    cost_configuration_status: str
    estimated_shipping: str
    estimated_import_cost: str
    estimated_profit: Decimal
    profit_margin: Decimal
    roi: Decimal
    demand_score: float
    turnover_score: float
    validation_score: float
    decision: str
    acquisition_status: str
    data_status: str
    verification_complete: bool
    retrieved_at: str
    external_id: str
    blocking_reason: str = ""
    recommendation_rank: int | None = None
