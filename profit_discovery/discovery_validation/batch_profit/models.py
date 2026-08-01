"""Data models for batch real profit discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class BatchDisplayDecision(StrEnum):
    """Batch-specific display decision label."""

    STRONG_CANDIDATE = "STRONG CANDIDATE"
    REVIEW = "REVIEW"
    HOLD = "HOLD"
    REJECT = "REJECT"
    DATA_INSUFFICIENT = "DATA INSUFFICIENT"
    BLOCKED = "BLOCKED"


class BatchRunStatus(StrEnum):
    """Overall batch run status."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class YahooDataSource(StrEnum):
    """Truth label for Yahoo sold data origin."""

    LIVE = "LIVE"
    LIVE_CACHE = "LIVE_CACHE"
    UNAVAILABLE = "UNAVAILABLE"
    FIXTURE = "FIXTURE"


@dataclass(frozen=True, slots=True)
class BatchProfitCandidate:
    """One purchase candidate in a batch run."""

    candidate_id: str
    title: str
    brand: str
    category: str
    detected_subtype: str
    detected_material: str
    condition: str
    purchase_price: Decimal
    currency: str
    purchase_price_jpy: Decimal
    purchase_url: str
    purchase_source: str
    import_status: str = "OK"
    subtype_override: str = ""
    material_override: str = ""


@dataclass(frozen=True, slots=True)
class EstimatedCosts:
    """Cost breakdown used for net profit display."""

    exchange_rate: str
    international_shipping_jpy: Decimal
    forwarding_fee_jpy: Decimal
    import_duty_jpy: Decimal
    import_tax_jpy: Decimal
    payment_fee_jpy: Decimal
    domestic_platform_fee_jpy: Decimal
    domestic_shipping_jpy: Decimal
    inspection_or_repair_reserve_jpy: Decimal
    miscellaneous_cost_jpy: Decimal
    total_additional_costs_jpy: Decimal
    net_profit_complete: bool
    unconfigured_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RobustDomesticEstimate:
    """Robust domestic estimate from accepted comparables."""

    raw_sample_count: int
    accepted_count: int
    rejected_count: int
    minimum_jpy: int
    maximum_jpy: int
    average_jpy: Decimal
    median_jpy: Decimal
    q1_jpy: int
    q3_jpy: int
    iqr_jpy: int
    outlier_count: int
    trimmed_average_jpy: Decimal | None
    recommended_selling_estimate_jpy: Decimal
    reliability: str
    comparable_warning: str = ""
    outlier_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BatchProfitResult:
    """One batch profit verification result."""

    candidate: BatchProfitCandidate
    yahoo_queries: tuple[str, ...]
    yahoo_data_source: str
    yahoo_cache_retrieved_at: str
    yahoo_cache_age_hours: float | None
    raw_sample_count: int
    accepted_comparable_count: int
    rejected_sample_count: int
    domestic: RobustDomesticEstimate
    estimated_costs: EstimatedCosts
    gross_estimated_profit: Decimal
    net_estimated_profit: Decimal | None
    profit_margin: Decimal
    net_profit_margin: Decimal | None
    roi: Decimal
    net_roi: Decimal | None
    engine_decision: str
    batch_decision: str
    data_status: str
    verification_complete: bool
    retrieved_at: str
    failure_reason: str
    comparable_warning: str
    warnings: tuple[str, ...]
    diagnostics: str
    accepted_comparables_display: str
    rejected_samples_display: str
    rank: int = 0
    # Best Yahoo comparable for detail (sold or open); empty when unmatched
    yahoo_best_title: str = ""
    yahoo_best_price_jpy: int = 0
    yahoo_best_url: str = ""
    yahoo_best_score: int = 0
    yahoo_best_attributes: str = ""
    yahoo_best_condition: str = ""
    yahoo_marketplace: str = ""
    operational_trace: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BatchRunSummary:
    """Summary for one batch run."""

    batch_id: str
    started_at: str
    completed_at: str
    total_candidates: int
    processed_count: int
    strong_candidate_count: int
    review_count: int
    hold_count: int
    reject_count: int
    failed_count: int
    blocked_count: int
    total_yahoo_requests: int
    cache_hits: int
    exchange_rate: str
    cost_profile: str
    status: str
    import_errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class BatchProfitRun:
    """Complete batch run with summary and ranked results."""

    summary: BatchRunSummary
    results: tuple[BatchProfitResult, ...]
