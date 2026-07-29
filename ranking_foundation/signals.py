"""Ranking signal extraction from price results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from models.price_result import PriceResult
from ranking_foundation.context import RankingBatchContext

IDENTITY_CONFIDENCE_MAP: dict[str, Decimal] = {
    "HIGH": Decimal("100"),
    "MEDIUM": Decimal("66"),
    "LOW": Decimal("33"),
    "UNKNOWN": Decimal("0"),
}


def identity_confidence_from_label(label: str) -> Decimal | None:
    """Map an identity confidence label to its canonical score."""
    return IDENTITY_CONFIDENCE_MAP.get(label.upper())


@dataclass(frozen=True, slots=True)
class RankingSignals:
    """Normalized ranking inputs for one price result."""

    profit_margin: Decimal
    roi: Decimal
    normalized_profit_jpy: Decimal
    identity_confidence: Decimal
    import_cost_score: Decimal
    marketplace_confidence: Decimal


def extract_ranking_signals(result: PriceResult, batch: RankingBatchContext) -> RankingSignals:
    """Extract deterministic ranking signals without mutating the result."""
    profit_margin = _decimal_or_zero(result.profit_margin)
    roi = _decimal_or_zero(result.roi)
    normalized_profit = _normalize_value(result.profit_jpy, batch.max_profit_jpy)
    import_cost_score = _inverse_normalize_value(result.total_cost_jpy, batch.max_total_cost_jpy)
    identity_confidence = _identity_confidence_score(result)
    marketplace_confidence = _marketplace_confidence_score(result)
    return RankingSignals(
        profit_margin=profit_margin,
        roi=roi,
        normalized_profit_jpy=normalized_profit,
        identity_confidence=identity_confidence,
        import_cost_score=import_cost_score,
        marketplace_confidence=marketplace_confidence,
    )


def _identity_confidence_score(result: PriceResult) -> Decimal:
    metadata = result.metadata or {}
    explicit = metadata.get("identity_confidence_score")
    if explicit is not None:
        return _clamp_score(_to_decimal(explicit))

    label = metadata.get("selected_review_identity_confidence")
    if isinstance(label, str):
        mapped = identity_confidence_from_label(label)
        if mapped is not None:
            return mapped

    intel = result.profit_intelligence
    if intel is not None and intel.confidence_score is not None:
        return _clamp_score(Decimal(str(intel.confidence_score)))

    strength = metadata.get("identifier_match_strength")
    if strength is not None:
        return _clamp_score(_to_decimal(strength) * Decimal("100"))

    return Decimal("0")


def _marketplace_confidence_score(result: PriceResult) -> Decimal:
    metadata = result.metadata or {}
    completeness = metadata.get("data_completeness")
    if completeness is not None:
        value = _to_decimal(completeness)
        if value <= Decimal("1"):
            return _clamp_score(value * Decimal("100"))
        return _clamp_score(value)

    intel = result.profit_intelligence
    if intel is not None and intel.confidence_score is not None:
        return _clamp_score(Decimal(str(intel.confidence_score)))

    return Decimal("0")


def _normalize_value(value: Decimal | None, maximum: Decimal) -> Decimal:
    amount = _decimal_or_zero(value)
    if maximum <= 0:
        return Decimal("0")
    return (amount / maximum) * Decimal("100")


def _inverse_normalize_value(value: Decimal | None, maximum: Decimal) -> Decimal:
    amount = _decimal_or_zero(value)
    if maximum <= 0 or amount <= 0:
        return Decimal("0")
    return (Decimal("1") - (amount / maximum)) * Decimal("100")


def _decimal_or_zero(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _clamp_score(value: Decimal) -> Decimal:
    if value < Decimal("0"):
        return Decimal("0")
    if value > Decimal("100"):
        return Decimal("100")
    return value
