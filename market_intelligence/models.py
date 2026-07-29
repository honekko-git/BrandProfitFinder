"""Marketplace-independent market signal models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketSignals:
    """
    Normalized marketplace-independent market context signals.

    Values are optional until real scoring is implemented in a later phase.
    """

    competition_score: float | None = None
    price_stability_score: float | None = None
    demand_score: float | None = None
    inventory_risk_score: float | None = None
    confidence_score: float | None = None

    def to_metadata(self) -> dict[str, float | None]:
        """Serialize signal fields for PriceResult.metadata attachment."""
        return {
            "competition_score": self.competition_score,
            "price_stability_score": self.price_stability_score,
            "demand_score": self.demand_score,
            "inventory_risk_score": self.inventory_risk_score,
            "market_signal_confidence_score": self.confidence_score,
        }
