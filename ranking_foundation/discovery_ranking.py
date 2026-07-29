"""Optional ranking helpers for profit discovery scores."""

from __future__ import annotations

from models.price_result import CALCULATION_SUCCESS, PriceResult
from profit_intelligence.discovery_models import DiscoveryScore


def rank_by_discovery_score(
    results: list[PriceResult],
    discovery_scores: list[DiscoveryScore],
    *,
    exclude_invalid: bool = True,
) -> list[PriceResult]:
    """
    Rank price results by discovery overall score, then profit, preserving stability.

    Does not mutate profit fields or replace the default RankingEngine behavior.
    """
    if len(results) != len(discovery_scores):
        raise ValueError("results and discovery_scores length mismatch")

    indexed = list(enumerate(zip(results, discovery_scores, strict=True)))
    if exclude_invalid:
        indexed = [
            item
            for item in indexed
            if item[1][0].calculation_status == CALCULATION_SUCCESS
        ]

    def sort_key(item: tuple[int, tuple[PriceResult, DiscoveryScore]]) -> tuple:
        index, (result, discovery) = item
        profit = float(result.profit_jpy) if result.profit_jpy is not None else float("-inf")
        return (-discovery.overall_score, -profit, index)

    return [item[1][0] for item in sorted(indexed, key=sort_key)]
