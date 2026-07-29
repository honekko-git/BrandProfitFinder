"""Comparison ranking via ranking foundation and enriched metadata.

Example::

    from comparison.ranking_adapter import ComparisonRankingAdapter

    adapter = ComparisonRankingAdapter()
    ranked = adapter.rank_candidates(candidates)
"""

from __future__ import annotations

from comparison.metadata.enricher import MetadataEnricher, candidate_has_ranking_metadata
from comparison.metadata.ranking_builder import (
    INTELLIGENCE_OVERALL_KEY,
    WARNING_COUNT_KEY,
)
from comparison.models import MarketplaceCandidate, ProductComparisonResult
from models.price_result import PriceResult


class ComparisonRankingAdapter:
    """Rank comparison candidates using enriched metadata and ranking foundation scores."""

    def __init__(self, enricher: MetadataEnricher | None = None) -> None:
        self._enricher = enricher or MetadataEnricher()

    def rank_candidates(self, candidates: list[MarketplaceCandidate]) -> list[MarketplaceCandidate]:
        """
        Rank marketplace candidates deterministically for selected review selection.

        Preserves Version1 ordering:
        intelligence overall → profit → margin → completeness → fewer warnings → order_index
        """
        enriched = (
            candidates
            if candidates and all(candidate_has_ranking_metadata(candidate) for candidate in candidates)
            else self._enricher.enrich_candidates(candidates)
        )
        indexed = list(enumerate(enriched))
        ranked = sorted(indexed, key=lambda item: self._candidate_sort_key(item), reverse=True)
        return [item[1] for item in ranked]

    def highest_profit_candidate(
        self,
        candidates: list[MarketplaceCandidate],
    ) -> MarketplaceCandidate | None:
        """Return the JPY-comparable candidate with the highest comparable profit."""
        comparable = [candidate for candidate in candidates if candidate.is_comparable]
        if not comparable:
            return None

        def sort_key(candidate: MarketplaceCandidate) -> tuple[float, int]:
            profit = candidate.comparable_profit_jpy
            profit_value = float(profit) if profit is not None else float("-inf")
            return (profit_value, -candidate.order_index)

        return max(comparable, key=sort_key)

    def rank_comparison_results(
        self,
        results: list[ProductComparisonResult],
    ) -> list[PriceResult]:
        """Rank best-per-product price results for export."""
        best_results: list[tuple[int, PriceResult]] = []
        for index, comparison in enumerate(results):
            ranked = self.rank_candidates(comparison.candidates)
            for candidate in ranked:
                if candidate.is_comparable:
                    best_results.append((index, candidate.price_result))
                    break

        ordered = sorted(best_results, key=lambda item: self._price_result_sort_key(item))
        return [item[1] for item in ordered]

    def _candidate_sort_key(self, item: tuple[int, MarketplaceCandidate]) -> tuple:
        index, candidate = item
        if not candidate.is_comparable:
            return (False, float("-inf"), float("-inf"), float("-inf"), float("-inf"), 0, index)
        metadata = candidate.price_result.metadata or {}
        return (
            True,
            _metadata_float(metadata, INTELLIGENCE_OVERALL_KEY),
            _profit_sort_value(candidate),
            _margin_sort_value(candidate),
            _metadata_float(metadata, "data_completeness"),
            -int(metadata.get(WARNING_COUNT_KEY, 0)),
            -index,
        )

    @staticmethod
    def _price_result_sort_key(item: tuple[int, PriceResult]) -> tuple:
        index, result = item
        metadata = result.metadata or {}
        overall = _metadata_float(metadata, INTELLIGENCE_OVERALL_KEY)
        completeness = _metadata_float(metadata, "data_completeness")
        profit = float(result.profit_jpy) if result.profit_jpy is not None else float("-inf")
        margin = float(result.profit_margin) if result.profit_margin is not None else float("-inf")
        return (-overall, -profit, -margin, -completeness, index)


def _profit_sort_value(candidate: MarketplaceCandidate) -> float:
    profit = candidate.comparable_profit_jpy
    return float(profit) if profit is not None else float("-inf")


def _margin_sort_value(candidate: MarketplaceCandidate) -> float:
    margin = candidate.comparable_profit_margin
    return float(margin) if margin is not None else float("-inf")


def _metadata_float(metadata: dict[str, object], key: str) -> float:
    value = metadata.get(key)
    if value is None:
        return float("-inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")
