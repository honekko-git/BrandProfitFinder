"""
Configuration for cross-marketplace comparison.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from config import settings
from price_compare.price_comparator import PriceSelectionStrategy


@dataclass(frozen=True)
class ComparisonConfig:
    """
    Settings for deterministic cross-marketplace comparison.

    ``profit_selection_strategy`` and ``include_invalid_calculations`` are
    loaded for configuration parity but are not yet applied by the comparison
    service. Listing selection remains marketplace-adapter responsibility.
    """

    min_match_score: Decimal = Decimal("30")
    require_identity_match: bool = True
    profit_selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST
    include_invalid_calculations: bool = False
    expected_marketplaces: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> "ComparisonConfig":
        """Load comparison settings from application configuration."""
        raw = settings.COMPARISON_EXPECTED_MARKETPLACES.strip()
        expected = tuple(
            part.strip().lower()
            for part in raw.split(",")
            if part.strip()
        )
        return cls(
            min_match_score=Decimal(str(settings.COMPARISON_MIN_MATCH_SCORE)),
            require_identity_match=settings.COMPARISON_REQUIRE_IDENTITY_MATCH,
            include_invalid_calculations=settings.COMPARISON_INCLUDE_INVALID,
            expected_marketplaces=expected,
        )
