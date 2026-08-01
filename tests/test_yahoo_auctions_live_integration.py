"""Tests for Yahoo Auctions live open-search integration into profit/detail."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_comparable import select_best_yahoo_comparable
from marketplace.browser_acquisition.yahoo_open_acquirer import parse_yahoo_open_html
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_identity_queries, build_yahoo_search_queries
from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.connectors.models import MarketListing
from marketplace.importers.manual_importer import ManualImporter
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit
from profit_discovery.discovery_validation.real_profit_verification import build_real_profit_verifications
from datetime import UTC, datetime

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"
OPEN_HTML = (FIXTURES / "yahoo_open_results.html").read_text(encoding="utf-8")
SOLD_HTML = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")


def test_parse_yahoo_open_html_extracts_live_fields() -> None:
    samples = parse_yahoo_open_html(OPEN_HTML)
    assert len(samples) >= 2
    top = samples[0]
    assert top.title
    assert top.sold_price_jpy > 0
    assert top.url.startswith("http")
    assert top.buyout_price_jpy == 198000 or top.auction_status in {"active", "buy_now", "auction"}
    assert top.bid_count is None or top.bid_count >= 0


def test_identity_queries_prefer_model_number() -> None:
    identity = extract_listing_identity(
        title="Louis Vuitton Pochette Metis M80481 Monogram",
        brand="LV",
        category="Bag",
    )
    queries = build_yahoo_identity_queries(identity=identity, title=identity.cleaned_title, brand="LV", category="Bag")
    assert queries
    assert any("M80481" in query for query in queries)


def test_select_best_yahoo_comparable_prefers_high_score() -> None:
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
    samples = [
        YahooSoldSample(
            title="シャネル クラシック ウォレット 黒 キャビアスキン",
            sold_price_jpy=180000,
            retrieved_at="t",
            source="Yahoo Auction",
            url="https://auctions.yahoo.co.jp/jp/auction/x1",
        ),
        YahooSoldSample(
            title="シャネル コインケース 黒 キャビア",
            sold_price_jpy=25000,
            retrieved_at="t",
            source="Yahoo Auction",
            url="https://auctions.yahoo.co.jp/jp/auction/x2",
        ),
    ]
    result = evaluate_comparables(purchase, samples, purchase_price_jpy=Decimal("111200"))
    best = select_best_yahoo_comparable(purchase, result)
    assert best is not None
    assert best.price_jpy == 180000
    assert "auctions.yahoo.co.jp" in best.url
    assert best.matching_score > 0


def test_batch_profit_sets_yahoo_best_match_fields() -> None:
    from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate

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
    queries = build_yahoo_search_queries(title=candidate.title, brand=candidate.brand, category=candidate.category)
    html_by_query = {query: SOLD_HTML for query in queries}
    open_by_query = {query: OPEN_HTML for query in queries}
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")
    run = run_batch_profit(
        [candidate],
        cost_profile=profile,
        use_cache=False,
        html_by_query=html_by_query,
        open_html_by_query=open_by_query,
    )
    item = run.results[0]
    assert item.yahoo_best_title
    assert item.yahoo_best_price_jpy > 0
    assert item.yahoo_marketplace == "Yahoo Auctions"
    assert item.yahoo_best_score > 0


def test_detail_sales_info_includes_yahoo_match_rows() -> None:
    from tests.acquisition_test_helpers import make_candidate
    from profit_discovery.discovery_validation.batch_profit.models import (
        BatchProfitCandidate,
        BatchProfitResult,
        EstimatedCosts,
        RobustDomesticEstimate,
    )

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
        yahoo_best_price_jpy=185000,
        yahoo_best_url="https://auctions.yahoo.co.jp/jp/auction/openchanel001",
        yahoo_best_score=85,
        yahoo_best_attributes="material:CAVIAR; color:BLACK",
        yahoo_marketplace="Yahoo Auctions",
    )
    detail = build_sourcing_detail(candidate=candidate, batch_result=batch_result, batch_id="b1")
    pairs = detail.sales_info
    assert ("Marketplace", "Yahoo Auctions") in pairs
    assert any(label == "Title" and value.startswith("シャネル") for label, value in pairs)
    assert any(label == "Price" and ("185,000" in value or "¥" in value) for label, value in pairs)
    assert any(label == "URL" and "auctions.yahoo.co.jp" in value for label, value in pairs)
    assert ("Matching confidence", "85") in pairs
    assert any(label == "Matched attributes" and "material" in value for label, value in pairs)