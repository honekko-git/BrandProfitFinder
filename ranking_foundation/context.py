"""Batch normalization context for ranking."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from models.price_result import CALCULATION_SUCCESS, PriceResult


@dataclass(frozen=True, slots=True)
class RankingBatchContext:
    """Batch normalization context for ranking signals."""

    max_profit_jpy: Decimal
    max_total_cost_jpy: Decimal

    @classmethod
    def from_results(cls, results: list[PriceResult]) -> RankingBatchContext:
        valid = [result for result in results if result.calculation_status == CALCULATION_SUCCESS]
        max_profit = max((result.profit_jpy for result in valid), default=Decimal("0"))
        max_cost = max((result.total_cost_jpy for result in valid), default=Decimal("0"))
        return cls(max_profit_jpy=max_profit, max_total_cost_jpy=max_cost)
