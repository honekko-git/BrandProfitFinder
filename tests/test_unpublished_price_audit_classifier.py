"""Focused deterministic tests for unpublished-price audit classifier."""

from __future__ import annotations

from scripts.unpublished_audit_classifier import classify_primary, recoverability


def test_category_only_sold_pool_is_correct_rejection() -> None:
    primary, secondary = classify_primary(
        result={},
        quality_info={"quality": "SUSPECT", "reason": "同一モデル販売データ不足"},
        warning="COMPARABLE_DATA_SUSPECT",
        nmv={},
        identity={"reference_numbers": [], "family": "", "collection": ""},
        yahoo={"raw_count": 5, "queries": ["prada tote"]},
        mercari={"raw_count": 0, "queries": []},
        same_model=0,
        sold=5,
        category_matches=5,
        best_score=75,
        junk=0,
    )
    assert primary == "CATEGORY_ONLY_MATCHES"
    assert recoverability(primary, {}, {"raw_count": 5}, {"raw_count": 0}, 0, 5, 75) == "A_CORRECT_REJECTION"


def test_no_raw_samples_with_reference_is_query_narrow() -> None:
    primary, _ = classify_primary(
        result={},
        quality_info={"quality": "INSUFFICIENT", "sold_confirmed_count": 0},
        warning="",
        nmv={},
        identity={"reference_numbers": ["SPR26Z"], "family": "", "collection": ""},
        yahoo={"raw_count": 0, "queries": ["PRADA SPR26Z"]},
        mercari={"raw_count": 0, "queries": []},
        same_model=0,
        sold=0,
        category_matches=0,
        best_score=0,
        junk=0,
    )
    assert primary == "QUERY_TOO_NARROW"


def test_new_price_critical() -> None:
    primary, _ = classify_primary(
        result={},
        quality_info={"quality": "HIGH"},
        warning="",
        nmv={"risk": "CRITICAL", "ranking_safe": False, "code": "NEW_PRICE_LOWER_THAN_USED"},
        identity={"reference_numbers": ["SPR26Z"], "family": "Sunglasses", "collection": ""},
        yahoo={"raw_count": 3, "queries": []},
        mercari={"raw_count": 0, "queries": []},
        same_model=3,
        sold=3,
        category_matches=0,
        best_score=95,
        junk=0,
    )
    assert primary == "NEW_PRICE_CRITICAL"
