"""Tests for comparable domestic estimate rules."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, ReliabilityLevel, YahooSoldSample


def _purchase() -> AcquiredListing:
    return AcquiredListing(
        external_id="fp-1",
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        condition="Very Good",
        price=Decimal("695"),
        currency="USD",
        url="https://example.invalid/p/1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Fashionphile",
        raw_title="Chanel Classic Wallet Black Caviar",
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Yahoo Auction",
    )


def _wallet(title: str, price: int) -> YahooSoldSample:
    return _sample(f"CHANEL クラシック ウォレット 黒 キャビア {title}", price)


def test_accepted_only_median() -> None:
    samples = [
        _wallet("A", 150000),
        _wallet("B", 160000),
        _wallet("C", 170000),
        _sample("CHANEL コインケース 黒", 20000),
    ]
    result = evaluate_comparables(_purchase(), samples, purchase_price_jpy=Decimal("111200"))
    assert result.sample_count == 3
    assert result.median_jpy == Decimal("160000")
    assert result.rejected_count == 1


def test_outlier_exclusion() -> None:
    samples = [
        _wallet("A", 150000),
        _wallet("B", 160000),
        _wallet("C", 165000),
        _wallet("D", 170000),
        _wallet("E", 500000),
    ]
    result = evaluate_comparables(_purchase(), samples, purchase_price_jpy=Decimal("111200"))
    assert result.outlier_exclusions
    assert result.median_jpy < Decimal("500000")


def test_low_sample_reliability() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_wallet("A", 160000), _wallet("B", 165000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.reliability == ReliabilityLevel.LOW
    assert result.sample_count == 2


def test_suspect_price_warning() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_wallet("A", 20000), _wallet("B", 22000), _wallet("C", 24000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.data_warning == "COMPARABLE_DATA_SUSPECT"
