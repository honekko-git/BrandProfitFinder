"""
Cross-marketplace comparison data models.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from product_identity.models import ProductIdentityResult


@dataclass
class MarketplaceCandidate:
    """One marketplace outcome considered in a product comparison."""

    marketplace_name: str
    search_result: MarketplaceSearchResult
    price_result: PriceResult
    match_score: Decimal | None = None
    match_warnings: list[str] = field(default_factory=list)
    listing_currency: str | None = None
    source_price_amount: Decimal | None = None
    jpy_comparable: bool = False
    order_index: int = 0
    identity_matched: bool = True
    identity_listing: MarketplaceListing | None = None
    identity_result: ProductIdentityResult | None = None

    @property
    def identity_decision(self) -> str | None:
        """Return identity decision text when evaluated."""
        return self.identity_result.decision.value if self.identity_result else None

    @property
    def identity_review_required(self) -> bool | None:
        """Return review requirement when identity was evaluated."""
        if self.identity_result is None:
            return None
        return self.identity_result.review_required

    @property
    def is_comparable(self) -> bool:
        """
        Return True when the candidate has an authoritative JPY-comparable profit result.

        Non-JPY listings without conversion remain non-comparable even if numeric fields exist.
        """
        return (
            self.identity_matched
            and self.jpy_comparable
            and self.price_result.calculation_status == CALCULATION_SUCCESS
            and self.price_result.is_valid
        )

    @property
    def comparable_profit_jpy(self) -> Decimal | None:
        """Return profit only when JPY-comparable; otherwise None (never zero as substitute)."""
        if not self.is_comparable:
            return None
        return self.price_result.profit_jpy

    @property
    def comparable_profit_margin(self) -> Decimal | None:
        """Return margin only when JPY-comparable; otherwise None."""
        if not self.is_comparable:
            return None
        return self.price_result.profit_margin


@dataclass
class ProductComparisonResult:
    """Comparison summary for one product across marketplaces."""

    product: Product
    candidates: list[MarketplaceCandidate] = field(default_factory=list)
    selected_review_marketplace: str | None = None
    selected_review_profit_jpy: Decimal | None = None
    selected_review_margin: Decimal | None = None
    highest_profit_marketplace: str | None = None
    highest_profit_jpy: Decimal | None = None
    highest_profit_margin: Decimal | None = None
    best_confidence_score: float | None = None
    best_data_completeness: float | None = None
    best_overall_score: float | None = None
    best_risk_score: float | None = None
    supported_marketplaces: list[str] = field(default_factory=list)
    missing_marketplaces: list[str] = field(default_factory=list)
    currencies_observed: list[str] = field(default_factory=list)
    currency_consistent: bool | None = None
    price_consistent: bool | None = None
    warnings: list[str] = field(default_factory=list)
    validation_summary: str = ""
    comparison_reliability: str = "insufficient"
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def marketplaces_compared(self) -> list[str]:
        """Return marketplace names that returned any search outcome."""
        return [candidate.marketplace_name for candidate in self.candidates]

    @property
    def comparable_count(self) -> int:
        """Return count of candidates with authoritative JPY-comparable profit."""
        return sum(1 for candidate in self.candidates if candidate.is_comparable)

    @property
    def selected_review_profit_margin(self) -> Decimal | None:
        """Preferred alias for selected_review_margin."""
        return self.selected_review_margin

    @property
    def best_marketplace(self) -> str | None:
        """Compatibility alias for selected_review_marketplace."""
        return self.selected_review_marketplace

    @property
    def best_profit_jpy(self) -> Decimal | None:
        """Compatibility alias for selected_review_profit_jpy."""
        return self.selected_review_profit_jpy

    @property
    def best_profit_margin(self) -> Decimal | None:
        """Compatibility alias for selected_review_margin."""
        return self.selected_review_margin


@dataclass
class ComparisonRunResult:
    """Full comparison run across products and marketplaces."""

    products: list[ProductComparisonResult] = field(default_factory=list)
    all_search_results: list[MarketplaceSearchResult] = field(default_factory=list)
    all_listings: list[MarketplaceListing] = field(default_factory=list)
    ranked_price_results: list[PriceResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
