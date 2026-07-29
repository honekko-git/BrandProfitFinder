"""Multi supplier discovery orchestration service."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import BatchDiscoveryResult, DiscoveryCandidateResult
from profit_discovery.discovery_runner.ranking import rank_discovery_results
from profit_discovery.discovery_runner.runner import DiscoveryRunner
from profit_discovery.supplier_discovery.models import (
    MultiSupplierDiscoveryResult,
    SupplierDiscoveryResult,
    SupplierDiscoverySource,
)


class MultiSupplierDiscoveryService:
    """Evaluate products from multiple supplier sources through one discovery pipeline."""

    def __init__(
        self,
        *,
        sources: list[SupplierDiscoverySource],
        discovery_runner: DiscoveryRunner,
    ) -> None:
        self._sources = tuple(sources)
        self._discovery_runner = discovery_runner

    @property
    def sources(self) -> tuple[SupplierDiscoverySource, ...]:
        return self._sources

    @property
    def discovery_runner(self) -> DiscoveryRunner:
        return self._discovery_runner

    def run(
        self,
        *,
        query: str = "",
        page: int = 1,
        max_results: int = 20,
    ) -> MultiSupplierDiscoveryResult:
        """Run discovery across all enabled supplier sources."""
        source_results: list[SupplierDiscoveryResult] = []
        merged_candidates: list[DiscoveryCandidateResult] = []
        total_products = 0

        for source in self._sources:
            if not source.enabled:
                source_results.append(
                    SupplierDiscoveryResult(
                        source_name=source.supplier_name,
                        batch_result=None,
                        metadata={"status": "DISABLED"},
                    )
                )
                continue

            try:
                products = source.client.search_products(
                    query,
                    page=page,
                    max_results=max_results,
                )
                batch_result = self._discovery_runner.evaluate_products(products)
                source_results.append(
                    SupplierDiscoveryResult(
                        source_name=source.supplier_name,
                        batch_result=batch_result,
                        metadata={"status": "SUCCESS", "product_count": len(products)},
                    )
                )
                total_products += batch_result.total_products
                merged_candidates.extend(batch_result.results)
            except Exception as exc:
                source_results.append(
                    SupplierDiscoveryResult(
                        source_name=source.supplier_name,
                        batch_result=None,
                        metadata={"status": "ERROR", "error": str(exc)},
                    )
                )

        ranked_candidates = tuple(rank_discovery_results(merged_candidates))
        enabled_sources = sum(1 for source in self._sources if source.enabled)

        return MultiSupplierDiscoveryResult(
            total_sources=enabled_sources,
            total_products=total_products,
            results=tuple(source_results),
            ranked_candidates=ranked_candidates,
            metadata={"query": query, "page": page, "max_results": max_results},
        )
