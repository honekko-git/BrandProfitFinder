"""Tests for robust domestic estimate."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.models import YahooSoldSample
from profit_discovery.discovery_validation.batch_profit.robust_estimate import build_robust_domestic_estimate


def _sample(price: int) -> YahooSoldSample:
    return YahooSoldSample(
        title="CHANEL wallet",
        sold_price_jpy=price,
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Yahoo Auction",
    )


def test_median_and_iqr() -> None:
    estimate = build_robust_domestic_estimate(
        raw_sample_count=5,
        accepted_samples=tuple(_sample(price) for price in (100000, 110000, 120000, 130000, 500000)),
        rejected_count=0,
    )
    assert estimate.median_jpy < Decimal("500000")
    assert estimate.outlier_count >= 1
    assert estimate.iqr_jpy >= 0


def test_trimmed_and_recommended_estimate() -> None:
    estimate = build_robust_domestic_estimate(
        raw_sample_count=5,
        accepted_samples=tuple(_sample(price) for price in (150000, 160000, 170000, 180000, 190000)),
        rejected_count=0,
    )
    assert estimate.recommended_selling_estimate_jpy == min(estimate.median_jpy, estimate.trimmed_average_jpy or estimate.median_jpy)


def test_insufficient_samples() -> None:
    estimate = build_robust_domestic_estimate(
        raw_sample_count=2,
        accepted_samples=(_sample(150000), _sample(160000)),
        rejected_count=0,
    )
    assert estimate.reliability == "LOW"
    assert estimate.accepted_count == 2
