"""Tests for purchase/sold title matching."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.matching import (
    build_yahoo_search_terms,
    compute_similarity_score,
    filter_matched_samples,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample


def _purchase(title: str) -> AcquiredListing:
    return AcquiredListing(
        external_id="fp-1",
        title=title,
        brand="Chanel",
        category="Wallet",
        condition="Very Good",
        price=Decimal("700"),
        currency="USD",
        url="https://example.invalid/p/1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Fashionphile",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int = 160000) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Yahoo Auction",
    )


def test_wallet_similarity_above_threshold() -> None:
    purchase = _purchase("Chanel Classic Wallet Black Caviar")
    sample = _sample("CHANEL クラシック ウォレット 黒 カビアン")
    score = compute_similarity_score(purchase, sample)
    assert score >= 60


def test_accessory_only_exclusion() -> None:
    purchase = _purchase("Chanel Classic Wallet Black Caviar")
    sample = _sample("CHANEL 箱のみ 空箱", price=4000)
    score = compute_similarity_score(purchase, sample)
    assert score == 0


def test_unrelated_model_exclusion() -> None:
    purchase = _purchase("Chanel Classic Wallet Black Caviar")
    sample = _sample("Gucci Marmont Wallet Black")
    score = compute_similarity_score(purchase, sample)
    assert score == 0


def test_similarity_threshold_filtering() -> None:
    purchase = _purchase("Chanel Classic Wallet Black Caviar")
    samples = [
        _sample("CHANEL クラシック ウォレット 黒 カビアン"),
        _sample("CHANEL 箱のみ 空箱", price=4000),
    ]
    matched = filter_matched_samples(purchase, samples, min_score=60)
    assert len(matched) == 1


def test_build_yahoo_search_terms_removes_noise() -> None:
    terms = build_yahoo_search_terms(
        title="Chanel Classic Wallet Black Caviar Authentic Excellent",
        brand="Chanel",
        category="Wallet",
    )
    lowered = terms.lower()
    assert "chanel" in lowered
    assert "wallet" in lowered
    assert "excellent" not in lowered
    assert "authentic" not in lowered
