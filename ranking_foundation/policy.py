"""Configurable ranking policy and weights."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from price_compare.profit_config import ProfitConfig


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    """Configurable weights for ranking signal components."""

    profit_margin_weight: Decimal = Decimal("0.4")
    roi_weight: Decimal = Decimal("0.4")
    profit_jpy_weight: Decimal = Decimal("0.2")
    identity_confidence_weight: Decimal = Decimal("0")
    import_cost_weight: Decimal = Decimal("0")
    marketplace_confidence_weight: Decimal = Decimal("0")

    @classmethod
    def default(cls) -> RankingPolicy:
        """Return default Version1 ranking policy."""
        return cls()

    @classmethod
    def from_profit_config(cls, config: ProfitConfig) -> RankingPolicy:
        """Build ranking policy from legacy ProfitConfig weight fields."""
        return cls(
            profit_margin_weight=config.ranking_score_profit_margin_weight,
            roi_weight=config.ranking_score_roi_weight,
            profit_jpy_weight=config.ranking_score_profit_jpy_weight,
            identity_confidence_weight=config.ranking_score_identity_confidence_weight,
            import_cost_weight=config.ranking_score_import_cost_weight,
            marketplace_confidence_weight=config.ranking_score_marketplace_confidence_weight,
        )

    def legacy_only(self) -> bool:
        """Return True when only legacy profit signals contribute to the score."""
        return (
            self.identity_confidence_weight == Decimal("0")
            and self.import_cost_weight == Decimal("0")
            and self.marketplace_confidence_weight == Decimal("0")
        )
