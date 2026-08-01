"""Search query generation for Mercari live lookup.

Reuses the marketplace-neutral domestic query contract so Mercari and Yahoo
search from identical listing identity signals.
"""

from __future__ import annotations

from marketplace.browser_acquisition.domestic_search_queries import MAX_SEARCH_QUERIES, build_domestic_search_queries
from marketplace.browser_acquisition.listing_identity import ListingIdentity
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_identity_queries

__all__ = [
    "MAX_SEARCH_QUERIES",
    "build_mercari_identity_queries",
    "build_mercari_search_queries",
    "build_mercari_search_query_result",
]


def build_mercari_search_query_result(*, title: str, brand: str, category: str):
    """Return full QueryGenerationResult for Mercari tracing."""
    return build_domestic_search_queries(title=title, brand=brand, category=category)


def build_mercari_search_queries(*, title: str, brand: str, category: str) -> list[str]:
    """Build up to MAX_SEARCH_QUERIES Mercari search queries from title/brand/category."""
    return build_domestic_search_queries(title=title, brand=brand, category=category).query_strings


def build_mercari_identity_queries(
    *,
    identity: ListingIdentity,
    title: str = "",
    brand: str = "",
    category: str = "",
) -> list[str]:
    """Build Mercari queries from normalized listing identity."""
    return build_yahoo_identity_queries(
        identity=identity,
        title=title,
        brand=brand,
        category=category,
    )
