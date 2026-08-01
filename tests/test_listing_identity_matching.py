"""Tests for deterministic luxury listing identity normalization and matching priority."""

from __future__ import annotations

from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.listing_identity import (
    cleanup_title,
    extract_listing_identity,
    extract_model_numbers,
    normalize_brand,
    normalize_category,
    normalize_color,
    normalize_condition,
    normalize_hardware,
    normalize_material,
)
from marketplace.browser_acquisition.luxury_material import LuxuryMaterial, detect_luxury_material
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample


def test_normalize_brand_aliases() -> None:
    assert normalize_brand("LV") == "LOUIS VUITTON"
    assert normalize_brand("Louis Vuitton") == "LOUIS VUITTON"
    assert normalize_brand("ルイヴィトン") == "LOUIS VUITTON"
    assert normalize_brand("chanel") == "CHANEL"
    assert normalize_brand("", title="GUCCI Dionysus Wallet") == "GUCCI"


def test_extract_model_numbers() -> None:
    assert extract_model_numbers("Louis Vuitton Pochette Metis M80481") == ("M80481",)
    assert "A01998" in extract_model_numbers("Chanel Classic A01998 Caviar")
    assert "N41661" in extract_model_numbers("LV Neonoe N41661 Monogram")


def test_normalize_category_variants() -> None:
    assert normalize_category(title="Chanel Zip Wallet") == "ZIP_WALLET"
    assert normalize_category(title="Round Zip Wallet") == "ROUND_ZIP"
    assert normalize_category(title="Long Wallet Monogram") == "LONG_WALLET"
    assert normalize_category(title="Shoulder Bag") == "SHOULDER_BAG"
    assert normalize_category(title="Tote Bag") == "TOTE_BAG"
    assert normalize_category(title="Backpack") == "BACKPACK"


def test_normalize_color_synonyms() -> None:
    assert normalize_color("Noir Caviar") == "BLACK"
    assert normalize_color("Nero Leather") == "BLACK"
    assert normalize_color("黒 キャビア") == "BLACK"
    assert normalize_color("Blanc") == "WHITE"


def test_normalize_material_families() -> None:
    assert normalize_material("Epi Leather") == "EPI"
    assert normalize_material("Damier Ebene") == "DAMIER"
    assert normalize_material("Monogram Canvas") == "MONOGRAM"
    assert normalize_material("Caviar") == "CAVIAR"
    assert detect_luxury_material("LV Epi Zippy") == LuxuryMaterial.EPI
    assert detect_luxury_material("Damier wallet") == LuxuryMaterial.DAMIER


def test_normalize_hardware_and_condition() -> None:
    assert normalize_hardware("Black Caviar Gold Hardware") == "GOLD"
    assert normalize_hardware("SHW silver") == "SILVER"
    assert normalize_hardware("Palladium hardware") == "PALLADIUM"
    assert normalize_condition("Excellent") == "EXCELLENT"
    assert normalize_condition("Very Good") == "VERY_GOOD"
    assert normalize_condition("美品") == "EXCELLENT"
    assert normalize_condition("Fair") == "FAIR"


def test_title_cleanup_removes_marketing_noise() -> None:
    cleaned = cleanup_title("  CHANEL  Classic!!! Wallet  Free Shipping  Authenticated  ")
    assert "chanel" in cleaned
    assert "classic" in cleaned
    assert "!!!" not in cleaned
    assert "free shipping" not in cleaned
    assert "authenticated" not in cleaned
    assert "  " not in cleaned


def test_extract_listing_identity_bundle() -> None:
    identity = extract_listing_identity(
        title="Louis Vuitton Neonoe MM N41661 Noir Monogram",
        brand="LV",
        category="Bag",
        condition="Very Good",
    )
    assert identity.brand == "LOUIS VUITTON"
    assert identity.model_numbers == ("N41661",)
    assert identity.color == "BLACK"
    assert identity.material == "MONOGRAM"
    assert identity.condition == "VERY_GOOD"


def _purchase(**kwargs) -> AcquiredListing:
    title = kwargs.get("title", "Chanel Classic Wallet Black Caviar")
    return AcquiredListing(
        external_id="fp-1",
        title=title,
        brand=kwargs.get("brand", "Chanel"),
        category=kwargs.get("category", "Wallet"),
        condition=kwargs.get("condition", "Very Good"),
        price=Decimal("695"),
        currency="USD",
        url="https://example.invalid/p/1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Fashionphile",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int = 160000, condition: str = "") -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at="2026-01-01T00:00:00+00:00",
        source="Yahoo Auction",
        condition=condition,
    )


def test_model_number_match_accepted_as_priority() -> None:
    result = evaluate_comparables(
        _purchase(
            title="Louis Vuitton Pochette Metis East West M80481 Monogram",
            brand="LV",
            category="Bag",
        ),
        [_sample("ルイヴィトン ポシェットメティス M80481 モノグラム", 280000)],
        purchase_price_jpy=Decimal("180000"),
    )
    assert result.sample_count == 1
    assert result.accepted_diagnostics[0].matching_score >= COMPARABLE_SCORE_THRESHOLD


def test_model_number_mismatch_rejected() -> None:
    result = evaluate_comparables(
        _purchase(
            title="Louis Vuitton Pochette Metis M80481 Monogram",
            brand="Louis Vuitton",
            category="Bag",
        ),
        [_sample("ルイヴィトン ネオンエ N41661 モノグラム", 200000)],
        purchase_price_jpy=Decimal("180000"),
    )
    assert result.sample_count == 0
    assert RejectionReason.MODEL_NUMBER_MISMATCH.value in result.rejected_diagnostics[0].rejection_reasons


def test_lv_brand_alias_and_noir_color_match() -> None:
    result = evaluate_comparables(
        _purchase(
            title="Louis Vuitton Zippy Wallet N41661 Noir Monogram",
            brand="LV",
            category="Wallet",
        ),
        [_sample("ルイヴィトン ジッピーウォレット N41661 黒 モノグラム", 145000)],
        purchase_price_jpy=Decimal("120000"),
    )
    assert result.sample_count == 1


def test_bag_vs_wallet_category_rejected() -> None:
    result = evaluate_comparables(
        _purchase(title="Chanel Classic Wallet Black Caviar", brand="Chanel", category="Wallet"),
        [_sample("CHANEL マトラッセ ショルダーバッグ 黒 キャビア", 450000)],
        purchase_price_jpy=Decimal("111200"),
    )
    assert result.sample_count == 0
    reasons = result.rejected_diagnostics[0].rejection_reasons
    assert (
        RejectionReason.CATEGORY_MISMATCH.value in reasons
        or RejectionReason.SUBTYPE_MISMATCH.value in reasons
        or RejectionReason.SCORE_BELOW_THRESHOLD.value in reasons
    )
