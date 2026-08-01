"""Tests for acquisition workspace domain models."""

from __future__ import annotations

import pytest

from marketplace.acquisition_workspace.models import (
    CandidateDataStatus,
    CandidateQualityGrade,
    CandidateState,
    SourceType,
    can_transition,
    transition_state,
)


def test_source_type_values() -> None:
    assert SourceType.CSV.value == "CSV"
    assert SourceType.SAVED_HTML.value == "SAVED_HTML"
    assert SourceType.EXISTING_IMPORT.value == "EXISTING_IMPORT"


def test_data_status_values() -> None:
    assert CandidateDataStatus.IMPORT.value == "IMPORT"
    assert CandidateDataStatus.PARSED_SAVED_HTML.value == "PARSED_SAVED_HTML"
    assert CandidateDataStatus.UNAVAILABLE.value == "UNAVAILABLE"


def test_quality_grade_values() -> None:
    assert CandidateQualityGrade.A.value == "A"
    assert CandidateQualityGrade.REJECTED.value == "REJECTED"


def test_valid_state_transitions() -> None:
    assert can_transition(CandidateState.NEW, CandidateState.READY)
    assert can_transition(CandidateState.READY, CandidateState.SELECTED)
    assert can_transition(CandidateState.SELECTED, CandidateState.PROFIT_CHECKED)
    assert can_transition(CandidateState.PROFIT_CHECKED, CandidateState.READY)


def test_invalid_state_transitions() -> None:
    assert not can_transition(CandidateState.REJECTED, CandidateState.SELECTED)
    assert not can_transition(CandidateState.DUPLICATE, CandidateState.SELECTED)
    assert not can_transition(CandidateState.NEW, CandidateState.PROFIT_CHECKED)


def test_transition_state_success() -> None:
    assert transition_state("READY", "SELECTED") == "SELECTED"


def test_transition_state_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid state transition"):
        transition_state("REJECTED", "SELECTED")
