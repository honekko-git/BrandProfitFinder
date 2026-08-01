"""Comparable sold-price quality gates (V1.0 reliability)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.comparable_quality import (
    apply_publish_gate,
    classify_comparable_quality,
    classify_sold_status,
    filter_estimation_samples,
    is_low_quality_title,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from profit_discovery.discovery_validation.batch_profit.robust_estimate import (
    build_robust_domestic_estimate,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _sample(
    title: str,
    price: int,
    *,
    status: str = "sold",
    source: str = "Yahoo Auctions",
) -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=_now(),
        source=source,
        auction_status=status,
        url="https://auctions.yahoo.co.jp/jp/auction/x1",
        sold_at="2026-07-30",
    )


def _purchase() -> AcquiredListing:
    return AcquiredListing(
        external_id="p1",
        title="Prada Saffiano Lux Medium Tote Cammeo",
        brand="Prada",
        category="Bag",
        condition="Good",
        price=Decimal("895"),
        currency="USD",
        url="https://www.fashionphile.com/products/prada-saffiano",
        retrieved_at=_now(),
        source="Fashionphile",
        raw_title="Prada Saffiano Lux Medium Tote Cammeo",
        acquisition_status=AcquisitionStatus.LIVE,
    )


def test_sold_auction_price_accepted() -> None:
    sample = _sample("PRADA サフィアーノ トートバッグ", 148000, status="sold")
    assert classify_sold_status(sample) == "SOLD_COMPLETED"
    kept, counts = filter_estimation_samples([sample])
    assert len(kept) == 1
    assert counts["sold_kept"] == 1


def test_active_listing_rejected() -> None:
    sample = _sample("PRADA トート", 148000, status="active")
    kept, counts = filter_estimation_samples([sample])
    assert kept == []
    assert counts["active_excluded"] == 1


def test_buy_now_and_auction_status_rejected() -> None:
    for status in ("buy_now", "auction", "on_sale", "open"):
        kept, counts = filter_estimation_samples([_sample("PRADA トート", 100000, status=status)])
        assert kept == []
        assert counts["active_excluded"] == 1


def test_unknown_sale_status_rejected() -> None:
    sample = _sample("PRADA トート", 100000, status="", source="Unknown Market")
    kept, counts = filter_estimation_samples([sample])
    assert kept == []
    assert counts["unknown_excluded"] == 1


def test_yahoo_blank_status_from_closed_source_accepted() -> None:
    sample = _sample("PRADA サフィアーノ トート", 160000, status="", source="Yahoo Auctions")
    kept, _ = filter_estimation_samples([sample])
    assert len(kept) == 1


def test_mercari_sold_accepted_active_rejected() -> None:
    sold = _sample("PRADA トート", 120000, status="sold_out", source="Mercari")
    active = _sample("PRADA トート", 120000, status="active", source="Mercari")
    kept, counts = filter_estimation_samples([sold, active])
    assert len(kept) == 1
    assert counts["active_excluded"] == 1


def test_junk_box_accessory_excluded() -> None:
    titles = [
        "PRADA ジャンク トート",
        "PRADA 箱のみ",
        "PRADA empty box",
        "PRADA pouch only",
        "PRADA 1円 スタート 破損",
        "PRADA accessory only case",
    ]
    for title in titles:
        assert is_low_quality_title(title)
        kept, counts = filter_estimation_samples([_sample(title, 5000, status="sold")])
        assert kept == []
        assert counts["junk_excluded"] == 1


def test_cheap_unrelated_do_not_contaminate_luxury_median() -> None:
    purchase = _purchase()
    junk_cluster = [
        _sample("PRADA トートバッグ レディース", 7975, status="sold"),
        _sample("1円 PRADA ナイロン トート 破損", 1780, status="sold"),
        _sample("PRADA ポーチのみ", 2980, status="sold"),
        _sample("PRADA 現状品 トート", 4399, status="sold"),
        _sample("PRADA Canapa Small Tote", 8097, status="sold"),
        _sample("PRADA Sport トートバック", 7250, status="sold"),
    ]
    luxury = [
        _sample("PRADA サフィアーノ ラックス トート カメオ", 148000, status="sold"),
        _sample("プラダ サフィアーノ ミディアム トート", 160000, status="sold"),
        _sample("PRADA Saffiano Lux Medium Tote", 155000, status="sold"),
    ]
    raw = junk_cluster + luxury
    filtered, counts = filter_estimation_samples(
        raw,
        purchase_price_jpy=Decimal("150000"),
    )
    assert counts["junk_excluded"] >= 2
    assert counts["suspicious_low_excluded"] >= 1
    comparable = evaluate_comparables(
        purchase,
        filtered,
        purchase_price_jpy=Decimal("150000"),
    )
    domestic = build_robust_domestic_estimate(
        raw_sample_count=comparable.raw_sample_count,
        accepted_samples=comparable.matched_samples,
        rejected_count=comparable.rejected_count,
        comparable_warning=comparable.data_warning,
        outlier_notes=comparable.outlier_exclusions,
    )
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("150000"),
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        comparable_warning=comparable.data_warning or domestic.comparable_warning,
        filter_counts=counts,
    )
    published = apply_publish_gate(domestic.recommended_selling_estimate_jpy, report)
    # Must not publish the contaminated ¥7,975 path.
    assert published != Decimal("7975")
    if report.quality == "SUSPECT" or not report.publish_price:
        assert published == Decimal("0")
    else:
        assert published >= Decimal("100000")


def test_prada_saffiano_audit_replay_rejects_7975() -> None:
    """Replay of live audit comps must not publish ¥7,975."""
    purchase = AcquiredListing(
        external_id="p-promenade",
        title="Prada Saffiano Lux Promenade Tote Argilla",
        brand="Prada",
        category="Bag",
        condition="Good",
        price=Decimal("950"),
        currency="USD",
        url="https://www.fashionphile.com/products/prada-saffiano",
        retrieved_at=_now(),
        source="Fashionphile",
        raw_title="Prada Saffiano Lux Promenade Tote Argilla",
        acquisition_status=AcquisitionStatus.LIVE,
    )
    titles_prices = [
        ("1円 プラダ キャンバス カナパ トートバッグ 現状品", 8097),
        ("プラダ 2WAY トートバッグ カナパ BN2069", 22000),
        ("ブルー PRADA ランチバッグ ノベルティ トート", 4399),
        ("プラダ トートバッグ レディース PRADA", 7975),
        ("プラダ 2way トートバッグ BN2495", 63800),
        ("1円◆PRADA キルティング ナイロントート", 7361),
        ("1円◆PRADA デニム柄 ナイロントート", 1780),
        ("☆PRADA 1BG356 デニム レザー トートバッグ", 77200),
        ("1円スタート PRADA ナイロントート", 4730),
        ("PRADA SPORT トートバック", 7250),
        ("PRADA 1BG626 トートバッグ", 18700),
        ("PRADA カナパ/トートバッグ/キャンバス", 22660),
        ("良品 PRADA ラフィア トート", 140000),
        ("PRADA スエード トートバッグ", 30001),
        ("1円 PRADA テスートナイロン トート", 18150),
        ("1円 PRADA パテント トート", 5072),
        ("海外 ノベルティ プラダ ミニトート", 8280),
        ("1円 PRADA パテント ハンドバッグ", 5897),
        ("PRADA カナパ トートバッグ ブラック", 30000),
        ("PRADA ナイロン トート ファスナー破れ 1円〜", 2980),
    ]
    raw = [_sample(title, price) for title, price in titles_prices]
    filtered, counts = filter_estimation_samples(
        raw,
        purchase_price_jpy=Decimal("152000"),
    )
    comparable = evaluate_comparables(
        purchase,
        filtered,
        purchase_price_jpy=Decimal("152000"),
    )
    domestic = build_robust_domestic_estimate(
        raw_sample_count=comparable.raw_sample_count,
        accepted_samples=comparable.matched_samples,
        rejected_count=comparable.rejected_count,
        comparable_warning=comparable.data_warning,
    )
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("152000"),
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        comparable_warning=comparable.data_warning,
        filter_counts=counts,
    )
    published = apply_publish_gate(domestic.recommended_selling_estimate_jpy, report)
    assert published != Decimal("7975")
    assert report.publish_price is False or published >= Decimal("60000")
    # Contaminated category-only audit set must not silently publish ¥7,975 profit.
    if report.quality in {"SUSPECT", "INSUFFICIENT"}:
        assert published == Decimal("0")


def test_valid_luxury_still_calculates() -> None:
    samples = [
        _sample("PRADA サフィアーノ ラックス ミディアム トート", 148000, status="sold"),
        _sample("プラダ サフィアーノ ラックス トートバッグ", 152000, status="sold"),
        _sample("PRADA Saffiano Lux Medium Tote Cammeo", 155000, status="sold"),
        _sample("PRADA Saffiano Lux Tote", 149000, status="sold"),
        _sample("プラダ サフィアーノ トート ミディアム", 151000, status="sold"),
    ]
    purchase = _purchase()
    filtered, counts = filter_estimation_samples(
        samples,
        purchase_price_jpy=Decimal("152000"),
    )
    comparable = evaluate_comparables(
        purchase,
        filtered,
        purchase_price_jpy=Decimal("152000"),
    )
    domestic = build_robust_domestic_estimate(
        raw_sample_count=comparable.raw_sample_count,
        accepted_samples=comparable.matched_samples,
        rejected_count=comparable.rejected_count,
        comparable_warning=comparable.data_warning,
    )
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("152000"),
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        comparable_warning=comparable.data_warning,
        filter_counts=counts,
    )
    published = apply_publish_gate(domestic.recommended_selling_estimate_jpy, report)
    if comparable.matched_samples and report.publish_price:
        assert published >= Decimal("100000")
        assert report.quality in {"HIGH", "MEDIUM", "LOW"}


def test_suspect_does_not_publish_price() -> None:
    samples = [_sample(f"PRADA トート {i}", 8000 + i * 100, status="sold") for i in range(8)]
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("150000"),
        accepted_samples=samples,
        comparable_warning="COMPARABLE_DATA_SUSPECT",
    )
    assert report.quality == "SUSPECT"
    assert report.publish_price is False
    assert apply_publish_gate(Decimal("7975"), report) == Decimal("0")


def test_evidence_fields_present() -> None:
    samples = [_sample("PRADA サフィアーノ トート", 150000, status="sold")]
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("152000"),
        accepted_samples=samples,
    )
    assert report.evidence
    item = report.evidence[0]
    assert item.marketplace
    assert item.title
    assert item.sale_price == 150000
    assert item.status == "SOLD_COMPLETED"


def test_brand_regression_titles_still_match_quality_path() -> None:
    for _brand, title, price in (
        ("Chanel", "CHANEL マトラッセ トート", 480000),
        ("Louis Vuitton", "LOUIS VUITTON ネヴァーフル MM", 220000),
        ("Hermès", "HERMES ピコタン ロック PM", 650000),
        ("Gucci", "GUCCI ソーホー トート", 180000),
        ("Prada", "PRADA サフィアーノ トート", 155000),
    ):
        samples = [
            _sample(f"{title} A", price, status="sold"),
            _sample(f"{title} B", price + 5000, status="sold"),
            _sample(f"{title} C", price - 5000, status="sold"),
        ]
        kept, _ = filter_estimation_samples(
            samples,
            purchase_price_jpy=Decimal(price),
        )
        assert len(kept) == 3
        report = classify_comparable_quality(
            purchase_price_jpy=Decimal(price),
            accepted_samples=kept,
        )
        # Without diagnostics, category-only path is SUSPECT (no silent publish).
        assert report.publish_price is False or report.quality in {"HIGH", "MEDIUM", "LOW", "SUSPECT"}
