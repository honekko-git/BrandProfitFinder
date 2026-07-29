"""Marketplace-independent competition opportunity scoring."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from market_intelligence.models import MarketSignals
from models.marketplace_listing import MarketplaceListing
from profit_intelligence.discovery_models import ComponentScore
from profit_intelligence.normalization import clamp_score, normalize_optional_int

NEUTRAL_SCORE = 50.0


def score_competition(
    signals: MarketSignals | None = None,
    listings: Sequence[MarketplaceListing] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ComponentScore:
    """
    Score competition as business opportunity (higher score = lower competition).

    Uses market signals, listing count, and price spread when available.
    Missing data returns a neutral score and never raises.
    """
    reasons: list[str] = []
    warnings: list[str] = []
    meta = dict(metadata or {})

    if signals is not None and signals.competition_score is not None:
        intensity = clamp_score(float(signals.competition_score))
        opportunity = clamp_score(100.0 - intensity)
        if opportunity >= 70:
            reasons.append("Low competition.")
        elif opportunity <= 35:
            reasons.append("High competition.")
        else:
            reasons.append("Moderate competition.")
        return ComponentScore(score=opportunity, reasons=tuple(reasons), warnings=tuple(warnings))

    listing_count = _resolve_listing_count(listings, meta)
    price_spread = _resolve_price_spread(listings, meta)

    if listing_count is None and price_spread is None:
        warnings.append("Competition data unavailable.")
        return ComponentScore(score=NEUTRAL_SCORE, reasons=tuple(), warnings=tuple(warnings))

    score = NEUTRAL_SCORE

    if listing_count is not None:
        if listing_count <= 2:
            score = 90.0
            reasons.append("Low competition.")
        elif listing_count <= 5:
            score = 65.0
            reasons.append("Moderate competition.")
        elif listing_count <= 9:
            score = 40.0
            reasons.append("High competition.")
        else:
            score = 20.0
            reasons.append("High competition.")

    if price_spread is not None:
        spread_adjustment = _price_spread_adjustment(price_spread)
        if listing_count is None:
            score = spread_adjustment
        elif listing_count <= 5:
            score = clamp_score((score + spread_adjustment) / 2.0)
        if spread_adjustment >= 70 and listing_count is not None and listing_count <= 5:
            reasons.append("Wide price spread suggests differentiation opportunity.")
        elif spread_adjustment <= 35 and "High competition." not in reasons:
            reasons.append("Tight price spread suggests crowded market.")

    return ComponentScore(score=clamp_score(score), reasons=tuple(reasons), warnings=tuple(warnings))


def _resolve_listing_count(
    listings: Sequence[MarketplaceListing] | None,
    metadata: Mapping[str, Any],
) -> int | None:
    if listings is not None:
        count = len(listings)
        return count if count > 0 else None
    return normalize_optional_int(metadata.get("listing_count"))


def _resolve_price_spread(
    listings: Sequence[MarketplaceListing] | None,
    metadata: Mapping[str, Any],
) -> float | None:
    prices: list[float] = []
    if listings:
        for listing in listings:
            value = _listing_price(listing)
            if value is not None:
                prices.append(value)

    if len(prices) >= 2:
        return _spread_ratio(prices)

    raw_spread = metadata.get("price_spread_ratio")
    if raw_spread is None:
        return None
    try:
        spread = float(raw_spread)
    except (TypeError, ValueError):
        return None
    return spread if spread >= 0 else None


def _listing_price(listing: MarketplaceListing) -> float | None:
    price = listing.price_jpy
    if price is None:
        return None
    return float(price)


def _spread_ratio(prices: list[float]) -> float:
    minimum = min(prices)
    maximum = max(prices)
    if minimum <= 0:
        return 0.0
    return (maximum - minimum) / minimum


def _price_spread_adjustment(spread_ratio: float) -> float:
    if spread_ratio >= 0.5:
        return 85.0
    if spread_ratio >= 0.25:
        return 65.0
    if spread_ratio >= 0.1:
        return 45.0
    return 25.0
