"""Marketplace search routing service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marketplace_search.models import SearchRequest, SearchResult
from marketplace_search.policy import SearchPolicy

if TYPE_CHECKING:
    from marketplace.adapter import MarketplaceAdapter


class MarketplaceSearchService:
    """Route validated search requests through marketplace adapters."""

    def __init__(self, policy: SearchPolicy | None = None) -> None:
        self._policy = policy or SearchPolicy()

    def search(self, adapter: MarketplaceAdapter, request: SearchRequest) -> SearchResult:
        """
        Execute a search through the adapter after policy validation.

        Does not mutate the request product or adapter instance.
        """
        capability = adapter.capability
        validation = self._policy.validate(request, capability)
        if not validation.valid:
            return SearchResult.validation_error(request, validation)

        legacy_result = adapter.search(request.product, request.query)
        return SearchResult.from_marketplace_search_result(
            request,
            legacy_result,
            validation=validation,
        )

    def search_many(
        self,
        adapter: MarketplaceAdapter,
        requests: list[SearchRequest],
    ) -> list[SearchResult]:
        """Execute multiple search requests in order."""
        return [self.search(adapter, request) for request in requests]
