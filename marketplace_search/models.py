"""Canonical marketplace search request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.marketplace_search_result import (
    SEARCH_ERROR,
    MarketplaceSearchResult,
)
from models.product import Product


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Canonical input for marketplace search operations."""

    product: Product
    marketplace_id: str
    query: str | None = None
    page: int = 1
    page_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_product(
        cls,
        product: Product,
        marketplace_id: str,
        *,
        query: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> SearchRequest:
        """Build a search request for one product on one marketplace."""
        return cls(
            product=product,
            marketplace_id=marketplace_id,
            query=query,
            page=page,
            page_size=page_size,
        )

    def resolved_query(self) -> str:
        """Return explicit query or a deterministic fallback from product fields."""
        if self.query and self.query.strip():
            return self.query.strip()
        for value in (self.product.sku, self.product.model, self.product.name, self.product.brand):
            if value and str(value).strip():
                return str(value).strip()
        return ""


@dataclass(frozen=True, slots=True)
class SearchValidationResult:
    """Outcome of search request validation."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Canonical output for marketplace search operations."""

    request: SearchRequest
    marketplace_result: MarketplaceSearchResult
    validation: SearchValidationResult

    @property
    def status(self) -> str:
        """Return the legacy marketplace search status string."""
        return self.marketplace_result.status

    @property
    def marketplace_name(self) -> str:
        """Return the marketplace identifier for this search result."""
        return self.marketplace_result.marketplace_name

    @property
    def listings(self):
        """Return all listings returned by the marketplace search."""
        return self.marketplace_result.listings

    @property
    def valid_listings(self):
        """Return listings that passed local validation rules."""
        return self.marketplace_result.valid_listings

    def to_marketplace_search_result(self) -> MarketplaceSearchResult:
        """Return the legacy search result consumed by existing pipelines."""
        return self.marketplace_result

    @classmethod
    def from_marketplace_search_result(
        cls,
        request: SearchRequest,
        marketplace_result: MarketplaceSearchResult,
        *,
        validation: SearchValidationResult | None = None,
    ) -> SearchResult:
        return cls(
            request=request,
            marketplace_result=marketplace_result,
            validation=validation or SearchValidationResult(valid=True),
        )

    @classmethod
    def validation_error(
        cls,
        request: SearchRequest,
        validation: SearchValidationResult,
    ) -> SearchResult:
        message = "; ".join(validation.errors) or "invalid search request"
        legacy = MarketplaceSearchResult(
            product=request.product,
            query=request.resolved_query(),
            marketplace_name=request.marketplace_id,
            status=SEARCH_ERROR,
            error_message=message,
        )
        return cls(request=request, marketplace_result=legacy, validation=validation)
