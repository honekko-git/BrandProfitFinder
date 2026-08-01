"""Tests for candidate quality scoring."""

from __future__ import annotations

from decimal import Decimal

from marketplace.acquisition_workspace.quality import SUPPORTED_LIVE_CATEGORIES, score_candidate


def _score(**overrides):
    defaults = dict(
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        detected_subtype="COMPACT_WALLET",
        detected_material="Caviar",
        purchase_price=Decimal("695"),
        currency="USD",
        purchase_url="https://example.com/item",
        detected_condition="EXCELLENT",
    )
    defaults.update(overrides)
    return score_candidate(**defaults)


def test_supported_live_categories_wallet_and_bag_only() -> None:
    assert SUPPORTED_LIVE_CATEGORIES == {"Wallet", "Bag"}


def test_grade_a_for_complete_wallet() -> None:
    score, grade, warnings, errors, eligible = _score()
    assert grade in {"A", "B"}
    assert score >= 70
    assert not errors
    assert eligible


def test_bag_eligible_when_quality_and_brand_pass() -> None:
    score, grade, warnings, errors, eligible = _score(
        title="Chanel Classic Double Flap Bag Quilted Patent Medium",
        category="Bag",
        detected_subtype="UNKNOWN",
        detected_material="Patent",
    )
    assert "CATEGORY_NOT_SUPPORTED_FOR_LIVE_PROFIT" not in warnings
    assert not errors
    assert grade in {"A", "B", "C"}
    assert eligible
    assert score >= 50


def test_unknown_category_ineligible() -> None:
    _, grade, warnings, _, eligible = _score(category="Unknown")
    assert "category not detected" in warnings or "CATEGORY_NOT_SUPPORTED_FOR_LIVE_PROFIT" in warnings
    assert not eligible


def test_unsupported_category_ineligible() -> None:
    _, _, warnings, _, eligible = _score(category="Jewelry")
    assert "CATEGORY_NOT_SUPPORTED_FOR_LIVE_PROFIT" in warnings
    assert not eligible


def test_low_quality_bag_ineligible() -> None:
    _, grade, _, errors, eligible = _score(
        title="",
        category="Bag",
        brand="Chanel",
    )
    assert grade == "REJECTED"
    assert "missing title" in errors
    assert not eligible


def test_rejected_missing_title() -> None:
    _, grade, _, errors, eligible = _score(title="")
    assert grade == "REJECTED"
    assert "missing title" in errors
    assert not eligible


def test_rejected_invalid_price() -> None:
    _, grade, _, errors, eligible = _score(purchase_price=Decimal("0"))
    assert grade == "REJECTED"
    assert not eligible


def test_rejected_unsupported_currency() -> None:
    _, grade, _, errors, eligible = _score(currency="CNY")
    assert grade == "REJECTED"
    assert "unsupported currency" in errors


def test_hard_exclusion_replica() -> None:
    _, grade, _, errors, eligible = _score(title="Chanel replica wallet")
    assert grade == "REJECTED"
    assert "hard exclusion keyword" in errors
    assert not eligible


def test_missing_subtype_still_scores() -> None:
    score, grade, warnings, _, _ = _score(detected_subtype="UNKNOWN")
    assert grade in {"A", "B", "C"}
    assert "subtype unknown" in warnings
    assert score >= 50


def test_bag_subtype_unknown_does_not_alone_block_eligibility() -> None:
    _, _, warnings, _, eligible = _score(
        title="Louis Vuitton Speedy handbag",
        category="Bag",
        detected_subtype="UNKNOWN",
        detected_material="Unknown",
    )
    assert "subtype unknown" in warnings
    assert eligible
