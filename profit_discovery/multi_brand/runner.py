"""Multi-brand discovery orchestration."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.discovery_runner.ranking import rank_discovery_results
from profit_discovery.discovery_runner.runner import DiscoveryRunner
from profit_discovery.multi_brand.models import (
    BrandDiscoveryResult,
    MultiBrandDiscoveryRequest,
    MultiBrandDiscoveryResult,
)
from profit_discovery.opportunity import OpportunityResult, OpportunityScorer, rank_opportunities


class MultiBrandDiscoveryRunner:
    """Run the existing discovery pipeline once per brand and merge the results."""

    def __init__(self, *, discovery_runner: DiscoveryRunner) -> None:
        self._discovery_runner = discovery_runner

    @property
    def discovery_runner(self) -> DiscoveryRunner:
        return self._discovery_runner

    def run(self, request: MultiBrandDiscoveryRequest) -> MultiBrandDiscoveryResult:
        """Evaluate each brand independently without stopping on individual brand failures."""
        brand_results: list[BrandDiscoveryResult] = []
        merged_candidates: list[DiscoveryCandidateResult] = []
        successful_brands: list[str] = []
        failed_brands: list[str] = []

        search_targets = request.search_targets
        if search_targets:
            iteration = [
                (target.brand, target.query, target.category)
                for target in search_targets
            ]
        else:
            iteration = [
                (
                    brand,
                    _build_brand_query(
                        brand,
                        keyword=request.keyword,
                        category=request.category,
                    ),
                    request.category,
                )
                for brand in request.brands
            ]

        for brand, query, category in iteration:
            try:
                products = self._discovery_runner.supplier_client.search_products(
                    query,
                    max_results=request.max_results_per_brand,
                )
                batch_result = self._discovery_runner.evaluate_products(products)
                brand_results.append(
                    BrandDiscoveryResult(
                        brand=brand,
                        batch_result=batch_result,
                        metadata={
                            "status": "SUCCESS",
                            "product_count": len(products),
                            "query": query,
                            "category": category,
                        },
                    )
                )
                if brand not in successful_brands:
                    successful_brands.append(brand)
                merged_candidates.extend(batch_result.results)
            except Exception as exc:
                brand_results.append(
                    BrandDiscoveryResult(
                        brand=brand,
                        batch_result=None,
                        metadata={
                            "status": "ERROR",
                            "error": str(exc),
                            "query": query,
                            "category": category,
                        },
                    )
                )
                if brand not in failed_brands:
                    failed_brands.append(brand)

        ranked_candidates = tuple(rank_discovery_results(merged_candidates))
        ranked_opportunities = _build_ranked_opportunities(ranked_candidates)

        return MultiBrandDiscoveryResult(
            results=tuple(brand_results),
            ranked_candidates=ranked_candidates,
            ranked_opportunities=ranked_opportunities,
            successful_brands=tuple(successful_brands),
            failed_brands=tuple(failed_brands),
            total_candidates=len(merged_candidates),
            metadata={
                "category": request.category,
                "keyword": request.keyword,
                "max_results_per_brand": request.max_results_per_brand,
                "search_target_count": len(search_targets) if search_targets else 0,
            },
        )


def _build_ranked_opportunities(
    candidates: tuple[DiscoveryCandidateResult, ...] | list[DiscoveryCandidateResult],
) -> tuple[OpportunityResult, ...]:
    """Score and rank successful discovery candidates by purchase priority."""
    scorer = OpportunityScorer()
    successful_candidates = [
        candidate
        for candidate in candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    ]
    opportunities = [scorer.evaluate(candidate) for candidate in successful_candidates]
    return tuple(rank_opportunities(opportunities))


def _build_brand_query(
    brand: str,
    *,
    keyword: str | None,
    category: str | None,
) -> str:
    parts = [brand.strip()]
    if keyword:
        parts.append(keyword.strip())
    if category:
        parts.append(category.strip())
    return " ".join(part for part in parts if part)
