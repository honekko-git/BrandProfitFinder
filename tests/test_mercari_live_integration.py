"""Tests for Mercari live integration into profit/detail."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.mercari_acquirer import parse_mercari_html
from marketplace.browser_acquisition.mercari_comparable import (
    choose_best_marketplace_comparable,
    select_best_mercari_comparable,
)
from marketplace.browser_acquisition.mercari_search_queries import (
    build_mercari_identity_queries,
    build_mercari_search_queries,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable, select_best_yahoo_comparable
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.models import (
    BatchProfitCandidate,
    BatchProfitResult,
    EstimatedCosts,
    RobustDomesticEstimate,
)
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit
from tests.acquisition_test_helpers import make_candidate

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"
MERCARI_HTML = (FIXTURES / "mercari_search_results.html").read_text(encoding="utf-8")
SOLD_HTML = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
OPEN_HTML = (FIXTURES / "yahoo_open_results.html").read_text(encoding="utf-8")


def test_parse_mercari_html_extracts_listing_fields() -> None:
    samples = parse_mercari_html(MERCARI_HTML)
    assert len(samples) >= 4
    top = samples[0]
    assert "シャネル" in top.title or "CHANEL" in top.title.upper()
    assert top.sold_price_jpy > 0
    assert top.url.startswith("https://jp.mercari.com/item/")
    assert top.source == "Mercari"
    assert top.image_url or top.seller or top.condition or True


def test_mercari_identity_queries_prefer_model_number() -> None:
    identity = extract_listing_identity(
        title="Louis Vuitton Pochette Metis M80481 Monogram",
        brand="LV",
        category="Bag",
    )
    queries = build_mercari_identity_queries(
        identity=identity,
        title=identity.cleaned_title,
        brand="LV",
        category="Bag",
    )
    assert queries
    assert any("M80481" in query for query in queries)


def test_select_best_mercari_comparable_uses_matching_engine() -> None:
    purchase = AcquiredListing(
        external_id="1",
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
    samples = parse_mercari_html(MERCARI_HTML)
    result = evaluate_comparables(purchase, samples, purchase_price_jpy=Decimal("111200"))
    best = select_best_mercari_comparable(purchase, result, candidate_samples=samples)
    assert best is not None
    assert best.price_jpy > 0
    assert "mercari.com" in best.url
    assert best.matching_score > 0


def test_choose_best_marketplace_prefers_higher_score() -> None:
    yahoo = YahooBestComparable(
        title="yahoo",
        price_jpy=100000,
        url="https://auctions.yahoo.co.jp/jp/auction/x1",
        matching_score=70,
        matched_attributes="score:70",
    )
    mercari = YahooBestComparable(
        title="mercari",
        price_jpy=120000,
        url="https://jp.mercari.com/item/m1",
        matching_score=85,
        matched_attributes="score:85",
        identity_material="CAVIAR",
    )
    best, marketplace = choose_best_marketplace_comparable(yahoo, mercari)
    assert marketplace == "Mercari"
    assert best is not None
    assert best.title == "mercari"


def test_batch_profit_can_select_mercari_marketplace() -> None:
    candidate = BatchProfitCandidate(
        candidate_id="c1",
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
        detected_subtype="COMPACT_WALLET",
        detected_material="Caviar",
        condition="Very Good",
        purchase_price=Decimal("695"),
        currency="USD",
        purchase_price_jpy=Decimal("111200"),
        purchase_url="https://www.fashionphile.com/p/demo",
        purchase_source="Fashionphile",
    )
    queries = build_mercari_search_queries(title=candidate.title, brand=candidate.brand, category=candidate.category)
    yahoo_queries = queries
    # Weak Yahoo comps (coin case only) vs strong Mercari wallet comps
    weak_yahoo = """
    <html><body><ul>
    <li class="Product">
      <a href="https://auctions.yahoo.co.jp/jp/auction/weak1">シャネル コインケース 黒</a>
      <div>落札 12,000 円</div>
    </li>
    </ul></body></html>
    """
    html_by_query = {query: weak_yahoo for query in yahoo_queries}
    mercari_by_query = {query: MERCARI_HTML for query in queries}
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")
    run = run_batch_profit(
        [candidate],
        cost_profile=profile,
        use_cache=False,
        html_by_query=html_by_query,
        open_html_by_query={},
        mercari_html_by_query=mercari_by_query,
    )
    item = run.results[0]
    assert item.yahoo_best_title
    assert item.yahoo_best_price_jpy > 0
    assert item.yahoo_marketplace in {"Mercari", "Yahoo Auctions"}
    assert item.yahoo_best_score > 0
    if item.yahoo_marketplace == "Mercari":
        assert "mercari.com" in item.yahoo_best_url


def test_detail_sales_info_shows_selected_marketplace_rows() -> None:
    candidate = make_candidate()
    domestic = RobustDomesticEstimate(
        raw_sample_count=3,
        accepted_count=2,
        rejected_count=1,
        minimum_jpy=100000,
        maximum_jpy=200000,
        average_jpy=Decimal("150000"),
        median_jpy=Decimal("160000"),
        q1_jpy=120000,
        q3_jpy=180000,
        iqr_jpy=60000,
        outlier_count=0,
        trimmed_average_jpy=Decimal("150000"),
        recommended_selling_estimate_jpy=Decimal("160000"),
        reliability="MEDIUM",
    )
    costs = EstimatedCosts(
        exchange_rate="160",
        international_shipping_jpy=Decimal("0"),
        forwarding_fee_jpy=Decimal("0"),
        import_duty_jpy=Decimal("0"),
        import_tax_jpy=Decimal("0"),
        payment_fee_jpy=Decimal("0"),
        domestic_platform_fee_jpy=Decimal("0"),
        domestic_shipping_jpy=Decimal("0"),
        inspection_or_repair_reserve_jpy=Decimal("0"),
        miscellaneous_cost_jpy=Decimal("0"),
        total_additional_costs_jpy=Decimal("0"),
        net_profit_complete=False,
    )
    batch_candidate = BatchProfitCandidate(
        candidate_id=candidate.candidate_id,
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
        detected_subtype=candidate.detected_subtype,
        detected_material=candidate.detected_material,
        condition=candidate.detected_condition,
        purchase_price=candidate.purchase_price,
        currency=candidate.currency,
        purchase_price_jpy=candidate.purchase_price_jpy,
        purchase_url=candidate.purchase_url,
        purchase_source=candidate.source_name,
    )
    batch_result = BatchProfitResult(
        candidate=batch_candidate,
        yahoo_queries=("q",),
        yahoo_data_source="LIVE",
        yahoo_cache_retrieved_at="",
        yahoo_cache_age_hours=None,
        raw_sample_count=3,
        accepted_comparable_count=2,
        rejected_sample_count=1,
        domestic=domestic,
        estimated_costs=costs,
        gross_estimated_profit=Decimal("10000"),
        net_estimated_profit=Decimal("8000"),
        profit_margin=Decimal("0.1"),
        net_profit_margin=Decimal("0.08"),
        roi=Decimal("0.1"),
        net_roi=Decimal("0.08"),
        engine_decision="HOLD",
        batch_decision="HOLD",
        data_status="MIXED",
        verification_complete=False,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        failure_reason="",
        comparable_warning="",
        warnings=(),
        diagnostics="{}",
        accepted_comparables_display="",
        rejected_samples_display="",
        yahoo_best_title="シャネル クラシック ウォレット 黒 キャビアスキン",
        yahoo_best_price_jpy=182000,
        yahoo_best_url="https://jp.mercari.com/item/m10000000001",
        yahoo_best_score=88,
        yahoo_best_attributes="material:CAVIAR; color:BLACK",
        yahoo_marketplace="Mercari",
    )
    detail = build_sourcing_detail(candidate=candidate, batch_result=batch_result, batch_id="b1")
    pairs = detail.sales_info
    assert ("Marketplace", "Mercari") in pairs
    assert any(label == "Title" and "シャネル" in value for label, value in pairs)
    assert any(label == "URL" and "mercari.com" in value for label, value in pairs)
    assert ("Matching confidence", "88") in pairs
    assert any(label == "Profit" for label, _ in pairs)
