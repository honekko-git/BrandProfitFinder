"""Cross-marketplace comparison foundation.

Public exports are limited to orchestration entry points and core result models.
"""

from comparison.models import (
    ComparisonRunResult,
    MarketplaceCandidate,
    ProductComparisonResult,
)
from comparison.service import CrossMarketplaceComparisonService

__all__ = [
    "ComparisonRunResult",
    "CrossMarketplaceComparisonService",
    "MarketplaceCandidate",
    "ProductComparisonResult",
]
