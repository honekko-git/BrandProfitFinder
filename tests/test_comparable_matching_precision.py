"""Tests for precision comparable matching."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample


def _purchase(title: str = "Chanel Classic Wallet Black Caviar") -> AcquiredListing:
    return AcquiredListing(
        external_id="fp-1",
        title=title,
        brand="Chanel",
        category="Wallet",
        condition="Very Good",
        price=Decimal("695"),
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


def test_exact_subtype_accepted() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("CHANEL クラシック ウォレット 黒 キャビアスキン", 180000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 1
    assert result.purchase_subtype == "COMPACT_WALLET"
    assert result.accepted_diagnostics[0].matching_score >= COMPARABLE_SCORE_THRESHOLD


def test_coin_case_rejected() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("CHANEL コインケース 黒 キャビア", 25000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 0
    assert result.rejected_diagnostics[0].rejection_reasons[0] in {
        RejectionReason.HARD_EXCLUSION.value,
        RejectionReason.SUBTYPE_MISMATCH.value,
        RejectionReason.ACCESSORY_ONLY.value,
    }


def test_card_holder_rejected() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("CHANEL カードケース 黒", 30000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 0
    assert RejectionReason.HARD_EXCLUSION.value in result.rejected_diagnostics[0].rejection_reasons


def test_material_mismatch_rejected() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("CHANEL クラシック ウォレット 黒 ラムスキン", 170000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 0
    assert RejectionReason.MATERIAL_MISMATCH.value in result.rejected_diagnostics[0].rejection_reasons


def test_generic_brand_only_result_rejected() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("CHANEL wallet black", 50000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 0
    assert RejectionReason.SCORE_BELOW_THRESHOLD.value in result.rejected_diagnostics[0].rejection_reasons
