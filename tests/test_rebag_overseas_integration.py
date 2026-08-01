"""Tests for Rebag overseas acquisition integration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.acquisition_workspace.live_rebag_intake import (
    import_rebag_keyword,
    search_rebag_listings,
)
from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.acquisition_workspace.saved_html_parser import RebagSavedHtmlParser, parse_saved_html
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.browser_acquisition.comparable_candidate import (
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.rebag_acquirer import RebagAcquirer, parse_rebag_html
from marketplace.browser_acquisition.rebag_search_queries import build_rebag_identity_queries
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from profit_discovery.discovery_validation.batch_profit.models import (
    BatchProfitCandidate,
    BatchProfitResult,
    EstimatedCosts,
    RobustDomesticEstimate,
)
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate
from tests.acquisition_test_helpers import make_candidate

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"
REBAG_HTML = (FIXTURES / "rebag_search_results.html").read_text(encoding="utf-8")
REBAG_EMPTY = (FIXTURES / "rebag_empty.html").read_text(encoding="utf-8")
REBAG_CAPTCHA = (FIXTURES / "rebag_captcha.html").read_text(encoding="utf-8")
YAHOO_HTML = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
OPEN_HTML = (FIXTURES / "yahoo_open_results.html").read_text(encoding="utf-8")
MERCARI_HTML = (FIXTURES / "mercari_search_results.html").read_text(encoding="utf-8")


def test_rebag_search_query_priority_prefers_model_number() -> None:
    identity = extract_listing_identity(
        title="Louis Vuitton Pochette Metis M80481 Monogram",
        brand="LV",
        category="Bag",
    )
    queries = build_rebag_identity_queries(
        identity=identity,
        title=identity.cleaned_title,
        brand="LV",
        category="Bag",
    )
    assert queries
    assert any("M80481" in query for query in queries)


def test_parse_rebag_search_results_extracts_required_fields() -> None:
    listings = parse_rebag_html(REBAG_HTML)
    assert len(listings) >= 10
    sample = listings[0]
    assert sample.source == "Rebag"
    assert sample.title
    assert sample.price > 0
    assert sample.currency == "USD"
    assert sample.url.startswith("https://www.rebag.com/products/")
    assert sample.condition


def test_individual_rebag_product_url_preserved() -> None:
    listings = parse_rebag_html(REBAG_HTML)
    assert all("/products/" in item.url for item in listings)
    assert all(item.url.startswith("http") for item in listings)


def test_missing_url_is_skipped() -> None:
    html = """
    <html><body>
    <div class="plp__product" data-product-id="1">
      <span class="title">Chanel Wallet Black Caviar</span>
      <span class="price">$695</span>
    </div>
    <div class="plp__product" data-product-id="2">
      <a class="plp__card" href="/products/handbags-chanel-classic-wallet-black-2">
        Chanel Classic Wallet Black Caviar Excellent Condition $820
      </a>
    </div>
    </body></html>
    """
    listings = parse_rebag_html(html)
    assert len(listings) == 1
    assert listings[0].url.endswith("/products/handbags-chanel-classic-wallet-black-2")


def test_missing_or_invalid_price_is_skipped() -> None:
    html = """
    <html><body>
    <div class="plp__product" data-product-id="1">
      <a href="/products/handbags-chanel-no-price">Chanel Wallet</a>
    </div>
    <div class="plp__product" data-product-id="2">
      <a href="/products/handbags-chanel-with-price">Chanel Wallet Excellent Condition $100</a>
    </div>
    </body></html>
    """
    listings = parse_rebag_html(html)
    assert len(listings) == 1
    assert listings[0].price == Decimal("100")


def test_usd_price_converts_via_existing_exchange_path() -> None:
    listings = parse_rebag_html(REBAG_HTML)
    item = listings[0]
    jpy = purchase_price_jpy(item.price, item.currency)
    expected = item.price * Decimal(str(resolve_usd_jpy_exchange_rate()))
    assert jpy == expected
    assert jpy > 0


def test_rebag_condition_and_identity_normalization() -> None:
    listings = parse_rebag_html(REBAG_HTML)
    bag = next(item for item in listings if "Chanel" in item.title and "Flap" in item.title)
    assert "Condition" in bag.condition
    identity = extract_listing_identity(
        title=bag.title,
        brand=bag.brand,
        category=bag.category,
        condition=bag.condition,
    )
    assert identity.brand == "CHANEL"
    assert bag.category


def test_blocked_captcha_page_without_products() -> None:
    result = RebagAcquirer().search_keyword("Chanel", html=REBAG_CAPTCHA)
    assert result.status.value == "BLOCKED"
    assert not result.listings


def test_empty_search_results() -> None:
    listings, status, detail = search_rebag_listings("Chanel", html=REBAG_EMPTY)
    assert listings == []
    assert status == "BLOCKED"
    assert detail


def test_saved_html_fallback_parser() -> None:
    parser = RebagSavedHtmlParser()
    assert parser.can_parse(REBAG_HTML)
    parsed = parser.parse(REBAG_HTML)
    assert len(parsed) >= 10
    assert all(item.source_name == "Rebag" for item in parsed)
    assert all(item.purchase_url.startswith("http") for item in parsed)
    rows, strategy, _meta = parse_saved_html(REBAG_HTML)
    assert strategy == "rebag_saved_html"
    assert len(rows) >= 10


def test_rebag_import_searches_yahoo_and_mercari(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "rebag.db")
    )
    listings = parse_rebag_html(REBAG_HTML)[:3]
    yahoo_map: dict[str, str] = {}
    open_map: dict[str, str] = {}
    mercari_map: dict[str, str] = {}
    for item in listings:
        for query in build_yahoo_search_queries(title=item.title, brand=item.brand, category=item.category):
            yahoo_map[query] = YAHOO_HTML
            open_map[query] = OPEN_HTML
        for query in build_mercari_search_queries(title=item.title, brand=item.brand, category=item.category):
            mercari_map[query] = MERCARI_HTML

    result = import_rebag_keyword(
        service,
        "luxury bags",
        limit=3,
        html=REBAG_HTML,
        acquirer=RebagAcquirer(purchase_limit=3),
        run_profit=True,
        html_by_query=yahoo_map,
        open_html_by_query=open_map,
        mercari_html_by_query=mercari_map,
    )
    assert result.batch_id
    assert result.listing_count >= 1
    assert result.profit_checked is True
    _batch, rows = service.get_batch(result.batch_id)
    assert all(row.source_name == "Rebag" for row in rows)
    assert all(row.purchase_url.startswith("http") for row in rows)


def test_rebag_never_required_in_domestic_comparable_selector() -> None:
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
    selected = select_best_comparable_candidate(
        [
            candidate_from_best_comparable(yahoo, marketplace="Yahoo Auctions"),
            candidate_from_best_comparable(mercari, marketplace="Mercari"),
        ]
    )
    assert selected is not None
    assert selected.marketplace in {"Yahoo Auctions", "Mercari"}
    assert selected.marketplace != "Rebag"


def test_yahoo_and_mercari_can_win_as_domestic_comparables() -> None:
    yahoo = YahooBestComparable(
        title="yahoo",
        price_jpy=100000,
        url="https://auctions.yahoo.co.jp/jp/auction/x1",
        matching_score=90,
        matched_attributes="score:90",
    )
    mercari = YahooBestComparable(
        title="mercari",
        price_jpy=120000,
        url="https://jp.mercari.com/item/m1",
        matching_score=70,
        matched_attributes="score:70",
    )
    selected = select_best_comparable_candidate(
        [
            candidate_from_best_comparable(yahoo, marketplace="Yahoo Auctions"),
            candidate_from_best_comparable(mercari, marketplace="Mercari"),
        ]
    )
    assert selected is not None
    assert selected.marketplace == "Yahoo Auctions"

    selected2 = select_best_comparable_candidate(
        [
            candidate_from_best_comparable(yahoo, marketplace="Yahoo Auctions"),
            candidate_from_best_comparable(
                YahooBestComparable(
                    title="mercari-high",
                    price_jpy=130000,
                    url="https://jp.mercari.com/item/m2",
                    matching_score=95,
                    matched_attributes="score:95",
                    identity_material="CAVIAR",
                ),
                marketplace="Mercari",
            ),
        ]
    )
    assert selected2 is not None
    assert selected2.marketplace == "Mercari"


def test_ranking_and_detail_retain_rebag_acquisition_and_domestic_urls() -> None:
    candidate = make_candidate(
        source_name="Rebag",
        purchase_url="https://www.rebag.com/products/handbags-chanel-demo",
    )

    domestic = RobustDomesticEstimate(
        raw_sample_count=2,
        accepted_count=2,
        rejected_count=0,
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
        purchase_source="Rebag",
    )
    batch_result = BatchProfitResult(
        candidate=batch_candidate,
        yahoo_queries=("q",),
        yahoo_data_source="LIVE",
        yahoo_cache_retrieved_at="",
        yahoo_cache_age_hours=None,
        raw_sample_count=2,
        accepted_comparable_count=2,
        rejected_sample_count=0,
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
        yahoo_best_title="シャネル クラシック",
        yahoo_best_price_jpy=185000,
        yahoo_best_url="https://auctions.yahoo.co.jp/jp/auction/open1",
        yahoo_best_score=85,
        yahoo_best_attributes="material:CAVIAR",
        yahoo_marketplace="Yahoo Auctions",
    )
    detail = build_sourcing_detail(candidate=candidate, batch_result=batch_result, batch_id="b1")
    assert detail.marketplace == "Rebag"
    assert detail.purchase_url.startswith("https://www.rebag.com/products/")
    pairs = detail.sales_info
    assert any(label == "Marketplace" and value == "Yahoo Auctions" for label, value in pairs)
    assert any(label == "URL" and "auctions.yahoo.co.jp" in value for label, value in pairs)
    assert any(label == "Listing URL" and "rebag.com" in value for label, value in pairs)


def test_rebag_route_accepts_saved_html(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "route.db"

    def _service_factory(_request):
        return AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))

    app = create_app()
    import app.routes as routes

    monkeypatch.setattr(routes, "_get_acquisition_service", lambda request: _service_factory(request))
    client = TestClient(app)
    response = client.post(
        "/acquisition-workspace/import/rebag-live",
        data={"keyword": "Chanel", "limit": "5"},
        files={"html_file": ("rebag.html", REBAG_HTML.encode("utf-8"), "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "acquisition-workspace" in response.headers.get("location", "")
