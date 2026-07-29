"""Search request validation policy."""

from __future__ import annotations

from marketplace_search.capability import MarketplaceCapability
from marketplace_search.models import SearchRequest, SearchValidationResult


class SearchPolicy:
    """Validate search requests against marketplace capabilities."""

    def validate(
        self,
        request: SearchRequest,
        capability: MarketplaceCapability,
    ) -> SearchValidationResult:
        """Return validation outcome for a search request."""
        errors: list[str] = []
        warnings: list[str] = []

        if request.product is None:
            errors.append("product is required")

        marketplace_id = request.marketplace_id.strip()
        if not marketplace_id:
            errors.append("marketplace_id is required")
        elif marketplace_id != capability.marketplace_id:
            errors.append(
                f"marketplace_id mismatch: request={marketplace_id} adapter={capability.marketplace_id}",
            )

        if request.page < 1:
            errors.append("page must be greater than or equal to 1")

        if request.page_size is not None:
            if request.page_size < 1:
                errors.append("page_size must be greater than or equal to 1")
            elif request.page_size > capability.max_page_size:
                errors.append(
                    f"page_size exceeds marketplace maximum ({request.page_size} > {capability.max_page_size})",
                )

        if not capability.supports_pagination and request.page > 1:
            errors.append("marketplace does not support pagination")

        resolved_query = request.resolved_query()
        if not resolved_query:
            errors.append("search query or product identifier is required")
        elif request.query is None:
            if resolved_query == (request.product.sku or "").strip() and capability.supports_sku_search:
                pass
            elif resolved_query == (request.product.model or "").strip() and capability.supports_model_search:
                pass
            elif capability.supports_text_search:
                pass
            else:
                errors.append("marketplace does not support inferred product search")

        if capability.requires_configured_client:
            warnings.append("adapter requires configured client; search may fail without demo client")

        return SearchValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
