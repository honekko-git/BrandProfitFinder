"""Merge duplicate discovery candidates by resolved product identity."""

from __future__ import annotations

from dataclasses import replace

from product_identity.identity_resolver import ProductIdentityResolver
from product_identity.models import ProductIdentity
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus


class DuplicateResolver:
    """Merge discovery candidates that share the same brand and identity key."""

    def merge_candidates(
        self,
        candidates: list[DiscoveryCandidateResult] | tuple[DiscoveryCandidateResult, ...],
        *,
        identity_resolver: ProductIdentityResolver | None = None,
    ) -> list[DiscoveryCandidateResult]:
        """Merge duplicate candidates while preserving the strongest metrics."""
        active_resolver = identity_resolver or ProductIdentityResolver()
        success_candidates: list[DiscoveryCandidateResult] = []
        passthrough: list[DiscoveryCandidateResult] = []

        for candidate in candidates:
            if candidate.status is DiscoveryCandidateStatus.SUCCESS:
                success_candidates.append(candidate)
            else:
                passthrough.append(candidate)

        grouped: dict[tuple[str, str], list[tuple[DiscoveryCandidateResult, ProductIdentity]]] = {}
        for candidate in success_candidates:
            identity = active_resolver.resolve(candidate)
            group_key = (identity.brand.casefold(), identity.identity_key)
            grouped.setdefault(group_key, []).append((candidate, identity))

        merged_success = [self._merge_group(group) for group in grouped.values()]
        return merged_success + passthrough

    def _merge_group(
        self,
        group: list[tuple[DiscoveryCandidateResult, ProductIdentity]],
    ) -> DiscoveryCandidateResult:
        winner, identity = max(group, key=self._candidate_rank_key)
        best_market_confidence = max(
            (
                candidate.market_evaluation.confidence_score
                if candidate.market_evaluation is not None
                else 0.0
                for candidate, _ in group
            ),
            default=0.0,
        )
        best_demand_score = max(
            (float(candidate.metadata.get("demand_score", 0.0)) for candidate, _ in group),
            default=0.0,
        )
        merged_metadata = dict(winner.metadata)
        merged_metadata.update(
            {
                "identity_key": identity.identity_key,
                "merged_candidate_count": len(group),
                "merged_external_ids": tuple(candidate.supplier_product.external_id for candidate, _ in group),
                "best_market_confidence": best_market_confidence,
                "best_demand_score": best_demand_score,
            }
        )
        return replace(winner, metadata=merged_metadata)

    @staticmethod
    def _candidate_rank_key(
        item: tuple[DiscoveryCandidateResult, ProductIdentity],
    ) -> tuple[float, float]:
        candidate, _ = item
        profit_jpy = float(candidate.profit_result.profit_jpy) if candidate.profit_result is not None else 0.0
        market_confidence = (
            candidate.market_evaluation.confidence_score if candidate.market_evaluation is not None else 0.0
        )
        return profit_jpy, market_confidence
