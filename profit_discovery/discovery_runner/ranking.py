"""Ranking helpers for batch discovery candidate results."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.models import BuyDecision


def rank_discovery_results(
    results: list[DiscoveryCandidateResult],
) -> list[DiscoveryCandidateResult]:
    """
    Rank discovery candidate results without modifying RankingEngine.

    Order:
        1. BUY decisions first
        2. Discovery overall score descending
        3. Profit descending
    """
    return sorted(results, key=_rank_key)


def _rank_key(result: DiscoveryCandidateResult) -> tuple:
    decision_rank = _decision_rank(result)
    discovery_score = (
        result.discovery_score.overall_score
        if result.discovery_score is not None
        else float("-inf")
    )
    profit = (
        float(result.profit_result.profit_jpy)
        if result.profit_result is not None and result.profit_result.profit_jpy is not None
        else float("-inf")
    )
    status_rank = 0 if result.status is DiscoveryCandidateStatus.SUCCESS else 1
    return (status_rank, decision_rank, -discovery_score, -profit)


def _decision_rank(result: DiscoveryCandidateResult) -> int:
    if result.buy_decision is None:
        return 3
    if result.buy_decision.decision is BuyDecision.BUY:
        return 0
    if result.buy_decision.decision is BuyDecision.HOLD:
        return 1
    return 2
