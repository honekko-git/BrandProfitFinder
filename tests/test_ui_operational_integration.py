"""Version 1.0 RC UI operational integration tests.

Covers browser-only sourcing workflow: empty state, live/HTML intake,
workspace population, profit analysis, ranking filters, detail page,
and humanized acquisition errors — without auto-injected demo data.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.main import create_app
from marketplace.acquisition_workspace.ui_messaging import humanize_intake_error
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as _real_run_batch_profit

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"
HTML_FIXTURES = FIXTURES / "browser_acquisition"
YAHOO_HTML = HTML_FIXTURES.joinpath("yahoo_live_ja.html").read_text(encoding="utf-8")


def _client(tmp_path: Path, name: str = "ops.db") -> TestClient:
    return TestClient(create_app(database_path=tmp_path / name))


def test_empty_workspace_message_without_demo(tmp_path: Path) -> None:
    client = _client(tmp_path, "empty.db")
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "No acquisition candidates have been imported." in page.text
    assert "No analyzed opportunities." in page.text
    assert "デモ表示中" not in page.text
    assert "example.com/demo/" not in page.text
    assert "Fashionphile検索" in page.text
    assert "Rebag検索" in page.text
    assert "The RealReal検索" in page.text
    assert "Vestiaire Collective検索" in page.text
    assert "data-live-acquisition-form" in page.text
    assert "最終実行" in page.text


def test_saved_html_import_populates_workspace(tmp_path: Path) -> None:
    client = _client(tmp_path, "html.db")
    html = HTML_FIXTURES.joinpath("fashionphile_search_results.html").read_bytes()
    redirect = client.post(
        "/acquisition-workspace/import/html",
        files={"html_files": ("fashionphile_search_results.html", BytesIO(html), "text/html")},
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    location = redirect.headers["location"]
    assert "intake_ok=1" in location
    assert "batch_id=" in location
    page = client.get(location)
    assert page.status_code == 200
    assert "Imported" in page.text
    assert "デモ表示中" not in page.text
    assert "Fashionphile" in page.text or "Chanel" in page.text
    assert "data-purchase-jpy" in page.text
    assert "data-brand" in page.text
    assert "data-purchase-url" in page.text
    assert "利益分析" in page.text


def test_live_fashionphile_saved_html_search_imports_candidates(tmp_path: Path, monkeypatch) -> None:
    from marketplace.acquisition_workspace import live_fashionphile_intake as intake_mod
    from marketplace.browser_acquisition.fashionphile_acquirer import FashionphileAcquirer, parse_fashionphile_html
    from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries

    fixture_html = HTML_FIXTURES.joinpath("fashionphile_search_results.html").read_text(encoding="utf-8")
    original = intake_mod.import_fashionphile_keyword

    def _import(service, keyword, *, limit=20, html=None, acquirer=None, run_profit=True, html_by_query=None):
        listings = parse_fashionphile_html(fixture_html)[: max(1, min(int(limit), 5))]
        yahoo_map = {
            query: YAHOO_HTML
            for item in listings
            for query in build_yahoo_search_queries(title=item.title, brand=item.brand, category=item.category)[:2]
        }
        return original(
            service,
            keyword,
            limit=min(int(limit), 5),
            html=fixture_html,
            acquirer=acquirer or FashionphileAcquirer(purchase_limit=5),
            run_profit=False,
            html_by_query=yahoo_map,
        )

    monkeypatch.setattr(intake_mod, "import_fashionphile_keyword", _import)
    client = _client(tmp_path, "live-fp.db")
    redirect = client.post(
        "/acquisition-workspace/import/fashionphile-live",
        data={"keyword": "Chanel", "limit": "5"},
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    location = redirect.headers["location"]
    assert "intake_ok=1" in location
    assert "marketplace=Fashionphile" in location or "Fashionphile" in location
    page = client.get(location)
    assert "Imported" in page.text
    assert "Rejected" in page.text
    assert "Fashionphile" in page.text
    assert "利益分析" in page.text
    assert "Purchase Budget" in page.text
    assert "All Brands" in page.text


def test_profit_analysis_and_ranking_generation(tmp_path: Path, monkeypatch) -> None:
    def _inject(candidates, **kwargs):
        kwargs["html_by_query"] = {query: YAHOO_HTML for query in (
            "シャネル キャビアスキン 財布 黒",
            "シャネル クラシック 財布",
            "CHANEL wallet caviar black",
        )}
        return _real_run_batch_profit(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _inject,
    )
    client = _client(tmp_path, "profit.db")
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    batch_id = parse_qs(urlparse(redirect.headers["location"]).query)["batch_id"][0]
    client.post(f"/acquisition-workspace/{batch_id}/select-all-eligible")
    run = client.post(
        f"/acquisition-workspace/{batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert run.status_code == 303
    assert "profit_ok=1" in run.headers["location"]
    page = client.get(run.headers["location"])
    assert "利益分析が完了しました" in page.text
    assert "デモ表示中" not in page.text
    assert "Chanel" in page.text or "Wallet" in page.text
    assert "data-ops-ranking-table" in page.text
    assert "data-budget-filter" in page.text
    assert "data-brand-filter" in page.text
    assert "≤ ¥50,000" in page.text
    assert "≤ ¥1,000,000" in page.text


def test_purchase_budget_and_brand_filter_markup(tmp_path: Path) -> None:
    client = _client(tmp_path, "filters.db")
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    page = client.get(redirect.headers["location"])
    assert 'data-budget-filter' in page.text
    assert 'value="unlimited"' in page.text
    assert 'value="50000"' in page.text
    assert 'value="100000"' in page.text
    assert 'value="150000"' in page.text
    assert 'value="300000"' in page.text
    assert 'value="500000"' in page.text
    assert 'value="1000000"' in page.text
    assert 'data-brand-filter' in page.text
    assert "All Brands" in page.text
    assert 'data-purchase-jpy="' in page.text
    assert 'data-brand="' in page.text
    # Brand options come from imported candidates.
    assert "Chanel" in page.text or "CHANEL" in page.text


def test_detail_page_shows_acquisition_and_profit_fields(tmp_path: Path) -> None:
    client = _client(tmp_path, "detail.db")
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    ranking = client.get(redirect.headers["location"])
    marker = "/acquisition-workspace/candidate/"
    start = ranking.text.index(marker)
    end = ranking.text.index('"', start)
    detail_path = ranking.text[start:end].replace("&amp;", "&")
    detail = client.get(detail_path)
    assert detail.status_code == 200
    assert "純利益" in detail.text
    assert "ROI" in detail.text
    assert "Marketplace" in detail.text or "sourcing-detail-meta" in detail.text
    assert "注意事項" in detail.text or "Warning" in detail.text or "data-component=\"WarningList\"" in detail.text
    assert "商品ページを開く" in detail.text or "Listing URL" in detail.text


def test_blocked_captcha_no_products_error_messages(tmp_path: Path, monkeypatch) -> None:
    from marketplace.acquisition_workspace.live_fashionphile_intake import LiveFashionphileIntakeResult

    def _blocked(*_args, **_kwargs):
        return LiveFashionphileIntakeResult(
            batch_id="",
            query="Chanel",
            listing_count=0,
            status="BLOCKED",
            detail="blocked_by_site: policy_restriction",
            errors=("blocked_by_site: policy_restriction",),
        )

    monkeypatch.setattr(
        "marketplace.acquisition_workspace.live_fashionphile_intake.import_fashionphile_keyword",
        _blocked,
    )
    client = _client(tmp_path, "blocked.db")
    redirect = client.post(
        "/acquisition-workspace/import/fashionphile-live",
        data={"keyword": "Chanel", "limit": "5"},
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    assert "intake_error=" in redirect.headers["location"]
    page = client.get(redirect.headers["location"])
    assert "ブロック" in page.text
    assert "Traceback" not in page.text


def test_captcha_error_message(tmp_path: Path, monkeypatch) -> None:
    from marketplace.acquisition_workspace.live_rebag_intake import LiveRebagIntakeResult

    def _captcha(*_args, **_kwargs):
        return LiveRebagIntakeResult(
            batch_id="",
            query="Louis Vuitton",
            listing_count=0,
            status="CAPTCHA",
            detail="CAPTCHA challenge page",
            errors=("CAPTCHA challenge page",),
        )

    monkeypatch.setattr(
        "marketplace.acquisition_workspace.live_rebag_intake.import_rebag_keyword",
        _captcha,
    )
    client = _client(tmp_path, "captcha.db")
    redirect = client.post(
        "/acquisition-workspace/import/rebag-live",
        data={"keyword": "Louis Vuitton", "limit": "5"},
        follow_redirects=False,
    )
    page = client.get(redirect.headers["location"])
    assert "CAPTCHA" in page.text
    assert "Traceback" not in page.text


def test_no_products_and_invalid_html_messaging(tmp_path: Path) -> None:
    client = _client(tmp_path, "noprod.db")
    redirect = client.post(
        "/acquisition-workspace/import/html",
        files={"html_files": ("empty.html", BytesIO(b"<html><body>no items</body></html>"), "text/html")},
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    page = client.get(redirect.headers["location"])
    assert "商品" in page.text or "見つかりません" in page.text or "intake_error" in redirect.headers["location"]
    assert "Traceback" not in page.text


def test_humanize_intake_error_cases() -> None:
    assert "CAPTCHA" in humanize_intake_error("cf-challenge captcha wall")
    assert "ブロック" in humanize_intake_error("blocked_by_site")
    assert "商品" in humanize_intake_error("No products found")
    assert "通貨" in humanize_intake_error("unsupported currency XYZ")
    assert "比較" in humanize_intake_error("no domestic comparable found")
    assert "無効なHTML" in humanize_intake_error("invalid html upload")
    assert "Traceback" not in humanize_intake_error('Traceback (most recent call last):\n  File "x.py"')


def test_four_source_panels_and_regression_routes(tmp_path: Path) -> None:
    client = _client(tmp_path, "panels.db")
    page = client.get("/acquisition-workspace")
    for action in (
        "/acquisition-workspace/import/fashionphile-live",
        "/acquisition-workspace/import/rebag-live",
        "/acquisition-workspace/import/realreal-live",
        "/acquisition-workspace/import/vestiaire-live",
    ):
        assert f'action="{action}"' in page.text
    assert "Yahooキャッシュを使用" in page.text or "利益分析" in page.text or "商品を追加" in page.text
    # Explicit demo remains available for development.
    demo = client.get("/acquisition-workspace?demo=1")
    assert "デモ表示中" in demo.text
    assert "マトラッセ" in demo.text or "Chanel" in demo.text or "CHANEL" in demo.text


def test_landing_uses_latest_history_not_demo(tmp_path: Path) -> None:
    client = _client(tmp_path, "history.db")
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    landing = client.get("/acquisition-workspace")
    assert "デモ表示中" not in landing.text
    assert "Chanel Classic Wallet" in landing.text
    assert "利益分析" in landing.text
