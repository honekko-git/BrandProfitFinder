"""Focused tests for Fashionphile capture continuation (120 → 80 → 40 → done)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from marketplace.acquisition_workspace.browser_capture import (
    MAX_CAPTURE_PRODUCTS,
    collect_known_fashionphile_urls,
    import_browser_capture,
    resolve_known_urls,
)
from marketplace.acquisition_workspace.fashionphile_dom_extract import canonicalize_product_url
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.connectors.models import MarketListing


def _product(i: int, *, price: str = "100", title: str | None = None) -> dict:
    return {
        "title": title or f"Prada Bag {i}",
        "brand": "Prada",
        "current_price": price,
        "currency": "USD",
        "url": f"https://www.fashionphile.com/products/prada-bag-{i}",
        "product_id": str(i),
        "condition": "Excellent",
    }


def _payload(products: list[dict], *, detected: int | None = None, visible: list[str] | None = None) -> dict:
    urls = [p["url"] for p in products]
    return {
        "source_marketplace": "Fashionphile",
        "source_page_url": "https://www.fashionphile.com/search?q=PRADA",
        "extension_version": "1.0.0",
        "run_profit": False,
        "detected_count": detected if detected is not None else len(products),
        "visible_urls": visible if visible is not None else urls,
        "products": products,
    }


def test_first_capture_120_imports_first_80(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "c1.db")
    )
    all_products = [_product(i) for i in range(1, 121)]
    visible = [p["url"] for p in all_products]
    first = all_products[:MAX_CAPTURE_PRODUCTS]
    result = import_browser_capture(
        service,
        _payload(first, detected=120, visible=visible),
        run_profit=False,
    )
    assert result.ok
    assert result.imported_this_run == 80
    assert result.remaining_count == 40
    assert result.already_imported_count == 0
    assert "80件を取り込みました" in result.user_message
    assert "残り40件" in result.user_message
    _, rows = service.get_batch(result.batch_id)
    assert len(rows) == 80


def test_second_capture_imports_only_remaining_40(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "c2.db")
    )
    all_products = [_product(i) for i in range(1, 121)]
    visible = [p["url"] for p in all_products]
    first = import_browser_capture(
        service,
        _payload(all_products[:80], detected=120, visible=visible),
        run_profit=False,
    )
    assert first.imported_this_run == 80

    known = resolve_known_urls(
        service,
        {"source_marketplace": "Fashionphile", "urls": visible},
    )
    assert known.ok
    assert known.known_count == 80
    known_set = set(known.known_urls)
    remaining = [p for p in all_products if canonicalize_product_url(p["url"]) not in known_set]
    assert len(remaining) == 40

    second = import_browser_capture(
        service,
        _payload(remaining, detected=120, visible=visible),
        run_profit=False,
    )
    assert second.ok
    assert second.imported_this_run == 40
    assert second.remaining_count == 0
    assert second.already_imported_count == 80
    assert "追加で40件" in second.user_message
    assert second.batch_id == first.batch_id
    _, rows = service.get_batch(second.batch_id)
    assert len(rows) == 120
    assert len({canonicalize_product_url(r.purchase_url) for r in rows}) == 120


def test_third_capture_reports_all_already_imported(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "c3.db")
    )
    all_products = [_product(i) for i in range(1, 121)]
    visible = [p["url"] for p in all_products]
    import_browser_capture(service, _payload(all_products[:80], detected=120, visible=visible), run_profit=False)
    import_browser_capture(service, _payload(all_products[80:], detected=120, visible=visible), run_profit=False)

    third = import_browser_capture(
        service,
        _payload(all_products[:80], detected=120, visible=visible),
        run_profit=False,
    )
    assert third.ok
    assert third.imported_this_run == 0
    assert third.remaining_count == 0
    assert "すべて取り込み済み" in third.user_message
    _, rows = service.get_batch(third.batch_id)
    assert len(rows) == 120


def test_canonical_and_tracking_parameter_duplicate_detection(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "dup.db")
    )
    base = _product(1)
    import_browser_capture(service, _payload([base]), run_profit=False)
    tracked = dict(base)
    tracked["url"] = base["url"] + "?utm_source=x&fbclid=1"
    tracked["title"] = "Changed Title Same Listing"
    tracked["current_price"] = "999"
    result = import_browser_capture(service, _payload([tracked]), run_profit=False)
    assert result.ok
    assert result.imported_this_run == 0
    known = collect_known_fashionphile_urls(service)
    assert canonicalize_product_url(base["url"]) in known
    assert len(known) == 1


def test_same_title_different_urls_remain_distinct(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "dist.db")
    )
    a = _product(1, title="Prada Re-Edition Nylon")
    b = _product(2, title="Prada Re-Edition Nylon")
    first = import_browser_capture(service, _payload([a]), run_profit=False)
    second = import_browser_capture(service, _payload([b]), run_profit=False)
    assert first.imported_this_run == 1
    assert second.imported_this_run == 1
    known = collect_known_fashionphile_urls(service)
    assert len(known) == 2


def test_same_url_changed_price_remains_one_candidate(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "price.db")
    )
    first = import_browser_capture(service, _payload([_product(7, price="100")]), run_profit=False)
    second = import_browser_capture(service, _payload([_product(7, price="250")]), run_profit=False)
    assert first.imported_this_run == 1
    assert second.imported_this_run == 0
    _, rows = service.get_batch(first.batch_id)
    assert len(rows) == 1
    assert rows[0].purchase_price == Decimal("100")


def test_known_urls_endpoint_and_backend_confirmation(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "api.db")
    client = TestClient(app)
    headers = {
        "X-BrandProfitFinder-Capture": "1",
        "Origin": "chrome-extension://testextensionid",
    }
    products = [_product(i) for i in range(1, 5)]
    visible = [p["url"] for p in products]

    known_before = client.post(
        "/acquisition-workspace/import/browser-capture/known-urls",
        headers=headers,
        json={"source_marketplace": "Fashionphile", "urls": visible},
    )
    assert known_before.status_code == 200
    assert known_before.json()["known_count"] == 0

    capture = client.post(
        "/acquisition-workspace/import/browser-capture",
        headers=headers,
        json=_payload(products[:2], detected=4, visible=visible),
    )
    assert capture.status_code == 200
    body = capture.json()
    assert body["ok"] is True
    assert body["imported_this_run"] == 2
    assert body["remaining_count"] == 2
    # Backend confirmation required: only imported_urls are marked.
    assert len(body["imported_urls"]) == 2

    known_after = client.post(
        "/acquisition-workspace/import/browser-capture/known-urls",
        headers=headers,
        json={"source_marketplace": "Fashionphile", "urls": visible},
    )
    assert known_after.json()["known_count"] == 2


def test_relative_and_absolute_url_forms_resolve_same(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "rel.db")
    )
    abs_url = "https://www.fashionphile.com/products/prada-bag-42"
    import_browser_capture(
        service,
        _payload(
            [
                {
                    "title": "Prada Bag 42",
                    "brand": "Prada",
                    "current_price": "100",
                    "currency": "USD",
                    "url": abs_url,
                    "product_id": "42",
                }
            ]
        ),
        run_profit=False,
    )
    relative = import_browser_capture(
        service,
        _payload(
            [
                {
                    "title": "Prada Bag 42 Again",
                    "brand": "Prada",
                    "current_price": "120",
                    "currency": "USD",
                    "url": "/products/prada-bag-42?utm_source=x",
                    "product_id": "42",
                }
            ]
        ),
        run_profit=False,
    )
    assert relative.imported_this_run == 0


def test_other_marketplace_records_unaffected(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "mix.db")
    )
    rebag = MarketListing(
        id="rebag-1",
        market_name="Rebag",
        title="Rebag Prada",
        brand="Prada",
        category="Bag",
        condition="Excellent",
        price=Decimal("500"),
        currency="USD",
        url="https://www.rebag.com/product/prada-1",
        source_type="fixture",
        created_at=datetime.now(tz=UTC),
    )
    batch = service.import_existing_listings([rebag], name="Rebag Manual")
    import_browser_capture(service, _payload([_product(9)]), run_profit=False)
    _, rebag_rows = service.get_batch(batch.workspace_batch_id)
    assert len(rebag_rows) == 1
    assert rebag_rows[0].source_name == "Rebag"
    known = collect_known_fashionphile_urls(service)
    assert all("fashionphile.com" in url for url in known)
    assert len(known) == 1


def test_cors_known_urls_preflight(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "cors.db")
    client = TestClient(app)
    response = client.options(
        "/acquisition-workspace/import/browser-capture/known-urls",
        headers={
            "Origin": "chrome-extension://abc",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in {200, 204}
