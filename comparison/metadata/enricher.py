"""Metadata enrichment for comparison pipeline stages."""

from __future__ import annotations

import copy

from comparison.metadata.ranking_builder import (
    FOUNDATION_SCORE_KEY,
    RankingMetadataBuilder,
)
from comparison.models import MarketplaceCandidate
from ranking_foundation.context import RankingBatchContext


class MetadataEnricher:
    """
    Enrich marketplace candidates after search, identity, and import-cost stages.

    Returns copied candidates with populated ranking metadata.
    """

    def __init__(self, builder: RankingMetadataBuilder | None = None) -> None:
        self._builder = builder or RankingMetadataBuilder()

    def enrich_candidate(
        self,
        candidate: MarketplaceCandidate,
        batch: RankingBatchContext,
    ) -> MarketplaceCandidate:
        """Return a candidate copy with ranking metadata applied."""
        if candidate_has_ranking_metadata(candidate):
            return candidate
        metadata = self._builder.build(candidate, batch)
        price_result = copy.deepcopy(candidate.price_result)
        price_result.metadata = metadata
        foundation_score = metadata.get("ranking_foundation_score")
        if foundation_score is not None:
            from decimal import Decimal

            price_result.ranking_score = Decimal(str(foundation_score))
        return MarketplaceCandidate(
            marketplace_name=candidate.marketplace_name,
            search_result=candidate.search_result,
            price_result=price_result,
            match_score=candidate.match_score,
            match_warnings=list(candidate.match_warnings),
            listing_currency=candidate.listing_currency,
            source_price_amount=candidate.source_price_amount,
            jpy_comparable=candidate.jpy_comparable,
            order_index=candidate.order_index,
            identity_matched=candidate.identity_matched,
            identity_listing=candidate.identity_listing,
            identity_result=candidate.identity_result,
        )

    def enrich_candidates(
        self,
        candidates: list[MarketplaceCandidate],
    ) -> list[MarketplaceCandidate]:
        """Enrich all candidates using one shared batch normalization context."""
        if not candidates:
            return []
        if all(candidate_has_ranking_metadata(candidate) for candidate in candidates):
            return list(candidates)
        batch = self._builder.apply_batch(candidates)
        return [self.enrich_candidate(candidate, batch) for candidate in candidates]


def candidate_has_ranking_metadata(candidate: MarketplaceCandidate) -> bool:
    """Return True when ranking foundation metadata is already present."""
    metadata = candidate.price_result.metadata or {}
    return FOUNDATION_SCORE_KEY in metadata
