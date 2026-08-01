"""Batch display decision rules."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.discovery_validation.batch_profit.models import BatchDisplayDecision, BatchProfitResult


def assign_batch_decision(
    *,
    accepted_count: int,
    reliability: str,
    comparable_warning: str,
    net_profit_complete: bool,
    net_profit: Decimal | None,
    net_margin: Decimal | None,
    net_roi: Decimal | None,
    yahoo_data_source: str,
    failure_reason: str,
    engine_decision: str,
    purchase_subtype: str,
    purchase_category: str = "",
) -> str:
    """Assign batch display decision without modifying ProfitValidationValidator."""
    if failure_reason or yahoo_data_source == "UNAVAILABLE":
        if "BLOCKED" in failure_reason.upper():
            return BatchDisplayDecision.BLOCKED.value
        if accepted_count == 0 and failure_reason:
            return BatchDisplayDecision.BLOCKED.value
    if accepted_count < 3:
        return BatchDisplayDecision.DATA_INSUFFICIENT.value
    # Wallet subtype UNKNOWN remains insufficient. Bags have no subtype detector yet —
    # UNKNOWN must not alone block ranking for canonical Bag candidates.
    if purchase_subtype == "UNKNOWN" and purchase_category != "Bag":
        return BatchDisplayDecision.DATA_INSUFFICIENT.value
    if comparable_warning == "COMPARABLE_DATA_SUSPECT":
        return BatchDisplayDecision.REVIEW.value if net_profit and net_profit > 0 else BatchDisplayDecision.HOLD.value
    if (
        accepted_count >= 5
        and reliability in {"MEDIUM", "HIGH"}
        and not comparable_warning
        and net_profit_complete
        and net_profit is not None
        and net_profit >= Decimal("15000")
        and net_margin is not None
        and net_margin >= Decimal("0.15")
        and net_roi is not None
        and net_roi >= Decimal("0.15")
        and yahoo_data_source in {"LIVE", "LIVE_CACHE"}
    ):
        return BatchDisplayDecision.STRONG_CANDIDATE.value
    if (
        net_profit is not None
        and net_profit >= Decimal("8000")
        and accepted_count >= 3
    ):
        return BatchDisplayDecision.REVIEW.value
    if accepted_count in {3, 4} and reliability == "MEDIUM":
        return BatchDisplayDecision.REVIEW.value
    if engine_decision.startswith("PROVISIONAL"):
        return BatchDisplayDecision.REVIEW.value
    if engine_decision == "PASS" or (net_profit is not None and net_profit < 0):
        return BatchDisplayDecision.REJECT.value if net_profit is not None and net_profit < 0 else BatchDisplayDecision.HOLD.value
    return BatchDisplayDecision.HOLD.value


def decision_sort_key(result: BatchProfitResult) -> tuple[int, float]:
    """Sort key for batch ranking."""
    order = {
        BatchDisplayDecision.STRONG_CANDIDATE.value: 0,
        BatchDisplayDecision.REVIEW.value: 1,
        BatchDisplayDecision.HOLD.value: 2,
        BatchDisplayDecision.DATA_INSUFFICIENT.value: 3,
        BatchDisplayDecision.REJECT.value: 4,
        BatchDisplayDecision.BLOCKED.value: 5,
    }
    net_profit = float(result.net_estimated_profit or result.gross_estimated_profit)
    return order.get(result.batch_decision, 9), -net_profit
