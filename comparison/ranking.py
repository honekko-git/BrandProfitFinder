"""
Deterministic ranking for cross-marketplace comparison candidates.
"""

from __future__ import annotations

from comparison.models import MarketplaceCandidate, ProductComparisonResult
from comparison.ranking_adapter import ComparisonRankingAdapter
from models.price_result import PriceResult

_default_adapter = ComparisonRankingAdapter()


def rank_candidates(candidates: list[MarketplaceCandidate]) -> list[MarketplaceCandidate]:
    """Rank marketplace candidates deterministically for selected review selection."""
    return _default_adapter.rank_candidates(candidates)


def highest_profit_candidate(
    candidates: list[MarketplaceCandidate],
) -> MarketplaceCandidate | None:
    """Return the JPY-comparable candidate with the highest comparable profit."""
    return _default_adapter.highest_profit_candidate(candidates)


def rank_comparison_results(
    results: list[ProductComparisonResult],
) -> list[PriceResult]:
    """Rank best-per-product price results for export."""
    return _default_adapter.rank_comparison_results(results)
