"""
Ranking engine for profit calculation results.
"""

from copy import deepcopy
from decimal import Decimal
from enum import Enum

from models.price_result import CALCULATION_SUCCESS, PriceResult
from price_compare.profit_config import ProfitConfig
from ranking_foundation.policy import RankingPolicy
from ranking_foundation.scorer import RankingScoreCalculator


class RankingSortKey(str, Enum):
    """Supported ranking sort keys."""

    PROFIT = "profit_jpy"
    MARGIN = "profit_margin"
    ROI = "roi"
    DOMESTIC_SALE = "domestic_sale_price_jpy"
    TOTAL_COST = "total_cost_jpy"
    SCORE = "ranking_score"


class RankingEngine:
    """Sort and score PriceResult collections."""

    def __init__(
        self,
        config: ProfitConfig | None = None,
        policy: RankingPolicy | None = None,
        score_calculator: RankingScoreCalculator | None = None,
    ) -> None:
        """
        Initialize ranking engine.

        Args:
            config: Optional score weight configuration.
            policy: Optional explicit ranking policy override.
            score_calculator: Optional score calculator override.
        """
        self.config = config or ProfitConfig()
        self.policy = policy or RankingPolicy.from_profit_config(self.config)
        self._score_calculator = score_calculator or RankingScoreCalculator(self.policy)

    def rank(
        self,
        results: list[PriceResult],
        sort_key: RankingSortKey = RankingSortKey.PROFIT,
        descending: bool = True,
        exclude_invalid: bool = True,
        limit: int | None = None,
    ) -> list[PriceResult]:
        """
        Return a sorted copy of price results.

        Args:
            results: Source results. Not modified.
            sort_key: Attribute used for sorting.
            descending: Sort highest values first when True.
            exclude_invalid: Skip non-success results when True.
            limit: Optional maximum number of rows to return.

        Returns:
            Sorted result list with ranking_score populated.
        """
        working = deepcopy(results)
        scored = self.apply_ranking_scores(working)

        if exclude_invalid:
            scored = [result for result in scored if result.calculation_status == CALCULATION_SUCCESS]

        reverse = descending
        scored.sort(
            key=lambda item: (
                -self._sort_value(item, sort_key)
                if reverse
                else self._sort_value(item, sort_key),
                item.product.name if item.product else item.title,
            ),
        )

        if limit is not None:
            return scored[:limit]
        return scored

    def apply_ranking_scores(self, results: list[PriceResult]) -> list[PriceResult]:
        """
        Populate ranking_score for each valid result.

        Args:
            results: Results to score.

        Returns:
            Same list with scores updated.
        """
        scores = self._score_calculator.score_results(results)
        for result, score in zip(results, scores, strict=True):
            if result.calculation_status != CALCULATION_SUCCESS:
                result.ranking_score = Decimal("0")
            else:
                result.ranking_score = score
        return results

    @staticmethod
    def _sort_value(result: PriceResult, sort_key: RankingSortKey) -> Decimal:
        value = getattr(result, sort_key.value, Decimal("0"))
        if value is None:
            return Decimal("0")
        return Decimal(str(value))
