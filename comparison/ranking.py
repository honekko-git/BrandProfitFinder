"""
Deterministic ranking for cross-marketplace comparison candidates.
"""

from __future__ import annotations

from comparison.models import MarketplaceCandidate, ProductComparisonResult
from models.price_result import PriceResult


def _warning_count(candidate: MarketplaceCandidate) -> int:
    search_warnings = candidate.search_result.metadata.get("warnings")
    search_count = len(search_warnings) if isinstance(search_warnings, list) else 0
    return search_count + len(candidate.match_warnings)


def _data_completeness(candidate: MarketplaceCandidate) -> float:
    metadata = candidate.price_result.metadata or {}
    value = metadata.get("data_completeness")
    if value is None:
        intel = candidate.price_result.profit_intelligence
        if intel is not None and intel.confidence_score is not None:
            return float(intel.confidence_score)
        return float("-inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def _overall_intelligence_score(candidate: MarketplaceCandidate) -> float:
    intel = candidate.price_result.profit_intelligence
    if intel is None or intel.overall_score is None:
        return float("-inf")
    return float(intel.overall_score)


def _profit_sort_value(candidate: MarketplaceCandidate) -> float:
    profit = candidate.comparable_profit_jpy
    return float(profit) if profit is not None else float("-inf")


def _margin_sort_value(candidate: MarketplaceCandidate) -> float:
    margin = candidate.comparable_profit_margin
    return float(margin) if margin is not None else float("-inf")


def rank_candidates(candidates: list[MarketplaceCandidate]) -> list[MarketplaceCandidate]:
    """
    Rank marketplace candidates deterministically for selected review selection.

    Eligible candidates must be JPY-comparable (``is_comparable``).

    Order for eligible candidates:
    1. Profit Intelligence overall score descending (missing sorts before any score)
    2. comparable profit JPY descending
    3. comparable profit margin descending
    4. data completeness descending
    5. fewer warnings
    6. original marketplace order (lower ``order_index`` wins full ties)
    """
    indexed = list(enumerate(candidates))

    def sort_key(item: tuple[int, MarketplaceCandidate]) -> tuple:
        index, candidate = item
        if not candidate.is_comparable:
            return (False, float("-inf"), float("-inf"), float("-inf"), float("-inf"), 0, index)
        return (
            True,
            _overall_intelligence_score(candidate),
            _profit_sort_value(candidate),
            _margin_sort_value(candidate),
            _data_completeness(candidate),
            -_warning_count(candidate),
            -index,
        )

    return [item[1] for item in sorted(indexed, key=sort_key, reverse=True)]


def highest_profit_candidate(
    candidates: list[MarketplaceCandidate],
) -> MarketplaceCandidate | None:
    """
    Return the JPY-comparable candidate with the highest comparable profit.

    Separate from selected review ranking; uses profit amount only.
    """
    comparable = [candidate for candidate in candidates if candidate.is_comparable]
    if not comparable:
        return None

    def sort_key(candidate: MarketplaceCandidate) -> tuple[float, int]:
        return (_profit_sort_value(candidate), -candidate.order_index)

    return max(comparable, key=sort_key)


def rank_comparison_results(
    results: list[ProductComparisonResult],
) -> list[PriceResult]:
    """
    Rank best-per-product price results for export.

    Uses the same deterministic ordering as candidate ranking.
    """
    best_results: list[tuple[int, PriceResult]] = []
    for index, comparison in enumerate(results):
        ranked = rank_candidates(comparison.candidates)
        for candidate in ranked:
            if candidate.is_comparable:
                best_results.append((index, candidate.price_result))
                break

    def sort_key(item: tuple[int, PriceResult]) -> tuple:
        index, result = item
        intel = result.profit_intelligence
        overall = intel.overall_score if intel is not None else None
        completeness = _metadata_float(result, "data_completeness")
        profit = float(result.profit_jpy) if result.profit_jpy is not None else float("-inf")
        margin = float(result.profit_margin) if result.profit_margin is not None else float("-inf")
        overall_sort = overall if overall is not None else float("-inf")
        return (-overall_sort, -profit, -margin, -completeness, index)

    return [item[1] for item in sorted(best_results, key=sort_key)]


def _metadata_float(result: PriceResult, key: str) -> float:
    metadata = result.metadata or {}
    value = metadata.get(key)
    if value is None:
        intel = result.profit_intelligence
        if key == "data_completeness" and intel is not None and intel.confidence_score is not None:
            return float(intel.confidence_score)
        return float("-inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")
