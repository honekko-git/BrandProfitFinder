"""Brand strength scoring foundation for profit discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from profit_intelligence.discovery_models import ComponentScore
from profit_intelligence.normalization import clamp_score

NEUTRAL_SCORE = 50.0


@dataclass(frozen=True, slots=True)
class BrandTierConfig:
    """Configurable brand tier scores."""

    tier_s: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"gucci", "chanel", "hermes", "louis vuitton", "louis-vuitton", "prada"}
        )
    )
    tier_a: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"dior", "balenciaga", "celine", "ysl", "saint laurent", "bottega veneta"}
        )
    )
    tier_b: frozenset[str] = field(
        default_factory=lambda: frozenset({"coach", "michael kors", "kate spade", "fendi"})
    )
    tier_s_score: float = 100.0
    tier_a_score: float = 80.0
    tier_b_score: float = 60.0
    unknown_score: float = NEUTRAL_SCORE


class BrandScorer:
    """Score brand strength using configurable tier lists."""

    def __init__(self, config: BrandTierConfig | None = None) -> None:
        self.config = config or BrandTierConfig()

    def score(self, metadata: Mapping[str, str] | None = None, brand: str | None = None) -> ComponentScore:
        reasons: list[str] = []
        warnings: list[str] = []

        normalized = _normalize_brand(brand)
        if not normalized and metadata is not None:
            normalized = _normalize_brand(str(metadata.get("brand") or ""))

        if not normalized:
            warnings.append("Brand identity unavailable.")
            return ComponentScore(
                score=self.config.unknown_score,
                reasons=tuple(),
                warnings=tuple(warnings),
            )

        if normalized in self.config.tier_s:
            reasons.append("Strong brand confidence.")
            return ComponentScore(score=clamp_score(self.config.tier_s_score), reasons=tuple(reasons))
        if normalized in self.config.tier_a:
            reasons.append("Recognized premium brand.")
            return ComponentScore(score=clamp_score(self.config.tier_a_score), reasons=tuple(reasons))
        if normalized in self.config.tier_b:
            reasons.append("Known brand with moderate resale strength.")
            return ComponentScore(score=clamp_score(self.config.tier_b_score), reasons=tuple(reasons))

        reasons.append("Brand tier unknown; neutral brand score applied.")
        return ComponentScore(score=clamp_score(self.config.unknown_score), reasons=tuple(reasons))


def _normalize_brand(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())
