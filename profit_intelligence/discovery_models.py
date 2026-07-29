"""Profit discovery scoring models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DiscoveryScore:
    """Explainable profit discovery score for one price result."""

    profit_score: float
    demand_score: float
    brand_score: float
    competition_score: float
    confidence_score: float
    overall_score: float
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComponentScore:
    """Single discovery component score with explainability."""

    score: float
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
