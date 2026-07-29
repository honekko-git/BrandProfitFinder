"""Demand scoring foundation for profit discovery."""

from __future__ import annotations

from typing import Any, Mapping

from market_intelligence.models import MarketSignals
from profit_intelligence.discovery_models import ComponentScore
from profit_intelligence.normalization import clamp_score, normalize_optional_int

NEUTRAL_SCORE = 50.0


class DemandScorer:
    """Score demand potential from market signals and neutral metadata keys."""

    def score(
        self,
        signals: MarketSignals | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ComponentScore:
        reasons: list[str] = []
        warnings: list[str] = []
        meta = dict(metadata or {})

        if signals is not None and signals.demand_score is not None:
            score = clamp_score(float(signals.demand_score))
            reasons.append("Demand score supplied by market signals.")
            return ComponentScore(score=score, reasons=tuple(reasons), warnings=tuple(warnings))

        sales_30 = normalize_optional_int(meta.get("sales_last_30_days"))
        sales_72 = normalize_optional_int(meta.get("sales_last_72_hours"))

        if sales_30 is not None:
            if sales_30 >= 30:
                score = 85.0
                reasons.append("Strong 30-day sales activity.")
            elif sales_30 >= 10:
                score = 65.0
                reasons.append("Moderate 30-day sales activity.")
            elif sales_30 > 0:
                score = 45.0
                reasons.append("Limited 30-day sales activity.")
            else:
                score = 25.0
                reasons.append("No recent 30-day sales activity observed.")
            if sales_72 is not None and sales_72 >= 3:
                score = clamp_score(score + 5.0)
                reasons.append("Recent 72-hour sales support demand.")
            return ComponentScore(score=clamp_score(score), reasons=tuple(reasons), warnings=tuple(warnings))

        if sales_72 is not None:
            score = 70.0 if sales_72 >= 3 else 40.0
            reasons.append("Demand estimated from recent 72-hour sales only.")
            warnings.append("30-day demand data unavailable.")
            return ComponentScore(score=score, reasons=tuple(reasons), warnings=tuple(warnings))

        warnings.append("Demand data unavailable.")
        return ComponentScore(
            score=NEUTRAL_SCORE,
            reasons=tuple(),
            warnings=tuple(warnings),
        )
