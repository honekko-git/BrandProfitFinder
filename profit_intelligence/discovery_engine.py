"""Profit discovery scoring engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from market_intelligence.competition_scorer import score_competition
from market_intelligence.extractor import extract_market_signals
from market_intelligence.models import MarketSignals
from models.marketplace_listing import MarketplaceListing
from models.price_result import PriceResult
from profit_intelligence.discovery_models import ComponentScore, DiscoveryScore
from profit_intelligence.normalization import clamp_score, dedupe_preserve_order
from profit_intelligence.scorers.brand_scorer import BrandScorer
from profit_intelligence.scorers.demand_scorer import DemandScorer
from profit_intelligence.scorers.profit_scorer import DiscoveryProfitScorer, NEUTRAL_SCORE

DEFAULT_WEIGHTS = {
    "profit": 0.40,
    "demand": 0.20,
    "brand": 0.15,
    "competition": 0.15,
    "confidence": 0.10,
}


@dataclass(frozen=True, slots=True)
class DiscoveryWeights:
    """Deterministic component weights for overall discovery scoring."""

    profit: float = DEFAULT_WEIGHTS["profit"]
    demand: float = DEFAULT_WEIGHTS["demand"]
    brand: float = DEFAULT_WEIGHTS["brand"]
    competition: float = DEFAULT_WEIGHTS["competition"]
    confidence: float = DEFAULT_WEIGHTS["confidence"]


class DiscoveryEngine:
    """Combine discovery component scorers into one explainable DiscoveryScore."""

    def __init__(
        self,
        *,
        weights: DiscoveryWeights | None = None,
        profit_scorer: DiscoveryProfitScorer | None = None,
        demand_scorer: DemandScorer | None = None,
        brand_scorer: BrandScorer | None = None,
    ) -> None:
        self.weights = weights or DiscoveryWeights()
        self.profit_scorer = profit_scorer or DiscoveryProfitScorer()
        self.demand_scorer = demand_scorer or DemandScorer()
        self.brand_scorer = brand_scorer or BrandScorer()

    def score(
        self,
        result: PriceResult,
        *,
        market_signals: MarketSignals | None = None,
        listings: Sequence[MarketplaceListing] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DiscoveryScore:
        """
        Score one price result without mutating profit fields.

        Args:
            result: Calculated profit result with optional discovery metadata attached.
            market_signals: Optional pre-extracted market signals.
            listings: Optional listing set for competition analysis.
            metadata: Optional metadata override.

        Returns:
            DiscoveryScore with component and overall scores.
        """
        meta = dict(metadata or result.metadata or {})
        signals = market_signals or extract_market_signals(metadata=meta)

        profit = self.profit_scorer.score(result)
        demand = self.demand_scorer.score(signals, meta)
        brand = self.brand_scorer.score(meta)
        competition = score_competition(signals, listings, meta)
        confidence = self._score_confidence(meta)

        overall = self._weighted_overall(
            profit=profit.score,
            demand=demand.score,
            brand=brand.score,
            competition=competition.score,
            confidence=confidence.score,
        )

        reasons = dedupe_preserve_order(
            list(profit.reasons)
            + list(demand.reasons)
            + list(brand.reasons)
            + list(competition.reasons)
            + list(confidence.reasons)
        )
        warnings = dedupe_preserve_order(
            list(profit.warnings)
            + list(demand.warnings)
            + list(brand.warnings)
            + list(competition.warnings)
            + list(confidence.warnings)
        )

        if overall >= 80:
            reasons = dedupe_preserve_order(["Strong business opportunity.", *list(reasons)])

        return DiscoveryScore(
            profit_score=profit.score,
            demand_score=demand.score,
            brand_score=brand.score,
            competition_score=competition.score,
            confidence_score=confidence.score,
            overall_score=overall,
            reasons=reasons,
            warnings=warnings,
        )

    def score_results(
        self,
        results: list[PriceResult],
        *,
        listings_by_index: Sequence[Sequence[MarketplaceListing] | None] | None = None,
    ) -> list[DiscoveryScore]:
        """Score multiple price results without mutating profit fields."""
        scores: list[DiscoveryScore] = []
        for index, result in enumerate(results):
            listings = None
            if listings_by_index is not None and index < len(listings_by_index):
                listings = listings_by_index[index]
            scores.append(self.score(result, listings=listings))
        return scores

    def _weighted_overall(
        self,
        *,
        profit: float,
        demand: float,
        brand: float,
        competition: float,
        confidence: float,
    ) -> float:
        weights = self.weights
        total = (
            profit * weights.profit
            + demand * weights.demand
            + brand * weights.brand
            + competition * weights.competition
            + confidence * weights.confidence
        )
        return clamp_score(total)

    def _score_confidence(self, metadata: Mapping[str, Any]) -> ComponentScore:
        reasons: list[str] = []
        warnings: list[str] = []
        raw = metadata.get("identity_confidence_score")
        if raw is None:
            warnings.append("Identity confidence unavailable.")
            return ComponentScore(score=NEUTRAL_SCORE, warnings=tuple(warnings))

        try:
            value = float(raw)
        except (TypeError, ValueError):
            warnings.append("Identity confidence unavailable.")
            return ComponentScore(score=NEUTRAL_SCORE, warnings=tuple(warnings))

        score = clamp_score(value * 100.0 if value <= 1.0 else value)
        if score >= 80:
            reasons.append("Strong identity confidence.")
        elif score >= 50:
            reasons.append("Moderate identity confidence.")
        else:
            reasons.append("Limited identity confidence.")
        return ComponentScore(score=score, reasons=tuple(reasons), warnings=tuple(warnings))


def attach_discovery_score_metadata(result: PriceResult, discovery: DiscoveryScore) -> None:
    """Attach discovery score fields to result metadata without changing profit numbers."""
    result.metadata.update(
        {
            "discovery_profit_score": discovery.profit_score,
            "discovery_demand_score": discovery.demand_score,
            "discovery_brand_score": discovery.brand_score,
            "discovery_competition_score": discovery.competition_score,
            "discovery_confidence_score": discovery.confidence_score,
            "discovery_overall_score": discovery.overall_score,
            "discovery_reasons": list(discovery.reasons),
            "discovery_warnings": list(discovery.warnings),
        }
    )
