"""Focused tests for data truth summary and metadata validation."""

from __future__ import annotations

from marketplace.acquisition_workspace.models import (
    ConfidenceLevel,
    DataTruthSummary,
    DiscoveryMetadata,
    RuntimeMode,
    validate_data_truth_summary,
    validate_discovery_metadata,
)


def test_data_truth_summary_defaults_are_export_safe() -> None:
    summary = DataTruthSummary()
    assert summary.source_mode == RuntimeMode.IMPORT.value
    assert summary.confidence_level == ConfidenceLevel.MEDIUM.value
    assert summary.reasons == ()


def test_discovery_metadata_validation_errors_are_specific() -> None:
    metadata = DiscoveryMetadata(
        discovery_timestamp="2026-07-30T00:00:00+00:00",
        runtime_mode="",
        query_count=0,
        query_used=(),
        candidate_count=1,
        comparable_count=2,
        estimated_from_multiple_results=False,
        median_used=False,
    )
    errors = validate_discovery_metadata(metadata)
    assert "runtime_mode is required" in errors
    assert "query_count must be at least 1" in errors
    assert "candidate_count must be greater than or equal to comparable_count" in errors


def test_data_truth_summary_requires_confidence() -> None:
    errors = validate_data_truth_summary(DataTruthSummary(confidence_level=""))
    assert errors == ("confidence_level is required",)
