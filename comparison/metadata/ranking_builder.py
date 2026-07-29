"""Build consistent ranking metadata for comparison candidates."""

from __future__ import annotations

import copy

from comparison.models import MarketplaceCandidate
from product_identity.formatter import identity_result_to_export_fields
from ranking_foundation.context import RankingBatchContext
from ranking_foundation.policy import RankingPolicy
from ranking_foundation.scorer import RankingScoreCalculator
from ranking_foundation.signals import identity_confidence_from_label

WARNING_COUNT_KEY = "comparison_warning_count"
INTELLIGENCE_OVERALL_KEY = "ranking_intelligence_overall"
FOUNDATION_SCORE_KEY = "ranking_foundation_score"
IMPORT_COST_TOTAL_KEY = "import_cost_total_jpy"


class RankingMetadataBuilder:
    """Populate ranking metadata on price results from comparison context."""

    def __init__(
        self,
        policy: RankingPolicy | None = None,
        score_calculator: RankingScoreCalculator | None = None,
    ) -> None:
        self._policy = policy or RankingPolicy.default()
        self._score_calculator = score_calculator or RankingScoreCalculator(self._policy)

    def build(
        self,
        candidate: MarketplaceCandidate,
        batch: RankingBatchContext,
    ) -> dict[str, object]:
        """Return enriched metadata for one candidate without mutating inputs."""
        metadata = dict(candidate.price_result.metadata or {})
        metadata.update(self._identity_metadata(candidate))
        metadata.update(self._import_cost_metadata(candidate))
        metadata.update(self._search_metadata(candidate))
        metadata.update(self._intelligence_metadata(candidate))
        price_for_scoring = copy.deepcopy(candidate.price_result)
        price_for_scoring.metadata = metadata
        foundation_score = self._score_calculator.score_result(price_for_scoring, batch)
        metadata[FOUNDATION_SCORE_KEY] = str(foundation_score)
        return metadata

    def apply_batch(
        self,
        candidates: list[MarketplaceCandidate],
    ) -> RankingBatchContext:
        """Return batch context shared by all candidates in one comparison group."""
        return RankingBatchContext.from_results([candidate.price_result for candidate in candidates])

    @staticmethod
    def _identity_metadata(candidate: MarketplaceCandidate) -> dict[str, object]:
        fields = identity_result_to_export_fields(candidate.identity_result)
        metadata: dict[str, object] = dict(fields)
        confidence_label = fields.get("selected_review_identity_confidence")
        if isinstance(confidence_label, str):
            score = identity_confidence_from_label(confidence_label)
            if score is not None:
                metadata["identity_confidence_score"] = str(score)
        return metadata

    @staticmethod
    def _import_cost_metadata(candidate: MarketplaceCandidate) -> dict[str, object]:
        total_cost = candidate.price_result.total_cost_jpy
        if total_cost is None:
            return {}
        return {IMPORT_COST_TOTAL_KEY: str(total_cost)}

    @staticmethod
    def _search_metadata(candidate: MarketplaceCandidate) -> dict[str, object]:
        search_warnings = candidate.search_result.metadata.get("warnings")
        warning_count = len(search_warnings) if isinstance(search_warnings, list) else 0
        warning_count += len(candidate.match_warnings)
        return {WARNING_COUNT_KEY: warning_count}

    @staticmethod
    def _intelligence_metadata(candidate: MarketplaceCandidate) -> dict[str, object]:
        intel = candidate.price_result.profit_intelligence
        if intel is None or intel.overall_score is None:
            return {}
        return {INTELLIGENCE_OVERALL_KEY: float(intel.overall_score)}
