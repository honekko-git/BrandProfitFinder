"""
Combine component explanations into a stable aggregate view.
"""

from __future__ import annotations

from profit_intelligence.models import ScoreComponentResult
from profit_intelligence.normalization import dedupe_preserve_order


class ExplanationBuilder:
    """Merge scorer outputs into concise human-readable explanations."""

    _COMPONENT_ORDER = ("profit", "velocity", "risk", "confidence")

    def build(
        self,
        components: dict[str, ScoreComponentResult],
        *,
        max_reasons: int = 8,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        reasons: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []

        for name in self._COMPONENT_ORDER:
            component = components.get(name)
            if component is None:
                continue
            reasons.extend(component.reasons)
            warnings.extend(component.warnings)
            missing.extend(component.missing_fields)

        trimmed_reasons = dedupe_preserve_order(reasons)[:max_reasons]
        return (
            trimmed_reasons,
            dedupe_preserve_order(warnings),
            dedupe_preserve_order(missing),
        )
