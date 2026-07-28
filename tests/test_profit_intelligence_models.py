"""Tests for profit intelligence models and normalization."""

import math
from decimal import Decimal

import pytest

from profit_intelligence.constants import SCORING_VERSION
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import (
    dedupe_preserve_order,
    normalize_optional_decimal,
    normalize_optional_float,
    normalize_optional_int,
    piecewise_linear_score,
)


def test_score_component_result_immutable_collections() -> None:
    result = ScoreComponentResult(
        score=50.0,
        available=True,
        reasons=("a",),
        warnings=("b",),
        missing_fields=("c",),
    )
    assert result.reasons == ("a",)
    assert result.warnings == ("b",)


def test_dedupe_preserve_order() -> None:
    assert dedupe_preserve_order(["a", "b", "a", ""]) == ("a", "b")


def test_reject_boolean_as_number() -> None:
    assert normalize_optional_int(True) is None
    assert normalize_optional_decimal(True) is None
    assert normalize_optional_float(True) is None


def test_reject_nan_and_infinity() -> None:
    assert normalize_optional_float(float("nan")) is None
    assert normalize_optional_float(float("inf")) is None
    assert normalize_optional_decimal(Decimal("NaN")) is None


def test_negative_counts_become_unknown() -> None:
    assert normalize_optional_int(-1) is None


def test_piecewise_linear_score_boundaries() -> None:
    score = piecewise_linear_score(5000.0, ((0, 5), (5000, 70), (20000, 100)))
    assert score == pytest.approx(70.0)


def test_profit_intelligence_input_defaults() -> None:
    data = ProfitIntelligenceInput()
    assert data.profit_amount_jpy is None
    assert data.sales_last_30_days is None


def test_scoring_version_constant() -> None:
    assert SCORING_VERSION == "profit-intelligence-v1"
