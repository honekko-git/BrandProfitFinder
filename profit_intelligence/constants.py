"""
Thresholds and weights for Profit Intelligence v1.
"""

from dataclasses import dataclass
from typing import Final

SCORING_VERSION: Final[str] = "profit-intelligence-v1"

# Piecewise thresholds: (value, score)
PROFIT_AMOUNT_THRESHOLDS: Final[tuple[tuple[float, float], ...]] = (
    (0.0, 5.0),
    (1_000.0, 25.0),
    (3_000.0, 50.0),
    (5_000.0, 70.0),
    (10_000.0, 85.0),
    (20_000.0, 100.0),
)

PROFIT_MARGIN_THRESHOLDS: Final[tuple[tuple[float, float], ...]] = (
    (0.0, 5.0),
    (5.0, 25.0),
    (10.0, 50.0),
    (20.0, 70.0),
    (30.0, 85.0),
    (50.0, 100.0),
)

SALES_30D_THRESHOLDS: Final[tuple[tuple[float, float], ...]] = (
    (0.0, 10.0),
    (5.0, 35.0),
    (15.0, 55.0),
    (30.0, 75.0),
    (60.0, 90.0),
    (100.0, 100.0),
)

SALES_72H_THRESHOLDS: Final[tuple[tuple[float, float], ...]] = (
    (0.0, 10.0),
    (1.0, 40.0),
    (3.0, 60.0),
    (6.0, 80.0),
    (12.0, 100.0),
)


@dataclass(frozen=True)
class ComponentWeights:
    """Overall score component weights (must sum to 1.0 when all available)."""

    profit: float = 0.45
    velocity: float = 0.25
    risk_inverse: float = 0.20
    confidence: float = 0.10


@dataclass(frozen=True)
class RecommendationThreshold:
    minimum: float
    stars: int
    label: str


RECOMMENDATION_THRESHOLDS: Final[tuple[RecommendationThreshold, ...]] = (
    RecommendationThreshold(90.0, 5, "High-priority review candidate"),
    RecommendationThreshold(75.0, 4, "Promising review candidate"),
    RecommendationThreshold(60.0, 3, "Moderate review candidate"),
    RecommendationThreshold(40.0, 2, "Cautious review candidate"),
    RecommendationThreshold(0.0, 1, "Low-priority review candidate"),
)

INSUFFICIENT_DATA_LABEL: Final[str] = "Insufficient data"

HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.30
LOW_LIQUIDITY_SALES_30D: Final[int] = 5
LOW_LIQUIDITY_ASKS: Final[int] = 3
