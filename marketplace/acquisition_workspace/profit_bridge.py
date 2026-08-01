"""Bridge acquisition workspace candidates to batch profit pipeline."""

from __future__ import annotations

from decimal import Decimal

from marketplace.acquisition_workspace.models import (
    AcquisitionCandidate,
    ConfidenceLevel,
    DataTruthSummary,
    DiscoveryMetadata,
    RuntimeMode,
)
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate


MAX_BATCH_CANDIDATES = 20


def to_batch_profit_candidates(candidates: list[AcquisitionCandidate]) -> list[BatchProfitCandidate]:
    """Convert selected eligible workspace candidates to batch profit candidates."""
    selected = [
        item
        for item in candidates
        if item.selected_for_profit_check
        and item.eligible_for_profit_check
        and not item.duplicate_of
        and item.quality_grade != "REJECTED"
    ]
    if len(selected) > MAX_BATCH_CANDIDATES:
        raise ValueError(f"Maximum {MAX_BATCH_CANDIDATES} candidates allowed for batch profit")
    return [_convert(item) for item in selected]


def apply_profit_results(
    candidates: list[AcquisitionCandidate],
    *,
    batch_id: str,
    results_by_candidate_id: dict[str, dict],
) -> list[AcquisitionCandidate]:
    from dataclasses import replace
    from datetime import UTC, datetime

    updated: list[AcquisitionCandidate] = []
    for candidate in candidates:
        payload = results_by_candidate_id.get(candidate.candidate_id)
        if not payload:
            updated.append(candidate)
            continue
        checked_at = str(payload.get("retrieved_at") or "").strip()
        if not checked_at:
            checked_at = datetime.now(tz=UTC).isoformat()
        updated.append(
            replace(
                candidate,
                candidate_state="PROFIT_CHECKED",
                last_profit_batch_id=batch_id,
                last_profit_checked_at=checked_at,
                last_decision=payload.get("batch_decision", ""),
                last_gross_profit=Decimal(str(payload.get("gross_estimated_profit", "0"))),
                last_net_profit=(
                    Decimal(str(payload["net_estimated_profit"]))
                    if payload.get("net_estimated_profit") is not None
                    else None
                ),
                last_warning=payload.get("warning", ""),
                data_truth_summary=_merge_truth_summary(candidate, payload),
                discovery_metadata=_merge_discovery_metadata(candidate, payload),
            )
        )
    return updated


def _convert(item: AcquisitionCandidate) -> BatchProfitCandidate:
    return BatchProfitCandidate(
        candidate_id=item.candidate_id,
        title=item.title,
        brand=item.brand,
        category=item.category,
        detected_subtype=item.detected_subtype,
        detected_material=item.detected_material,
        condition=item.detected_condition,
        purchase_price=item.purchase_price,
        currency=item.currency,
        purchase_price_jpy=item.purchase_price_jpy,
        purchase_url=item.purchase_url,
        purchase_source=item.source_name,
        import_status="OK",
        subtype_override=item.detected_subtype,
        material_override=item.detected_material,
    )


def _merge_truth_summary(candidate: AcquisitionCandidate, payload: dict) -> DataTruthSummary:
    yahoo_source = str(payload.get("yahoo_data_source", "")).upper()
    runtime_mode = _runtime_mode_from_yahoo_source(yahoo_source)
    reasons = list(candidate.data_truth_summary.reasons)
    reasons.extend(_build_profit_reasons(payload, yahoo_source))
    return DataTruthSummary(
        source_mode=_resolve_source_mode(candidate, runtime_mode),
        acquisition_mode=candidate.source_type,
        market_source=candidate.source_name or candidate.source_type,
        price_source=candidate.data_truth_summary.price_source or "Imported Listing",
        comparable_source=_format_comparable_source(yahoo_source),
        shipping_source="Estimated",
        fee_source="Configured" if payload.get("net_profit_complete") else "Configured (Partial)",
        used_live_data=runtime_mode == RuntimeMode.LIVE.value,
        used_fixture_data=runtime_mode == RuntimeMode.FIXTURE.value,
        used_saved_html=candidate.source_type == "SAVED_HTML",
        used_manual_input=candidate.source_type == "MANUAL",
        used_estimated_price=True,
        used_estimated_shipping=True,
        confidence_level=_resolve_confidence(payload, runtime_mode),
        reasons=tuple(dict.fromkeys(reason for reason in reasons if reason)),
    )


def _merge_discovery_metadata(candidate: AcquisitionCandidate, payload: dict) -> DiscoveryMetadata:
    from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION

    queries = tuple(payload.get("yahoo_queries", ()) or candidate.yahoo_query_preview or ())
    candidate_count = int(payload.get("candidate_count", 0) or 0)
    comparable_count = int(payload.get("comparable_count", 0) or 0)
    return DiscoveryMetadata(
        discovery_timestamp=str(payload.get("retrieved_at", "")) or candidate.imported_at,
        runtime_mode=_runtime_mode_from_yahoo_source(str(payload.get("yahoo_data_source", ""))),
        query_count=max(1, len(queries)),
        query_used=queries,
        candidate_count=max(candidate_count, comparable_count),
        comparable_count=comparable_count,
        estimated_from_multiple_results=bool(payload.get("estimated_from_multiple_results")),
        median_used=bool(payload.get("median_used")),
        profit_analysis_version=str(
            payload.get("profit_analysis_version") or PROFIT_ANALYSIS_VERSION
        ),
    )


def _resolve_source_mode(candidate: AcquisitionCandidate, runtime_mode: str) -> str:
    if runtime_mode == RuntimeMode.IMPORT.value:
        return RuntimeMode.IMPORT.value
    return "MIXED"


def _format_comparable_source(yahoo_source: str) -> str:
    if yahoo_source == "LIVE_CACHE":
        return "Yahoo Live Cache"
    if yahoo_source == "LIVE":
        return "Yahoo LIVE"
    if yahoo_source == "FIXTURE":
        return "Yahoo Fixture"
    return "Unavailable"


def _build_profit_reasons(payload: dict, yahoo_source: str) -> tuple[str, ...]:
    reasons = []
    comparable_label = _format_comparable_source(yahoo_source)
    if comparable_label != "Unavailable":
        reasons.append(comparable_label)
    if payload.get("estimated_from_multiple_results"):
        reasons.append("Estimated From Multiple Results")
    if payload.get("median_used"):
        reasons.append("Median Comparable")
    reasons.append("Estimated Shipping")
    return tuple(reasons)


def _resolve_confidence(payload: dict, runtime_mode: str) -> str:
    comparable_count = int(payload.get("comparable_count", 0) or 0)
    if runtime_mode == RuntimeMode.LIVE.value and comparable_count >= 3:
        return ConfidenceLevel.HIGH.value
    if comparable_count >= 1:
        return ConfidenceLevel.MEDIUM.value
    return ConfidenceLevel.LOW.value


def _runtime_mode_from_yahoo_source(yahoo_source: str) -> str:
    normalized = yahoo_source.strip().upper()
    if normalized in {"LIVE", "LIVE_CACHE"}:
        return RuntimeMode.LIVE.value
    if normalized == "FIXTURE":
        return RuntimeMode.FIXTURE.value
    return RuntimeMode.IMPORT.value
