"""Extract placeholder market signals from listing metadata."""

from __future__ import annotations

from typing import Any, Mapping

from market_intelligence.models import MarketSignals
from models.marketplace_listing import MarketplaceListing

_SIGNAL_KEYS = (
    "competition_score",
    "price_stability_score",
    "demand_score",
    "inventory_risk_score",
    "confidence_score",
    "market_signal_confidence_score",
)


def extract_market_signals(
    listing: MarketplaceListing | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MarketSignals:
    """
    Extract market signals from listing metadata using marketplace-neutral keys.

    Phase 26A returns placeholder defaults. Pre-populated standard keys are passed
    through when already present on the listing metadata contract.

    Args:
        listing: Optional marketplace listing source.
        metadata: Optional metadata mapping override.

    Returns:
        MarketSignals with None defaults or passthrough values.
    """
    source = dict(metadata or {})
    if listing is not None and listing.source_metadata:
        source = {**listing.source_metadata, **source}

    confidence = _optional_float(source.get("market_signal_confidence_score"))
    if confidence is None:
        confidence = _optional_float(source.get("confidence_score"))

    return MarketSignals(
        competition_score=_optional_float(source.get("competition_score")),
        price_stability_score=_optional_float(source.get("price_stability_score")),
        demand_score=_optional_float(source.get("demand_score")),
        inventory_risk_score=_optional_float(source.get("inventory_risk_score")),
        confidence_score=confidence,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
