"""Tests for batch display decision rules."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.discovery_validation.batch_profit.decisions import assign_batch_decision
from profit_discovery.discovery_validation.batch_profit.models import BatchDisplayDecision


def test_strong_candidate_requires_complete_net_profit() -> None:
    decision = assign_batch_decision(
        accepted_count=6,
        reliability="HIGH",
        comparable_warning="",
        net_profit_complete=True,
        net_profit=Decimal("20000"),
        net_margin=Decimal("0.20"),
        net_roi=Decimal("0.20"),
        yahoo_data_source="LIVE",
        failure_reason="",
        engine_decision="BUY",
        purchase_subtype="COMPACT_WALLET",
    )
    assert decision == BatchDisplayDecision.STRONG_CANDIDATE.value


def test_suspect_warning_prevents_strong_candidate() -> None:
    decision = assign_batch_decision(
        accepted_count=6,
        reliability="HIGH",
        comparable_warning="COMPARABLE_DATA_SUSPECT",
        net_profit_complete=True,
        net_profit=Decimal("20000"),
        net_margin=Decimal("0.20"),
        net_roi=Decimal("0.20"),
        yahoo_data_source="LIVE",
        failure_reason="",
        engine_decision="HOLD",
        purchase_subtype="COMPACT_WALLET",
    )
    assert decision != BatchDisplayDecision.STRONG_CANDIDATE.value


def test_data_insufficient_for_low_sample_count() -> None:
    decision = assign_batch_decision(
        accepted_count=2,
        reliability="LOW",
        comparable_warning="",
        net_profit_complete=False,
        net_profit=None,
        net_margin=None,
        net_roi=None,
        yahoo_data_source="LIVE",
        failure_reason="",
        engine_decision="PASS",
        purchase_subtype="COMPACT_WALLET",
    )
    assert decision == BatchDisplayDecision.DATA_INSUFFICIENT.value


def test_blocked_when_yahoo_unavailable() -> None:
    decision = assign_batch_decision(
        accepted_count=0,
        reliability="LOW",
        comparable_warning="",
        net_profit_complete=False,
        net_profit=None,
        net_margin=None,
        net_roi=None,
        yahoo_data_source="UNAVAILABLE",
        failure_reason="Yahoo sold data unavailable",
        engine_decision="PASS",
        purchase_subtype="COMPACT_WALLET",
    )
    assert decision == BatchDisplayDecision.BLOCKED.value


def test_wallet_unknown_subtype_still_data_insufficient() -> None:
    decision = assign_batch_decision(
        accepted_count=4,
        reliability="MEDIUM",
        comparable_warning="",
        net_profit_complete=True,
        net_profit=Decimal("10000"),
        net_margin=Decimal("0.10"),
        net_roi=Decimal("0.10"),
        yahoo_data_source="LIVE",
        failure_reason="",
        engine_decision="HOLD",
        purchase_subtype="UNKNOWN",
        purchase_category="Wallet",
    )
    assert decision == BatchDisplayDecision.DATA_INSUFFICIENT.value


def test_bag_unknown_subtype_not_blocked_by_subtype_alone() -> None:
    decision = assign_batch_decision(
        accepted_count=4,
        reliability="MEDIUM",
        comparable_warning="",
        net_profit_complete=True,
        net_profit=Decimal("10000"),
        net_margin=Decimal("0.10"),
        net_roi=Decimal("0.10"),
        yahoo_data_source="LIVE",
        failure_reason="",
        engine_decision="HOLD",
        purchase_subtype="UNKNOWN",
        purchase_category="Bag",
    )
    assert decision != BatchDisplayDecision.DATA_INSUFFICIENT.value
    assert decision == BatchDisplayDecision.REVIEW.value
