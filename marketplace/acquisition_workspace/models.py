"""Domain models for acquisition workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class RuntimeMode(StrEnum):
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    IMPORT = "IMPORT"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceType(StrEnum):
    MANUAL = "MANUAL"
    CSV = "CSV"
    SAVED_HTML = "SAVED_HTML"
    PUBLIC_URL = "PUBLIC_URL"
    EXISTING_IMPORT = "EXISTING_IMPORT"
    FIXTURE = "FIXTURE"


class CandidateDataStatus(StrEnum):
    IMPORT = "IMPORT"
    PARSED_SAVED_HTML = "PARSED_SAVED_HTML"
    PUBLIC_PAGE = "PUBLIC_PAGE"
    FIXTURE = "FIXTURE"
    UNAVAILABLE = "UNAVAILABLE"


class CandidateQualityGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    REJECTED = "REJECTED"


class CandidateState(StrEnum):
    NEW = "NEW"
    READY = "READY"
    SELECTED = "SELECTED"
    PROFIT_CHECKED = "PROFIT_CHECKED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    ERROR = "ERROR"


VALID_STATE_TRANSITIONS: dict[CandidateState, set[CandidateState]] = {
    CandidateState.NEW: {CandidateState.READY, CandidateState.REJECTED, CandidateState.ERROR, CandidateState.DUPLICATE},
    CandidateState.READY: {CandidateState.SELECTED, CandidateState.REJECTED, CandidateState.ERROR, CandidateState.DUPLICATE},
    CandidateState.SELECTED: {CandidateState.READY, CandidateState.PROFIT_CHECKED, CandidateState.REJECTED},
    CandidateState.PROFIT_CHECKED: {CandidateState.SELECTED, CandidateState.READY},
    CandidateState.REJECTED: set(),
    CandidateState.DUPLICATE: set(),
    CandidateState.ERROR: {CandidateState.READY, CandidateState.REJECTED},
}


@dataclass
class DataTruthSummary:
    source_mode: str = RuntimeMode.IMPORT.value
    acquisition_mode: str = ""
    market_source: str = ""
    price_source: str = ""
    comparable_source: str = ""
    shipping_source: str = ""
    fee_source: str = ""
    used_live_data: bool = False
    used_fixture_data: bool = False
    used_saved_html: bool = False
    used_manual_input: bool = False
    used_estimated_price: bool = False
    used_estimated_shipping: bool = False
    confidence_level: str = ConfidenceLevel.MEDIUM.value
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class DiscoveryMetadata:
    discovery_timestamp: str = ""
    runtime_mode: str = RuntimeMode.IMPORT.value
    query_count: int = 1
    query_used: tuple[str, ...] = field(default_factory=tuple)
    candidate_count: int = 1
    comparable_count: int = 0
    estimated_from_multiple_results: bool = False
    median_used: bool = False
    profit_analysis_version: str = ""


@dataclass
class AcquisitionCandidate:
    candidate_id: str
    workspace_batch_id: str
    title: str
    normalized_title: str
    brand: str
    category: str
    detected_subtype: str
    detected_material: str
    detected_model_tokens: tuple[str, ...]
    detected_color: str
    detected_condition: str
    purchase_price: Decimal
    currency: str
    purchase_price_jpy: Decimal
    purchase_url: str
    source_name: str
    source_type: str
    external_id: str
    image_url: str
    seller_name: str
    location: str
    raw_description: str
    acquired_at: str
    imported_at: str
    data_status: str
    quality_score: int
    quality_grade: str
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]
    duplicate_of: str
    duplicate_reason: str
    eligible_for_profit_check: bool
    selected_for_profit_check: bool
    candidate_state: str = CandidateState.NEW.value
    yahoo_query_preview: tuple[str, ...] = ()
    last_profit_batch_id: str = ""
    last_profit_checked_at: str = ""
    last_decision: str = ""
    last_gross_profit: Decimal | None = None
    last_net_profit: Decimal | None = None
    last_warning: str = ""
    data_truth_summary: DataTruthSummary = field(default_factory=DataTruthSummary)
    discovery_metadata: DiscoveryMetadata = field(default_factory=DiscoveryMetadata)


@dataclass
class WorkspaceBatch:
    workspace_batch_id: str
    name: str
    source_type: str
    created_at: str
    updated_at: str
    total_rows: int
    accepted_count: int
    warning_count: int
    rejected_count: int
    duplicate_count: int
    selected_count: int
    status: str


@dataclass
class ImportEvent:
    event_id: str
    workspace_batch_id: str
    candidate_id: str
    event_type: str
    parser_strategy: str
    source_filename: str
    source_file_hash: str
    diagnostics: dict
    created_at: str


@dataclass
class ParsedCandidate:
    title: str
    brand: str
    category: str
    condition: str
    purchase_price: Decimal
    currency: str
    purchase_url: str
    source_name: str
    external_id: str
    image_url: str
    raw_description: str
    parser_strategy: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


def can_transition(current: CandidateState, target: CandidateState) -> bool:
    return target in VALID_STATE_TRANSITIONS.get(current, set())


def transition_state(current: str, target: str) -> str:
    current_state = CandidateState(current)
    target_state = CandidateState(target)
    if not can_transition(current_state, target_state):
        raise ValueError(f"Invalid state transition: {current} -> {target}")
    return target_state.value


def validate_discovery_metadata(metadata: DiscoveryMetadata) -> tuple[str, ...]:
    errors: list[str] = []
    if not metadata.runtime_mode:
        errors.append("runtime_mode is required")
    if metadata.query_count < 1:
        errors.append("query_count must be at least 1")
    if metadata.candidate_count < metadata.comparable_count:
        errors.append("candidate_count must be greater than or equal to comparable_count")
    return tuple(errors)


def validate_data_truth_summary(summary: DataTruthSummary) -> tuple[str, ...]:
    if not summary.confidence_level:
        return ("confidence_level is required",)
    return ()


def validate_candidate_transparency(candidate: AcquisitionCandidate) -> tuple[str, ...]:
    return (
        *validate_data_truth_summary(candidate.data_truth_summary),
        *validate_discovery_metadata(candidate.discovery_metadata),
    )


def confidence_sort_key(level: str) -> int:
    return {
        ConfidenceLevel.HIGH.value: 3,
        ConfidenceLevel.MEDIUM.value: 2,
        ConfidenceLevel.LOW.value: 1,
    }.get(level, 0)
