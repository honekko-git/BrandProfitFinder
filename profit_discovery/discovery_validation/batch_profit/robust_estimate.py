"""Robust domestic estimate from accepted comparables."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from marketplace.browser_acquisition.models import ReliabilityLevel, YahooSoldSample
from profit_discovery.discovery_validation.batch_profit.models import RobustDomesticEstimate


def build_robust_domestic_estimate(
    *,
    raw_sample_count: int,
    accepted_samples: tuple[YahooSoldSample, ...],
    rejected_count: int,
    comparable_warning: str = "",
    outlier_notes: tuple[str, ...] = (),
) -> RobustDomesticEstimate:
    """Build robust domestic estimate from accepted Yahoo samples."""
    prices = sorted(sample.sold_price_jpy for sample in accepted_samples)
    accepted_count = len(prices)

    if not prices:
        return RobustDomesticEstimate(
            raw_sample_count=raw_sample_count,
            accepted_count=0,
            rejected_count=rejected_count,
            minimum_jpy=0,
            maximum_jpy=0,
            average_jpy=Decimal("0"),
            median_jpy=Decimal("0"),
            q1_jpy=0,
            q3_jpy=0,
            iqr_jpy=0,
            outlier_count=0,
            trimmed_average_jpy=None,
            recommended_selling_estimate_jpy=Decimal("0"),
            reliability=ReliabilityLevel.LOW.value,
            comparable_warning=comparable_warning,
            outlier_notes=outlier_notes,
        )

    filtered, outlier_count = _remove_outliers(prices)
    q1, q3, iqr = _quartiles(filtered)
    median_jpy = Decimal(str(int(median(filtered))))
    trimmed_avg = _trimmed_average(filtered)
    recommended = _recommended_estimate(filtered, median_jpy, trimmed_avg)
    reliability = _reliability(accepted_count)

    return RobustDomesticEstimate(
        raw_sample_count=raw_sample_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        minimum_jpy=min(filtered),
        maximum_jpy=max(filtered),
        average_jpy=Decimal(str(round(sum(filtered) / len(filtered)))),
        median_jpy=median_jpy,
        q1_jpy=q1,
        q3_jpy=q3,
        iqr_jpy=iqr,
        outlier_count=outlier_count,
        trimmed_average_jpy=trimmed_avg,
        recommended_selling_estimate_jpy=recommended,
        reliability=reliability,
        comparable_warning=comparable_warning,
        outlier_notes=outlier_notes,
    )


def _recommended_estimate(
    prices: list[int],
    median_jpy: Decimal,
    trimmed_avg: Decimal | None,
) -> Decimal:
    count = len(prices)
    if count >= 5 and trimmed_avg is not None:
        return min(median_jpy, trimmed_avg)
    if count >= 3:
        return median_jpy
    if count >= 1:
        return median_jpy
    return Decimal("0")


def _remove_outliers(prices: list[int]) -> tuple[list[int], int]:
    if len(prices) < 4:
        return prices, 0
    q1, q3, iqr = _quartiles(prices)
    lower = q1 - int(iqr * 1.5)
    upper = q3 + int(iqr * 1.5)
    kept = [price for price in prices if lower <= price <= upper]
    removed = len(prices) - len(kept)
    return kept or prices, removed


def _quartiles(prices: list[int]) -> tuple[int, int, int]:
    if not prices:
        return 0, 0, 0
    sorted_prices = sorted(prices)
    q1 = sorted_prices[len(sorted_prices) // 4]
    q3 = sorted_prices[(len(sorted_prices) * 3) // 4]
    return q1, q3, q3 - q1


def _trimmed_average(prices: list[int]) -> Decimal | None:
    if len(prices) < 4:
        return None
    trimmed = prices[1:-1]
    if not trimmed:
        return None
    return Decimal(str(round(sum(trimmed) / len(trimmed))))


def _reliability(count: int) -> str:
    if count >= 8:
        return ReliabilityLevel.HIGH.value
    if count >= 3:
        return ReliabilityLevel.MEDIUM.value
    return ReliabilityLevel.LOW.value
