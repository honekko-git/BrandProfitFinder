"""Tests for The RealReal overseas acquisition integration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.acquisition_workspace.live_realreal_intake import (
    import_realreal_keyword,
    search_realreal_listings,
)
from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.acquisition_workspace.saved_html_parser import RealRealSavedHtmlParser, parse_saved_html
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.browser_acquisition.comparable_candidate import (
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    NEAR_MISS_SCORE_THRESHOLD,
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.matching_config import get_matching_config
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.models import YahooSoldSample
from marketplace.browser_acquisition.realreal_acquirer import RealRealAcquirer, parse_realreal_html
from marketplace.browser_acquisition.realreal_search_queries import build_realreal_identity_queries
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.discovery_validation.batch_profit.models import (
    BatchProfitCandidate,
    BatchProfitResult,
    EstimatedCosts,
    RobustDomesticEstimate,
)
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate
from tests.acquisition_test_helpers import make_candidate

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"
REALREAL_HTML = (FIXTURES / "realreal_search_results.html").read_text(encoding="utf-8")
REALREAL_EMPTY = (FIXTURES / "realreal_empty.html").read_text(encoding="utf-8")
REALREAL_CAPTCHA = (FIXTURES / "realreal_captcha.html").read_text(encoding="utf-8")
YAHOO_HTML = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
OPEN_HTML = (FIXTURES / "yahoo_open_results.html").read_text(encoding="utf-8")
MERCARI_HTML = (FIXTURES / "mercari_search_results.html").read_text(encoding="utf-8")


def test_realreal_search_query_priority_prefers_model_number() -> None:
    identity = extract_listing_identity(
        title="Louis Vuitton Pochette Metis M80481 Monogram",
        brand="LV",
        category="Bag",
    )
    queries = build_realreal_identity_queries(
        identity=identity,
        title=identity.cleaned_title,
        brand="LV",
        category="Bag",
    )
    assert queries
    assert any("M80481" in query for query in queries)


def test_parse_realreal_search_results_extracts_required_fields() -> None:
    listings = parse_realreal_html(REALREAL_HTML)
    assert len(listings) >= 10
    sample = listings[0]
    assert sample.source == "The RealReal"
    assert sample.title
    assert sample.price > 0
    assert sample.currency == "USD"
    assert sample.url.startswith("https://www.therealreal.com/products/")
    assert "Was:" not in sample.title


def test_individual_realreal_product_url_preserved() -> None:
    listings = parse_realreal_html(REALREAL_HTML)
    assert all("/products/" in item.url for item in listings)
    assert all(item.url.startswith("http") for item in listings)


def test_missing_url_is_skipped() -> None:
    html = """
    <html><body>
    <div data-testid="plp-product/1">
      <span>Chanel Wallet Black Caviar $695</span>
    </div>
    <div data-testid="plp-product/2">
      <a href="/products/women/accessories/wallets/chanel-classic-wallet-abcd">
        Chanel Classic Wallet $820.00
      </a>
    </div>
    </body></html>
    """
    listings = parse_realreal_html(html)
    assert len(listings) == 1
    assert "/products/women/accessories/wallets/chanel-classic-wallet-abcd" in listings[0].url


def test_missing_or_invalid_price_is_skipped() -> None:
    html = """
    <html><body>
    <div data-testid="plp-product/1">
      <a href="/products/women/accessories/wallets/chanel-no-price">Chanel Wallet</a>
    </div>
    <div data-testid="plp-product/2">
      <a href="/products/women/accessories/wallets/chanel-with-price">Chanel Wallet $100.00</a>
    </div>
    </body></html>
    """
    listings = parse_realreal_html(html)
    assert len(listings) == 1
    assert listings[0].price == Decimal("100.00")


def test_usd_sale_price_prefers_current_over_was_price() -> None:
    html = """
    <html><body>
    <div data-testid="plp-product/9">
      <a href="/products/women/accessories/wallets/chanel-sale-wallet-xyz1">
        Chanel Sale Wallet Was: $260 $208.00 Now 20% off
      </a>
    </div>
    </body></html>
    """
    listings = parse_realreal_html(html)
    assert len(listings) == 1
    assert listings[0].price == Decimal("208.00")


def test_usd_price_converts_via_existing_exchange_path() -> None:
    listings = parse_realreal_html(REALREAL_HTML)
    item = listings[0]
    jpy = purchase_price_jpy(item.price, item.currency)
    expected = item.price * Decimal(str(resolve_usd_jpy_exchange_rate()))
    assert jpy == expected
    assert jpy > 0


def test_realreal_identity_normalization() -> None:
    listings = parse_realreal_html(REALREAL_HTML)
    bag = next(item for item in listings if "Chanel" in item.title and "Wallet" in item.title)
    identity = extract_listing_identity(
        title=bag.title,
        brand=bag.brand,
        category=bag.category,
        condition=bag.condition,
    )
    assert identity.brand == "CHANEL"
    assert bag.category == "Wallet"


def test_blocked_captcha_page_without_products() -> None:
    result = RealRealAcquirer().search_keyword("Chanel", html=REALREAL_CAPTCHA)
    assert result.status.value == "BLOCKED"
    assert not result.listings


def test_empty_search_results() -> None:
    listings, status, detail = search_realreal_listings("Chanel", html=REALREAL_EMPTY)
    assert listings == []
    assert status == "BLOCKED"
    assert detail


def test_saved_html_fallback_parser() -> None:
    parser = RealRealSavedHtmlParser()
    assert parser.can_parse(REALREAL_HTML)
    parsed = parser.parse(REALREAL_HTML)
    assert len(parsed) >= 10
    assert all(item.source_name == "The RealReal" for item in parsed)
    assert all(item.purchase_url.startswith("http") for item in parsed)
    rows, strategy, _meta = parse_saved_html(REALREAL_HTML)
    assert strategy == "realreal_saved_html"
    assert len(rows) >= 10


def test_realreal_import_searches_yahoo_and_mercari(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "realreal.db")
    )
    listings = parse_realreal_html(REALREAL_HTML)[:3]
    yahoo_map: dict[str, str] = {}
    open_map: dict[str, str] = {}
    mercari_map: dict[str, str] = {}
    for item in listings:
        for query in build_yahoo_search_queries(title=item.title, brand=item.brand, category=item.category):
            yahoo_map[query] = YAHOO_HTML
            open_map[query] = OPEN_HTML
        for query in build_mercari_search_queries(title=item.title, brand=item.brand, category=item.category):
            mercari_map[query] = MERCARI_HTML

    result = import_realreal_keyword(
        service,
        "Chanel wallet",
        limit=3,
        html=REALREAL_HTML,
        acquirer=RealRealAcquirer(purchase_limit=3),
        run_profit=True,
        html_by_query=yahoo_map,
        open_html_by_query=open_map,
        mercari_html_by_query=mercari_map,
    )
    assert result.batch_id
    assert result.listing_count >= 1
    assert result.profit_checked is True
    _batch, rows = service.get_batch(result.batch_id)
    assert all(row.source_name == "The RealReal" for row in rows)
    assert all(row.purchase_url.startswith("http") for row in rows)


def test_realreal_uses_existing_matching_thresholds_and_hard_rejects() -> None:
    config = get_matching_config()
    assert COMPARABLE_SCORE_THRESHOLD == config.thresholds.accept_threshold == 70
    assert NEAR_MISS_SCORE_THRESHOLD == config.thresholds.near_miss_threshold == 45
    listing = parse_realreal_html(REALREAL_HTML)[0]
    samples = [
        YahooSoldSample(
            title="コインケース シャネル",
            sold_price_jpy=12000,
            retrieved_at="2026-07-31T00:00:00+00:00",
            source="Yahoo Auctions",
            url="https://auctions.yahoo.co.jp/jp/auction/hard1",
        ),
        YahooSoldSample(
            title=f"シャネル {listing.title} 財布",
            sold_price_jpy=90000,
            retrieved_at="2026-07-31T00:00:00+00:00",
            source="Yahoo Auctions",
            url="https://auctions.yahoo.co.jp/jp/auction/ok1",
        ),
    ]
    result = evaluate_comparables(listing, samples)
    assert result.rejected_count >= 1
    assert any(
        RejectionReason.HARD_EXCLUSION.value in reason or "coin" in reason.lower()
        for diagnostic in result.rejected_diagnostics
        for reason in diagnostic.rejection_reasons
    ) or any(
        RejectionReason.HARD_EXCLUSION.value in diagnostic.rejection_reasons
        or RejectionReason.SUBTYPE_MISMATCH.value in diagnostic.rejection_reasons
        for diagnostic in result.rejected_diagnostics
    )


def test_realreal_profit_calculator_integration() -> None:
    listing = parse_realreal_html(REALREAL_HTML)[0]
    purchase_jpy = purchase_price_jpy(listing.price, listing.currency)
    product = Product(
        name=listing.title,
        brand=listing.brand or "Chanel",
        price=float(listing.price),
        currency=listing.currency,
        store_name="The RealReal",
        url=listing.url,
        exchange_rate=float(resolve_usd_jpy_exchange_rate()),
    )
    result = ProfitCalculator().calculate(product, Decimal("120000"), domestic_market="Yahoo Auctions")
    assert result.calculation_status == "success"
    assert purchase_jpy > 0
    assert listing.url.startswith("https://www.therealreal.com/products/")


def test_realreal_never_in_domestic_comparable_selector() -> None:
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
    assert selected.marketplace != "The RealReal"


def test_ranking_and_detail_retain_realreal_acquisition_and_domestic_urls() -> None:
    candidate = make_candidate(
        source_name="The RealReal",
        purchase_url="https://www.therealreal.com/products/women/accessories/wallets/chanel-demo-abcd",
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
        purchase_source="The RealReal",
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
    assert detail.marketplace == "The RealReal"
    assert detail.purchase_url.startswith("https://www.therealreal.com/products/")
    pairs = detail.sales_info
    assert any(label == "Marketplace" and value == "Yahoo Auctions" for label, value in pairs)
    assert any(label == "URL" and "auctions.yahoo.co.jp" in value for label, value in pairs)
    assert any(label == "Listing URL" and "therealreal.com" in value for label, value in pairs)


def test_realreal_route_accepts_saved_html(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "route.db"

    def _service_factory(_request):
        return AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))

    app = create_app()
    import app.routes as routes
    import marketplace.acquisition_workspace.live_realreal_intake as intake

    original_import = intake.import_realreal_keyword

    def _import_without_live_profit(service, keyword, **kwargs):
        kwargs["run_profit"] = False
        return original_import(service, keyword, **kwargs)

    monkeypatch.setattr(routes, "_get_acquisition_service", lambda request: _service_factory(request))
    monkeypatch.setattr(intake, "import_realreal_keyword", _import_without_live_profit)
    client = TestClient(app)
    response = client.post(
        "/acquisition-workspace/import/realreal-live",
        data={"keyword": "Chanel", "limit": "5"},
        files={"html_file": ("realreal.html", REALREAL_HTML.encode("utf-8"), "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "acquisition-workspace" in response.headers.get("location", "")
