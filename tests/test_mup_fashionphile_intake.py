"""MUP Fashionphile live intake: search -> import -> detail -> JPY -> profit."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.live_fashionphile_intake import (
    import_fashionphile_keyword,
    search_fashionphile_listings,
)
from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.browser_acquisition.fashionphile_acquirer import (
    FashionphileAcquirer,
    parse_fashionphile_html,
)
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"
MUP_HTML = FIXTURES / "fashionphile_mup_20.html"
YAHOO_HTML = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")


def _yahoo_map_for_titles(titles_brands_cats: list[tuple[str, str, str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for title, brand, category in titles_brands_cats:
        for query in build_yahoo_search_queries(title=title, brand=brand, category=category)[:3]:
            mapping[query] = YAHOO_HTML
    return mapping


def test_parse_fashionphile_mup_fixture_has_at_least_20_products() -> None:
    html = MUP_HTML.read_text(encoding="utf-8")
    listings = parse_fashionphile_html(html)
    assert len(listings) >= 20
    sample = listings[0]
    assert sample.title
    assert sample.price > 0
    assert sample.currency == "USD"
    assert sample.url.startswith("http")
    assert sample.condition


def test_search_keyword_returns_raw_listings_from_html() -> None:
    html = MUP_HTML.read_text(encoding="utf-8")
    listings, status, _detail = search_fashionphile_listings(
        "Chanel wallet",
        limit=20,
        html=html,
        acquirer=FashionphileAcquirer(purchase_limit=20),
    )
    assert status == "LIVE"
    assert len(listings) >= 20
    assert all(item.source == "Fashionphile" for item in listings)


def test_import_fashionphile_keyword_builds_jpy_and_detail_fields(tmp_path: Path) -> None:
    html = MUP_HTML.read_text(encoding="utf-8")
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "mup.db")
    )
    result = import_fashionphile_keyword(
        service,
        "luxury wallet",
        limit=20,
        html=html,
        acquirer=FashionphileAcquirer(purchase_limit=20),
        run_profit=False,
    )
    assert result.batch_id
    assert result.listing_count >= 20
    assert result.profit_checked is False

    _batch, rows = service.get_batch(result.batch_id)
    assert len(rows) >= 20
    rate = Decimal(str(resolve_usd_jpy_exchange_rate()))
    for row in rows[:5]:
        assert row.source_name == "Fashionphile"
        assert row.currency == "USD"
        assert row.purchase_price > 0
        assert row.purchase_price_jpy == purchase_price_jpy(row.purchase_price, "USD")
        assert row.purchase_price_jpy == (row.purchase_price * rate)
        assert row.purchase_url.startswith("http")
        assert row.acquired_at or row.imported_at


def test_import_fashionphile_runs_existing_profit_and_sets_candidate_profit(tmp_path: Path) -> None:
    html = MUP_HTML.read_text(encoding="utf-8")
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "mup-profit.db")
    )
    listings = parse_fashionphile_html(html)[:5]
    yahoo_map = _yahoo_map_for_titles(
        [(item.title, item.brand, item.category) for item in listings]
    )
    result = import_fashionphile_keyword(
        service,
        "Chanel wallet",
        limit=5,
        html=html,
        acquirer=FashionphileAcquirer(purchase_limit=5),
        run_profit=True,
        html_by_query=yahoo_map,
    )
    assert result.batch_id
    assert result.profit_checked is True
    assert result.first_candidate_id

    _batch, rows = service.get_batch(result.batch_id)
    checked = [row for row in rows if row.last_profit_checked_at]
    assert checked
    assert any(row.last_gross_profit is not None for row in checked)


def test_fashionphile_live_form_imports_and_detail_shows_listing_meta(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(create_app(database_path=tmp_path / "mup-web.db"))

    from marketplace.acquisition_workspace import live_fashionphile_intake as intake_mod

    original = intake_mod.import_fashionphile_keyword

    def _import_with_fixture(service, keyword, *, limit=20, html=None, acquirer=None, run_profit=True, html_by_query=None):
        fixture_html = html or MUP_HTML.read_text(encoding="utf-8")
        listings = parse_fashionphile_html(fixture_html)[: max(1, int(limit))]
        yahoo_map = html_by_query or _yahoo_map_for_titles(
            [(item.title, item.brand, item.category) for item in listings]
        )
        return original(
            service,
            keyword,
            limit=limit,
            html=fixture_html,
            acquirer=acquirer or FashionphileAcquirer(purchase_limit=limit),
            run_profit=run_profit,
            html_by_query=yahoo_map,
        )

    monkeypatch.setattr(intake_mod, "import_fashionphile_keyword", _import_with_fixture)

    redirect = client.post(
        "/acquisition-workspace/import/fashionphile-live",
        data={"keyword": "Chanel wallet", "limit": "5"},
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    location = redirect.headers["location"]
    assert "/acquisition-workspace?" in location
    assert "intake_ok=1" in location
    assert "batch_id=" in location
    assert "/acquisition-workspace/candidate/" not in location

    workspace = client.get(location)
    assert workspace.status_code == 200
    assert "デモ表示中" not in workspace.text
    assert "Imported" in workspace.text
    assert "Fashionphile" in workspace.text
    assert "利益分析" in workspace.text
    assert "data-budget-filter" in workspace.text
    assert "data-brand-filter" in workspace.text

    marker = "/acquisition-workspace/candidate/"
    assert marker in workspace.text
    start = workspace.text.index(marker)
    end = workspace.text.index('"', start)
    detail_path = workspace.text[start:end].replace("&amp;", "&")
    detail = client.get(detail_path)
    assert detail.status_code == 200
    assert "デモ表示中" not in detail.text
    assert "Marketplace" in detail.text
    assert "Fashionphile" in detail.text
    assert "Currency" in detail.text
    assert "USD" in detail.text
    assert "Original price" in detail.text
    assert "Converted JPY" in detail.text
    assert "¥" in detail.text
    assert "Listing URL" in detail.text
    assert "Retrieved" in detail.text
    assert "商品ページを開く" in detail.text
    assert "fashionphile.com" in detail.text
    assert "純利益" in detail.text or "利益" in detail.text


def test_fashionphile_live_form_accepts_saved_html_upload(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(create_app(database_path=tmp_path / "mup-html.db"))

    from marketplace.acquisition_workspace import live_fashionphile_intake as intake_mod

    original = intake_mod.import_fashionphile_keyword

    def _import_with_yahoo(service, keyword, *, limit=20, html=None, acquirer=None, run_profit=True, html_by_query=None):
        fixture_html = html or MUP_HTML.read_text(encoding="utf-8")
        listings = parse_fashionphile_html(fixture_html)[: max(1, int(limit))]
        yahoo_map = html_by_query or _yahoo_map_for_titles(
            [(item.title, item.brand, item.category) for item in listings]
        )
        return original(
            service,
            keyword,
            limit=min(int(limit), 5),
            html=fixture_html,
            acquirer=acquirer or FashionphileAcquirer(purchase_limit=5),
            run_profit=run_profit,
            html_by_query=yahoo_map,
        )

    monkeypatch.setattr(intake_mod, "import_fashionphile_keyword", _import_with_yahoo)

    with MUP_HTML.open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/fashionphile-live",
            data={"keyword": "Chanel wallet", "limit": "5"},
            files={"html_file": ("fashionphile_mup_20.html", handle, "text/html")},
            follow_redirects=False,
        )
    assert redirect.status_code == 303
    location = redirect.headers["location"]
    assert "/acquisition-workspace?" in location
    assert "intake_ok=1" in location
    workspace = client.get(location)
    assert workspace.status_code == 200
    assert "デモ表示中" not in workspace.text
    assert "Fashionphile" in workspace.text


def test_workspace_shows_fashionphile_search_form(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "mup-form.db"))
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "Fashionphile検索" in page.text
    assert 'action="/acquisition-workspace/import/fashionphile-live"' in page.text
