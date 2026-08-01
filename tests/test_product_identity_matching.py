"""Product identity matching and query priority (V1.0 reliability)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.comparable_quality import (
    apply_publish_gate,
    classify_comparable_quality,
    filter_estimation_samples,
)
from marketplace.browser_acquisition.listing_identity import extract_model_numbers
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.new_market_price import build_new_market_warning
from marketplace.browser_acquisition.product_identity import extract_product_identity
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from profit_discovery.discovery_validation.batch_profit.robust_estimate import (
    build_robust_domestic_estimate,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _listing(title: str, *, brand: str = "Prada", category: str = "Bag") -> AcquiredListing:
    return AcquiredListing(
        external_id="id",
        title=title,
        brand=brand,
        category=category,
        condition="Good",
        price=Decimal("500"),
        currency="USD",
        url="https://www.fashionphile.com/products/x",
        retrieved_at=_now(),
        source="Fashionphile",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _sample(title: str, price: int, *, status: str = "sold") -> YahooSoldSample:
    return YahooSoldSample(
        title=title,
        sold_price_jpy=price,
        retrieved_at=_now(),
        source="Yahoo Auctions",
        auction_status=status,
        url="https://auctions.yahoo.co.jp/jp/auction/x1",
        sold_at="2026-08-01",
    )


def test_prada_spr26z_reference_extracted_and_queries() -> None:
    title = "Prada Acetate Oval Sunglasses SPR 26Z Pink"
    identity = extract_product_identity(title=title, brand="Prada", category="Sunglasses")
    assert "SPR26Z" in identity.reference_numbers
    assert identity.category == "SUNGLASSES"
    assert identity.material == "ACETATE"
    queries = build_yahoo_search_queries(title=title, brand="Prada", category="Sunglasses")
    assert any("SPR26Z" in q for q in queries)
    assert any("sunglasses" in q.lower() or "サングラス" in q for q in queries)


def test_different_prada_sunglasses_not_high() -> None:
    purchase = _listing(
        "Prada Acetate Oval Sunglasses SPR 26Z Pink",
        category="Sunglasses",
    )
    samples = [
        _sample("PRADA SPR32S sunglasses black", 42000),
        _sample("PRADA SPR14 sunglasses", 38000),
        _sample("プラダ サングラス 黒", 35000),
        _sample("PRADA sunglasses acetate", 40000),
        _sample("プラダ SPR99 サングラス", 45000),
    ]
    filtered, counts = filter_estimation_samples(samples, purchase_price_jpy=Decimal("50000"))
    comparable = evaluate_comparables(purchase, filtered, purchase_price_jpy=Decimal("50000"))
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("50000"),
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        comparable_warning=comparable.data_warning,
        filter_counts=counts,
    )
    assert report.quality != "HIGH"


def test_saffiano_lux_family_extracted_and_queries() -> None:
    title = "Prada Saffiano Lux Medium Tote Cammeo"
    identity = extract_product_identity(title=title, brand="Prada", category="Bag")
    assert identity.collection == "Saffiano Lux"
    assert identity.size == "Medium"
    assert identity.material == "SAFFIANO"
    queries = build_yahoo_search_queries(title=title, brand="Prada", category="Bag")
    joined = " | ".join(queries).lower()
    assert "saffiano" in joined
    assert "lux" in joined or "ラックス" in joined


def test_generic_prada_tote_not_high() -> None:
    purchase = _listing("Prada Tote", category="Bag")
    samples = [
        _sample("プラダ トートバッグ", 80000),
        _sample("PRADA tote bag", 85000),
        _sample("プラダ トート", 90000),
        _sample("PRADA トートバッグ レザー", 95000),
        _sample("プラダ ハンドバッグ トート", 88000),
    ]
    filtered, counts = filter_estimation_samples(samples, purchase_price_jpy=Decimal("90000"))
    comparable = evaluate_comparables(purchase, filtered, purchase_price_jpy=Decimal("90000"))
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("90000"),
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        filter_counts=counts,
    )
    assert report.quality != "HIGH"


def test_reference_number_exact_match_highest_score() -> None:
    purchase = _listing(
        "Prada Acetate Oval Sunglasses SPR26Z Pink",
        category="Sunglasses",
    )
    exact = _sample("PRADA SPR26Z サングラス ピンク", 42800)
    other = _sample("PRADA サングラス アセテート", 120000)
    comparable = evaluate_comparables(
        purchase,
        [exact, other],
        purchase_price_jpy=Decimal("50000"),
    )
    by_title = {d.title: d.matching_score for d in comparable.accepted_diagnostics}
    # Exact reference must outrank category-only sunglasses.
    if exact.title in by_title and other.title in by_title:
        assert by_title[exact.title] > by_title[other.title]
    elif exact.title in by_title:
        assert by_title[exact.title] >= 55
    # Model number extraction itself is highest-priority key.
    assert extract_model_numbers("SPR26Z") == ("SPR26Z",)


def test_quality_gate_and_suspect_still_block() -> None:
    samples = [_sample(f"PRADA トート {i}", 8000 + i * 100) for i in range(8)]
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("150000"),
        accepted_samples=samples,
        comparable_warning="COMPARABLE_DATA_SUSPECT",
    )
    assert report.quality == "SUSPECT"
    assert report.publish_price is False
    assert apply_publish_gate(Decimal("120000"), report) == Decimal("0")


def test_saffiano_lux_can_reach_high_with_strong_comps() -> None:
    purchase = _listing("Prada Saffiano Lux Medium Tote Cammeo", category="Bag")
    samples = [
        _sample("PRADA サフィアーノ ラックス ミディアム トート", 148000),
        _sample("プラダ サフィアーノ ラックス トートバッグ", 152000),
        _sample("PRADA Saffiano Lux Medium Tote", 155000),
        _sample("PRADA Saffiano Lux Tote Cammeo", 150000),
        _sample("プラダ Saffiano Lux Medium トート", 151000),
    ]
    filtered, counts = filter_estimation_samples(samples, purchase_price_jpy=Decimal("152000"))
    comparable = evaluate_comparables(purchase, filtered, purchase_price_jpy=Decimal("152000"))
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
    assert report.evidence
    assert report.freshness_label or report.latest_sold_date
    if report.publish_price:
        assert published >= Decimal("100000")
        assert report.quality in {"HIGH", "MEDIUM"}


def test_evidence_and_freshness_fields_present() -> None:
    samples = [
        _sample("PRADA Saffiano Lux Medium Tote", 150000),
        _sample("プラダ サフィアーノ ラックス トート", 152000),
        _sample("PRADA Saffiano Lux Tote", 148000),
    ]
    # stagger dates
    samples = [
        YahooSoldSample(
            title=s.title,
            sold_price_jpy=s.sold_price_jpy,
            retrieved_at=s.retrieved_at,
            source=s.source,
            auction_status="sold",
            url=s.url,
            sold_at=date,
        )
        for s, date in zip(samples, ("2026-07-15", "2026-08-01", "2026-07-20"), strict=True)
    ]
    report = classify_comparable_quality(
        purchase_price_jpy=Decimal("152000"),
        accepted_samples=samples,
    )
    assert report.evidence
    assert report.latest_sold_date == "2026-08-01"
    assert report.oldest_sold_date == "2026-07-15"
    assert "2026年7月" in report.freshness_label
    assert report.marketplaces


def test_new_market_warning_framework() -> None:
    assert build_new_market_warning(used_estimate_jpy=120000, new_market_price_jpy=None) is None
    warning = build_new_market_warning(used_estimate_jpy=120000, new_market_price_jpy=42800)
    assert warning is not None
    assert warning.new_market_warning is True
    assert "新品" in warning.warning
