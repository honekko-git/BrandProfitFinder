"""Focused tests for handbag model-family extraction, queries, and matching."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.browser_acquisition.bag_model_family import (
    FAMILY_CLASSIC_FLAP,
    STRUCTURAL_DOUBLE_FLAP,
    extract_handbag_model_identity,
)
from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries


PURCHASE_TITLE = "Chanel Classic Double Flap Bag Quilted Patent Medium"


def _purchase() -> AcquiredListing:
    return AcquiredListing(
        external_id="p1",
        title=PURCHASE_TITLE,
        brand="Chanel",
        category="Bag",
        condition="UNKNOWN",
        price=Decimal("4515"),
        currency="USD",
        url="https://www.rebag.com/products/handbags-chanel-classic-double-flap-bag",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Rebag",
        raw_title=PURCHASE_TITLE,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int = 100000) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Mercari",
        auction_status="sold",
        url="https://jp.mercari.com/item/m1",
        condition="Good",
    )


def test_extract_classic_flap_english() -> None:
    identity = extract_handbag_model_identity(title=PURCHASE_TITLE, brand="Chanel", category="Bag")
    assert identity.model_family == FAMILY_CLASSIC_FLAP
    assert identity.structural_modifier == STRUCTURAL_DOUBLE_FLAP
    assert identity.size == "Medium"
    assert identity.material == "Patent"
    assert identity.category == "Bag"


def test_extract_japanese_aliases() -> None:
    for title in (
        "シャネル マトラッセ 黒",
        "シャネル クラシックフラップ ミディアム",
        "シャネル ダブルフラップ パテント",
    ):
        identity = extract_handbag_model_identity(title=title, brand="Chanel", category="Bag")
        assert identity.model_family == FAMILY_CLASSIC_FLAP, title


def test_same_family_can_accept() -> None:
    result = evaluate_comparables(
        _purchase(),
        [
            _sample("シャネル マトラッセ ダブルフラップ ミディアム パテント 黒", 180000),
            _sample("シャネル クラシックフラップ ミディアム パテント", 175000),
            _sample("Chanel Classic Double Flap Medium Patent", 190000),
        ],
        purchase_price_jpy=Decimal("600000"),
    )
    assert result.accepted_diagnostics
    assert all(item.model_family == FAMILY_CLASSIC_FLAP for item in result.accepted_diagnostics)
    assert all(item.matching_score >= COMPARABLE_SCORE_THRESHOLD for item in result.accepted_diagnostics)


def test_triple_coco_vinyl_tote_rejected() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("シャネル トリプルココ フラワー ビニール パテントレザー トートバッグ ピンク", 42000)],
        purchase_price_jpy=Decimal("600000"),
    )
    assert not result.accepted_diagnostics
    reasons = set(result.rejected_diagnostics[0].rejection_reasons)
    assert reasons & {
        RejectionReason.DISTINCT_PRODUCT_FAMILY.value,
        RejectionReason.MODEL_FAMILY_CONFLICT.value,
        RejectionReason.GENERIC_SAME_BRAND_INSUFFICIENT.value,
    }


def test_coco_sailor_rejected_against_classic_flap() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("本物 シャネル CHANEL ココセーラー マトラッセ ダブルフラップ チェーン ショルダーバッグ", 498000)],
        purchase_price_jpy=Decimal("600000"),
    )
    assert not result.accepted_diagnostics
    assert RejectionReason.DISTINCT_PRODUCT_FAMILY.value in result.rejected_diagnostics[0].rejection_reasons


def test_distinct_chanel_families_rejected() -> None:
    titles = [
        "Chanel tote bag black",
        "Chanel shopping tote canvas",
        "Chanel vanity case patent",
        "Chanel wallet on chain caviar",
        "Chanel Boy Bag black calfskin",
        "Chanel Gabrielle hobo black",
        "Chanel 19 flap bag black",
        "Chanel Coco Handle small black",
    ]
    for title in titles:
        result = evaluate_comparables(_purchase(), [_sample(title)], purchase_price_jpy=Decimal("600000"))
        assert not result.accepted_diagnostics, title


def test_brand_patent_bag_without_classic_flap_insufficient() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("シャネル パテントレザー バッグ 黒", 90000)],
        purchase_price_jpy=Decimal("600000"),
    )
    assert not result.accepted_diagnostics
    assert RejectionReason.GENERIC_SAME_BRAND_INSUFFICIENT.value in result.rejected_diagnostics[0].rejection_reasons


def test_material_cannot_overcome_model_family_conflict() -> None:
    result = evaluate_comparables(
        _purchase(),
        [_sample("シャネル ボーイ パテント フラップバッグ", 200000)],
        purchase_price_jpy=Decimal("600000"),
    )
    assert not result.accepted_diagnostics
    reasons = set(result.rejected_diagnostics[0].rejection_reasons)
    assert reasons & {
        RejectionReason.DISTINCT_PRODUCT_FAMILY.value,
        RejectionReason.MODEL_FAMILY_CONFLICT.value,
    }


def test_unknown_model_family_bag_remains_conservative() -> None:
    purchase = AcquiredListing(
        external_id="p2",
        title="Chanel Leather Shoulder Bag Black",
        brand="Chanel",
        category="Bag",
        condition="UNKNOWN",
        price=Decimal("1000"),
        currency="USD",
        url="https://www.rebag.com/products/handbags-x",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Rebag",
        raw_title="Chanel Leather Shoulder Bag Black",
        acquisition_status=AcquisitionStatus.LIVE,
    )
    identity = extract_handbag_model_identity(title=purchase.title, brand="Chanel", category="Bag")
    assert not identity.has_known_model_family
    result = evaluate_comparables(
        purchase,
        [_sample("シャネル パテント トートバッグ", 50000)],
        purchase_price_jpy=Decimal("150000"),
    )
    # No known family on purchase: do not invent Classic Flap acceptance.
    assert all(item.model_family != FAMILY_CLASSIC_FLAP or not item.accepted for item in result.accepted_diagnostics)


def test_wallet_matching_unchanged_for_classic_wallet() -> None:
    purchase = AcquiredListing(
        external_id="w1",
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        condition="EXCELLENT",
        price=Decimal("695"),
        currency="USD",
        url="https://www.fashionphile.com/p/chanel-classic-wallet",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Fashionphile",
        raw_title="Chanel Classic Wallet Black Caviar",
        acquisition_status=AcquisitionStatus.LIVE,
    )
    result = evaluate_comparables(
        purchase,
        [_sample("シャネル クラシック 長財布 キャビアスキン 黒", 120000)],
        purchase_price_jpy=Decimal("100000"),
    )
    # Wallet path must still evaluate without bag family hard-fail.
    assert result.raw_sample_count == 1


def test_query_generation_prioritizes_model_family() -> None:
    queries = build_yahoo_search_queries(title=PURCHASE_TITLE, brand="Chanel", category="Bag")
    joined = " ".join(queries)
    assert any("マトラッセ" in q or "クラシックフラップ" in q or "Classic" in q for q in queries)
    assert "ダブルフラップ" in joined or "クラシックフラップ" in joined or "エナメル" in joined
    assert not queries[0].startswith("シャネル バッグ")
    assert len(queries) >= 3
    assert "シャネル マトラッセ ダブルフラップ" in queries or queries[0].startswith("シャネル マトラッセ")


def test_classic_flap_query_variants_include_enamel_and_coco_mark() -> None:
    queries = build_yahoo_search_queries(title=PURCHASE_TITLE, brand="Chanel", category="Bag")
    joined = " ".join(queries)
    assert "エナメル" in joined or "パテント" in joined or "クラシックフラップ" in joined
    assert "バッグ パテント" not in queries[0]


def test_same_family_lambskin_not_hard_rejected_against_patent() -> None:
    result = evaluate_comparables(
        _purchase(),
        [
            _sample("シャネル マトラッセ ダブルフラップ 25cm ラムスキン 黒", 250000),
            _sample("シャネル マトラッセ ダブルフラップ ミディアム キャビアスキン", 280000),
            _sample("シャネル マトラッセ ダブルフラップ パテント ミディアム", 300000),
        ],
        purchase_price_jpy=Decimal("600000"),
    )
    assert len(result.accepted_diagnostics) >= 3
    assert all(item.model_family == FAMILY_CLASSIC_FLAP for item in result.accepted_diagnostics)


def test_extract_coco_matelasse_alias() -> None:
    identity = extract_handbag_model_identity(
        title="シャネル ココマーク マトラッセ ダブルフラップ 25cm",
        brand="Chanel",
        category="Bag",
    )
    assert identity.model_family == FAMILY_CLASSIC_FLAP
    assert identity.size == "Medium"


def test_selector_prefers_no_comparable_over_wrong_family() -> None:
    from marketplace.browser_acquisition.comparable_candidate import (
        candidate_from_best_comparable,
        select_best_comparable_candidate,
    )
    from marketplace.browser_acquisition.mercari_comparable import select_best_mercari_comparable

    result = evaluate_comparables(
        _purchase(),
        [_sample("シャネル トリプルココ フラワー ビニール パテントレザー トートバッグ ピンク", 42000)],
        purchase_price_jpy=Decimal("600000"),
    )
    best = select_best_mercari_comparable(_purchase(), result, candidate_samples=result.matched_samples)
    selected = select_best_comparable_candidate([candidate_from_best_comparable(best, marketplace="Mercari")])
    assert selected is None
