"""Search query generation for Yahoo Auction live sold lookup.

Delegates to the marketplace-neutral domestic query contract so Yahoo and
Mercari share identical identity-first query tiers.
"""

from __future__ import annotations

import re

from marketplace.browser_acquisition.domestic_search_queries import (
    BRAND_JA,
    CATEGORY_JA,
    COLOR_MAP,
    MATERIAL_MAP,
    MAX_SEARCH_QUERIES,
    STATUS_NO_SAFE_QUERY,
    build_domestic_search_queries,
)
from marketplace.browser_acquisition.listing_identity import ListingIdentity, extract_listing_identity

# Bag model-family path may return up to 4; wallet/identity path stays at 3.
MAX_IDENTITY_SEARCH_QUERIES = 3

# Re-export maps for callers / tests that imported them from this module.
__all__ = [
    "MAX_SEARCH_QUERIES",
    "MAX_IDENTITY_SEARCH_QUERIES",
    "BRAND_JA",
    "CATEGORY_JA",
    "COLOR_MAP",
    "MATERIAL_MAP",
    "build_yahoo_search_queries",
    "build_yahoo_identity_queries",
    "build_yahoo_search_query_result",
]


def build_yahoo_search_query_result(*, title: str, brand: str, category: str):
    """Return full QueryGenerationResult for Yahoo (and shared tracing)."""
    return build_domestic_search_queries(title=title, brand=brand, category=category)


def build_yahoo_search_queries(*, title: str, brand: str, category: str) -> list[str]:
    """Build Yahoo search queries prioritizing reference / model identity."""
    result = build_domestic_search_queries(title=title, brand=brand, category=category)
    return result.query_strings


def build_yahoo_identity_queries(
    *,
    identity: ListingIdentity,
    title: str = "",
    brand: str = "",
    category: str = "",
) -> list[str]:
    """Build Yahoo queries from normalized listing identity.

    Kept for callers that already hold a ListingIdentity. Prefer
    build_yahoo_search_queries for new code paths.
    """
    result = build_domestic_search_queries(
        title=title or identity.cleaned_title,
        brand=brand or identity.brand,
        category=category or identity.category,
    )
    return result.query_strings[:MAX_IDENTITY_SEARCH_QUERIES]


def _legacy_query(*, title: str, brand: str, category: str) -> str:
    tokens = set(re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", f"{title} {brand} {category}".lower()))
    noise = {"fashionphile", "authenticated", "authentic", "excellent", "very", "good", "condition", "used"}
    filtered = [token for token in sorted(tokens) if token not in noise and len(token) > 1]
    return " ".join(filtered[:8])


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())
