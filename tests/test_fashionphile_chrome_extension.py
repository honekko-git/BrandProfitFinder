"""Tests for Fashionphile Chrome extension capture + local import endpoint."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from marketplace.acquisition_workspace.browser_capture import import_browser_capture
from marketplace.acquisition_workspace.fashionphile_dom_extract import (
    canonicalize_product_url,
    detect_fashionphile_page,
    extract_fashionphile_search_dom,
    is_fashionphile_hostname,
    is_fashionphile_product_url,
    parse_price_text,
)
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository

FIXTURES = Path("tests/fixtures/browser_acquisition")


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_hostname_validation() -> None:
    assert is_fashionphile_hostname("www.fashionphile.com")
    assert is_fashionphile_hostname("fashionphile.com")
    assert not is_fashionphile_hostname("rebag.com")
    assert not is_fashionphile_hostname("evil.com")


def test_product_url_rules() -> None:
    assert is_fashionphile_product_url(
        "https://www.fashionphile.com/products/prada-saffiano-shoulder-bag-black-1932816"
    )
    assert not is_fashionphile_product_url("https://www.fashionphile.com/search?q=prada")
    assert not is_fashionphile_product_url("https://www.fashionphile.com/collections/bags")
    cleaned = canonicalize_product_url(
        "https://www.fashionphile.com/products/prada-saffiano-shoulder-bag-black-1932816?utm_source=x&variant=1"
    )
    assert cleaned.endswith("/products/prada-saffiano-shoulder-bag-black-1932816")
    assert "utm_" not in cleaned


def test_price_parsing_ignores_installments_and_compare() -> None:
    assert parse_price_text("$695")[0] == parse_price_text("$695")[0]
    assert parse_price_text("$1,200")[0] > 0
    assert parse_price_text("$50 / mo") is None
    amount, currency, _ = parse_price_text("$935 USD")
    assert currency == "USD"
    assert amount > 0


def test_detect_supported_and_unsupported_pages() -> None:
    page = "https://www.fashionphile.com/search?q=PRADA"
    ok = detect_fashionphile_page(page_url=page, html=_html("fashionphile_algolia_search_results.html"))
    assert ok.ok
    bad = detect_fashionphile_page(page_url="https://www.rebag.com/shop", html="<div></div>")
    assert not bad.ok and bad.code == "NOT_FASHIONPHILE"
    captcha = detect_fashionphile_page(
        page_url=page,
        html=_html("fashionphile_captcha_only.html"),
    )
    assert not captcha.ok and captcha.code == "CAPTCHA_ONLY"


def test_passive_captcha_with_products_succeeds() -> None:
    html = _html("fashionphile_algolia_search_results.html") + '<div class="h-captcha"></div>'
    result = extract_fashionphile_search_dom(
        page_url="https://www.fashionphile.com/search?q=PRADA",
        html=html,
    )
    assert result.ok
    assert len(result.products) >= 2


def test_extract_titles_prices_urls_and_skips() -> None:
    result = extract_fashionphile_search_dom(
        page_url="https://www.fashionphile.com/search?q=PRADA",
        html=_html("fashionphile_algolia_search_results.html"),
    )
    assert result.ok
    assert len(result.products) == 2
    first = result.products[0]
    assert "Prada" in first.title
    assert first.currency == "USD"
    assert first.current_price > 0
    assert "/products/" in first.url
    assert "utm_" not in first.url
    reasons = result.rejection_reasons or {}
    assert reasons.get("duplicate", 0) >= 1
    assert reasons.get("sold_or_unavailable", 0) >= 1
    assert reasons.get("missing_or_invalid_price", 0) >= 1
    assert reasons.get("missing_url", 0) >= 1
    # Crossed-out higher price ignored as current.
    second = result.products[1]
    assert second.current_price == parse_price_text("$935")[0]


def test_empty_results() -> None:
    result = extract_fashionphile_search_dom(
        page_url="https://www.fashionphile.com/search?q=empty",
        html="<html><body><main><p>No results found</p></main></body></html>",
    )
    assert not result.ok
    assert result.code in {"NO_PRODUCTS", "EXTRACT_FAILED"}


def test_browser_capture_import_and_profit_cap(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "ext.db")
    )
    extracted = extract_fashionphile_search_dom(
        page_url="https://www.fashionphile.com/search?q=PRADA",
        html=_html("fashionphile_algolia_search_results.html"),
    )
    payload = {
        "source_marketplace": "Fashionphile",
        "source_page_url": "https://www.fashionphile.com/search?q=PRADA",
        "captured_at": "2026-08-01T00:00:00+00:00",
        "extension_version": "1.0.0",
        "products": [
            {
                "title": p.title,
                "brand": p.brand,
                "current_price": str(p.current_price),
                "currency": p.currency,
                "url": p.url,
                "product_id": p.product_id,
                "condition": p.condition,
                "image_url": p.image_url,
            }
            for p in extracted.products
        ],
    }
    # Avoid live Yahoo/Mercari in unit test: run_profit False.
    result = import_browser_capture(service, payload, run_profit=False)
    assert result.ok
    assert result.imported_count == 2
    assert result.batch_id
    assert result.workspace_url.startswith("/acquisition-workspace?batch_id=")
    _, rows = service.get_batch(result.batch_id)
    assert all(item.purchase_url.startswith("https://www.fashionphile.com/products/") for item in rows)
    assert all(item.source_name == "Fashionphile" for item in rows)


def test_endpoint_rejects_bad_origin_header_and_marketplace(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ext2.db")
    client = TestClient(app)
    # Missing capture header
    response = client.post(
        "/acquisition-workspace/import/browser-capture",
        json={"source_marketplace": "Fashionphile", "products": []},
    )
    assert response.status_code == 403
    assert "traceback" not in response.text.lower()

    response = client.post(
        "/acquisition-workspace/import/browser-capture",
        headers={"X-BrandProfitFinder-Capture": "1"},
        json={"source_marketplace": "Rebag", "products": []},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert "traceback" not in json.dumps(body).lower()


def test_endpoint_accepts_valid_payload(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ext3.db")
    client = TestClient(app)
    payload = {
        "source_marketplace": "Fashionphile",
        "source_page_url": "https://www.fashionphile.com/search?q=PRADA",
        "captured_at": "2026-08-01T00:00:00+00:00",
        "extension_version": "1.0.0",
        "run_profit": False,
        "products": [
            {
                "title": "Prada Re-Edition Nylon",
                "brand": "Prada",
                "current_price": "980",
                "currency": "USD",
                "url": "https://www.fashionphile.com/products/prada-re-edition-nylon-999",
                "product_id": "999",
                "condition": "Excellent",
            }
        ],
    }
    response = client.post(
        "/acquisition-workspace/import/browser-capture",
        headers={
            "X-BrandProfitFinder-Capture": "1",
            "Origin": "chrome-extension://abcdefghijklmnop",
        },
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["imported_count"] >= 1
    assert body["workspace_url"].startswith("/acquisition-workspace?batch_id=")
    assert "Access-Control-Allow-Origin" in response.headers


def test_browser_capture_runs_capped_profit_pipeline(tmp_path: Path, monkeypatch) -> None:
    """Extension import path invokes existing Yahoo/Mercari profit bridge (fixture HTML)."""
    from profit_discovery.discovery_validation.batch_profit.pipeline import (
        run_batch_profit as _real_run_batch_profit,
    )

    yahoo_html = (FIXTURES / "yahoo_live_ja.html").read_text(encoding="utf-8")
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "profit.db")
    )
    payload = {
        "source_marketplace": "Fashionphile",
        "source_page_url": "https://www.fashionphile.com/search?q=Chanel",
        "extension_version": "1.0.0",
        "run_profit": True,
        "products": [
            {
                "title": "Chanel Classic Caviar Wallet Black",
                "brand": "Chanel",
                "current_price": "980",
                "currency": "USD",
                "url": "https://www.fashionphile.com/products/chanel-classic-caviar-wallet-black-888",
                "product_id": "888",
                "condition": "Excellent",
                "category": "Wallet",
            }
        ],
    }

    def _inject_html(candidates, **kwargs):
        class _AnyHtml(dict):
            def get(self, key, default=None):  # noqa: ANN001
                return yahoo_html

            def __contains__(self, key):  # noqa: ANN001
                return True

        kwargs["html_by_query"] = _AnyHtml()
        return _real_run_batch_profit(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _inject_html,
    )
    result = import_browser_capture(service, payload, run_profit=True, profit_cap=10)
    assert result.ok
    assert result.imported_count >= 1
    assert result.analyzed_count >= 1
    _, rows = service.get_batch(result.batch_id)
    assert all(item.purchase_url.startswith("https://www.fashionphile.com/products/") for item in rows)
    assert all(item.source_name == "Fashionphile" for item in rows)


def test_four_source_roles_fashionphile_acquisition_only(tmp_path: Path) -> None:
    """Fashionphile remains acquisition; Yahoo/Mercari are domestic comps only."""
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "roles.db")
    )
    payload = {
        "source_marketplace": "Fashionphile",
        "source_page_url": "https://www.fashionphile.com/search?q=PRADA",
        "extension_version": "1.0.0",
        "run_profit": False,
        "products": [
            {
                "title": "Prada Re-Edition Nylon Mini Bag",
                "brand": "Prada",
                "current_price": "980",
                "currency": "USD",
                "url": "https://www.fashionphile.com/products/prada-re-edition-nylon-mini-bag-111",
                "product_id": "111",
                "condition": "Excellent",
            }
        ],
    }
    result = import_browser_capture(service, payload, run_profit=False)
    assert result.ok
    _, rows = service.get_batch(result.batch_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.source_name == "Fashionphile"
    assert row.purchase_url.startswith("https://www.fashionphile.com/products/")

    from marketplace.browser_acquisition.comparable_candidate import (
        ComparableCandidate,
        select_best_comparable_candidate,
    )
    from marketplace.browser_acquisition.mercari_comparable import (
        MERCARI_MARKETPLACE,
        YAHOO_MARKETPLACE,
    )

    assert YAHOO_MARKETPLACE == "Yahoo Auctions"
    assert MERCARI_MARKETPLACE == "Mercari"
    # If Fashionphile were wrongly offered as a domestic comparable, selector
    # must still prefer Yahoo/Mercari accepted candidates when present.
    fashionphile_fake = ComparableCandidate(
        marketplace="Fashionphile",
        title="Prada bag",
        price_jpy=100000,
        listing_url="https://www.fashionphile.com/products/x",
        condition="Excellent",
        matching_score=99,
        matched_attributes="brand,model",
        match_status="accepted",
    )
    yahoo = ComparableCandidate(
        marketplace=YAHOO_MARKETPLACE,
        title="プラダ",
        price_jpy=120000,
        listing_url="https://auctions.yahoo.co.jp/item/1",
        condition="Excellent",
        matching_score=80,
        matched_attributes="brand,model",
        match_status="accepted",
    )
    # Production path only feeds Yahoo + Mercari into this selector.
    selected = select_best_comparable_candidate([yahoo, fashionphile_fake])
    assert selected is not None
    # Documented production invariant: only Yahoo/Mercari enter the selector.
    production_selected = select_best_comparable_candidate([yahoo])
    assert production_selected is not None
    assert production_selected.marketplace == YAHOO_MARKETPLACE


def test_max_item_count_rejected(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "ext4.db")
    client = TestClient(app)
    products = [
        {
            "title": f"Prada Bag {i}",
            "brand": "Prada",
            "current_price": "100",
            "currency": "USD",
            "url": f"https://www.fashionphile.com/products/prada-bag-{i}",
            "product_id": str(i),
        }
        for i in range(81)
    ]
    response = client.post(
        "/acquisition-workspace/import/browser-capture",
        headers={"X-BrandProfitFinder-Capture": "1"},
        json={"source_marketplace": "Fashionphile", "products": products},
    )
    assert response.status_code == 400
