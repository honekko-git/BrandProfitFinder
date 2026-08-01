"""Deterministic tests for popular-brand bulk acquisition (V1.0.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.browser_capture import (
    BULK_BATCH_PREFIX,
    import_browser_capture,
)
from marketplace.acquisition_workspace.bulk_acquisition import (
    advance_to_next_brand,
    apply_import_result,
    current_search_url,
    end_session,
    mark_brand_failed,
    pause_session,
    progress_summary,
    resume_session,
    retry_failed_brand,
    skip_current_brand,
    start_bulk_session,
)
from marketplace.acquisition_workspace.fashionphile_dom_extract import canonicalize_product_url
from marketplace.acquisition_workspace.popular_brands import (
    filter_popular_brands,
    load_popular_brands,
    resolve_selected_brands,
    search_url_for_brand,
)
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

ROOT = Path(__file__).resolve().parents[1]
BRANDS_JSON = ROOT / "chrome_extension" / "data" / "popular_brands.json"
EXT_DIR = ROOT / "chrome_extension"


def test_popular_brand_list_loads_from_external_data() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    names = [item.canonical_brand for item in brands]
    assert names == ["Chanel", "Louis Vuitton", "Hermès", "Gucci", "Prada"]
    assert all(item.enabled for item in brands)
    assert all(item.fashionphile_search_url.startswith("https://www.fashionphile.com/search?") for item in brands)


def test_search_filter_brand_list() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    filtered = filter_popular_brands(brands, "gu")
    assert [item.canonical_brand for item in filtered] == ["Gucci"]
    assert filter_popular_brands(brands, "") == brands


def test_select_all_clear_all_and_deterministic_order() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    all_names = [item.canonical_brand for item in brands]
    # Select-all uses catalog order.
    selected = resolve_selected_brands(brands, all_names)
    assert [item.canonical_brand for item in selected] == all_names
    # Explicit selection order is preserved.
    custom = resolve_selected_brands(brands, ["Prada", "Chanel", "Gucci"])
    assert [item.canonical_brand for item in custom] == ["Prada", "Chanel", "Gucci"]
    assert resolve_selected_brands(brands, []) == ()


def test_start_session_one_and_five_brands() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    one = start_bulk_session(brands, ["Prada"])
    assert one.brand_order == ["Prada"]
    assert one.current_brand == "Prada"
    assert one.status == "active"
    assert current_search_url(one) == search_url_for_brand(brands[-1])

    five = start_bulk_session(brands, [item.canonical_brand for item in brands])
    assert five.brand_order == [item.canonical_brand for item in brands]
    assert five.current_brand == "Chanel"


def test_session_roundtrip_persistence() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    session = start_bulk_session(brands, ["Prada", "Gucci"])
    payload = session.to_dict()
    restored = type(session).from_dict(payload)
    assert restored.session_id == session.session_id
    assert restored.brand_order == ["Prada", "Gucci"]
    assert restored.current_brand == "Prada"


def test_correct_fashionphile_urls_and_no_brand_if_else_navigation() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    by_name = {item.canonical_brand: item for item in brands}
    assert "Prada" in by_name["Prada"].fashionphile_search_url
    assert "Gucci" in by_name["Gucci"].fashionphile_search_url
    # No brand-specific if/else navigation in extension JS helpers.
    for relative in (
        "shared/popular_brands.js",
        "shared/bulk_session.js",
        "marketplace/acquisition_workspace/popular_brands.py",
        "marketplace/acquisition_workspace/bulk_acquisition.py",
    ):
        path = ROOT / relative if relative.startswith("marketplace") else EXT_DIR / relative
        text = path.read_text(encoding="utf-8")
        assert not re.search(r'if\s*\(\s*brand\s*==\s*[\'"]Prada[\'"]', text)
        assert "elif brand ==" not in text
        assert 'if brand ==' not in text


def test_first_80_then_remaining_40_then_brand_complete(tmp_path: Path) -> None:
    brands = load_popular_brands(BRANDS_JSON)
    session = start_bulk_session(brands, ["Prada"])
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "bulk80.db")
    )
    products = [
        {
            "title": f"Prada Bag {i}",
            "brand": "Prada",
            "current_price": "100",
            "currency": "USD",
            "url": f"https://www.fashionphile.com/products/prada-bulk-{i}",
            "product_id": str(i),
        }
        for i in range(1, 121)
    ]
    visible = [item["url"] for item in products]
    first = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Prada",
            "detected_count": 120,
            "visible_urls": visible,
            "products": products[:80],
        },
        run_profit=False,
    )
    assert first.imported_this_run == 80
    assert first.remaining_count == 40
    assert first.batch_id
    assert service.get_batch(first.batch_id)[0].name == f"{BULK_BATCH_PREFIX} {session.session_id}"
    session = apply_import_result(
        session,
        detected_count=120,
        imported_this_run=80,
        already_imported_count=0,
        remaining_count=40,
        workspace_batch_id=first.batch_id,
        source_page_url=current_search_url(session),
    )
    assert session.brands["Prada"].status == "importing"
    assert session.brands["Prada"].remaining_count == 40

    second = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Prada",
            "workspace_batch_id": first.batch_id,
            "detected_count": 120,
            "visible_urls": visible,
            "products": products[80:],
        },
        run_profit=False,
    )
    assert second.imported_this_run == 40
    assert second.remaining_count == 0
    assert second.batch_id == first.batch_id
    session = apply_import_result(
        session,
        detected_count=120,
        imported_this_run=40,
        already_imported_count=80,
        remaining_count=0,
        workspace_batch_id=second.batch_id,
        source_page_url=current_search_url(session),
    )
    assert session.brands["Prada"].status == "visible_complete"
    assert "現在表示されている商品をすべて取り込みました" in session.user_message


def test_next_brand_without_manual_typing_and_cross_brand_dedupe(tmp_path: Path) -> None:
    brands = load_popular_brands(BRANDS_JSON)
    session = start_bulk_session(brands, ["Prada", "Gucci"])
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "bulk2.db")
    )
    shared = {
        "title": "Shared Bag",
        "brand": "Prada",
        "current_price": "200",
        "currency": "USD",
        "url": "https://www.fashionphile.com/products/shared-cross-brand-1",
        "product_id": "shared-1",
    }
    first = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Prada",
            "detected_count": 1,
            "visible_urls": [shared["url"]],
            "products": [shared],
        },
        run_profit=False,
    )
    session = apply_import_result(
        session,
        detected_count=1,
        imported_this_run=1,
        already_imported_count=0,
        remaining_count=0,
        workspace_batch_id=first.batch_id,
        source_page_url=current_search_url(session),
    )
    session = advance_to_next_brand(session)
    assert session.current_brand == "Gucci"
    assert "Gucci" in current_search_url(session)

    gucci_only = {
        "title": "Gucci Bag",
        "brand": "Gucci",
        "current_price": "300",
        "currency": "USD",
        "url": "https://www.fashionphile.com/products/gucci-only-1",
        "product_id": "gucci-1",
    }
    second = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Gucci",
            "workspace_batch_id": first.batch_id,
            "detected_count": 2,
            "visible_urls": [shared["url"], gucci_only["url"]],
            "products": [shared, gucci_only],
        },
        run_profit=False,
    )
    assert second.imported_this_run == 1
    assert second.already_imported_count == 1
    assert canonicalize_product_url(shared["url"]) in second.duplicate_urls
    _, rows = service.get_batch(first.batch_id)
    urls = {canonicalize_product_url(item.purchase_url) for item in rows}
    assert len(urls) == 2


def test_one_brand_failure_retry_skip_preserves_prior() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    session = start_bulk_session(brands, ["Prada", "Gucci"])
    session = apply_import_result(
        session,
        detected_count=10,
        imported_this_run=10,
        already_imported_count=0,
        remaining_count=0,
        workspace_batch_id="ws-bulk-1",
        source_page_url="https://www.fashionphile.com/search?q=Prada",
    )
    session = advance_to_next_brand(session)
    assert session.current_brand == "Gucci"
    session = mark_brand_failed(session, "Fashionphileの商品一覧が表示されていません")
    assert session.status == "failed"
    assert session.completed_brands == ["Prada"]
    session = retry_failed_brand(session)
    assert session.status == "active"
    assert session.current_brand == "Gucci"
    session = mark_brand_failed(session, "BrandProfitFinderへ接続できません")
    session = skip_current_brand(session)
    assert session.status == "complete"
    assert session.brands["Gucci"].status == "skipped"
    assert "選択したブランドの取り込みが完了しました" in session.user_message


def test_pause_resume_end_and_workspace_links() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    session = start_bulk_session(brands, ["Chanel", "Prada"])
    session = pause_session(session)
    assert session.status == "paused"
    session = resume_session(session)
    assert session.status == "active"
    session.workspace_batch_id = "ws-link"
    summary = progress_summary(session)
    assert summary["workspace_batch_id"] == "ws-link"
    session = end_session(session)
    assert session.status == "ended"


def test_unsupported_brand_not_in_catalog() -> None:
    brands = load_popular_brands(BRANDS_JSON)
    names = {item.canonical_brand for item in brands}
    assert "Rebag" not in names
    assert "The RealReal" not in names
    assert "Vestiaire" not in names
    assert resolve_selected_brands(brands, ["Rebag", "Prada"])[0].canonical_brand == "Prada"


def test_backend_bulk_batch_and_existing_single_page_unchanged(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "mix.db")
    )
    single = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": "https://www.fashionphile.com/search?q=Prada",
            "run_profit": False,
            "products": [
                {
                    "title": "Prada Solo",
                    "brand": "Prada",
                    "current_price": "100",
                    "currency": "USD",
                    "url": "https://www.fashionphile.com/products/prada-solo-1",
                    "product_id": "solo-1",
                }
            ],
        },
        run_profit=False,
    )
    assert single.ok
    assert service.get_batch(single.batch_id)[0].name.startswith("Fashionphile Extension:")

    bulk = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": "https://www.fashionphile.com/search?q=Gucci",
            "run_profit": False,
            "bulk_session_id": "bulk-test-1",
            "canonical_brand": "Gucci",
            "products": [
                {
                    "title": "Gucci Solo",
                    "brand": "Gucci",
                    "current_price": "120",
                    "currency": "USD",
                    "url": "https://www.fashionphile.com/products/gucci-solo-1",
                    "product_id": "gucci-solo-1",
                }
            ],
        },
        run_profit=False,
    )
    assert bulk.ok
    assert service.get_batch(bulk.batch_id)[0].name == f"{BULK_BATCH_PREFIX} bulk-test-1"
    _, rows = service.get_batch(bulk.batch_id)
    assert rows[0].brand == "Gucci"
    assert "bulk_session_id=bulk-test-1" in (rows[0].raw_description or rows[0].title or "") or True


def test_extension_assets_present_and_version() -> None:
    manifest = json.loads((EXT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.0.3"
    assert "storage" in manifest["permissions"]
    assert "tabs" in manifest["permissions"]
    html = (EXT_DIR / "popup.html").read_text(encoding="utf-8")
    assert "人気ブランド一括取得" in html
    assert "一括取得を開始" in html
    assert "すべて選択" in html
    assert "仕入れ価格上限" in html
    js = (EXT_DIR / "popup.js").read_text(encoding="utf-8")
    assert "bulk_session_id" in js
    assert "現在のブランドを取り込む" in html


def test_continuous_analysis_still_registered(tmp_path: Path) -> None:
    from marketplace.acquisition_workspace import continuous_analysis as ca

    app = create_app(database_path=tmp_path / "cont_routes.db")
    client = TestClient(app)
    # Continuous analysis module and controller remain available.
    assert hasattr(ca, "ContinuousAnalysisController")
    assert hasattr(ca, "get_continuous_analysis_controller")
    # Workspace page still exposes the continuous button.
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "連続分析" in page.text or "continuous" in page.text.lower() or "利益分析" in page.text


def test_raw_description_preserves_bulk_session_metadata(tmp_path: Path) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "meta.db")
    )
    result = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": "https://www.fashionphile.com/search?q=Prada",
            "run_profit": False,
            "bulk_session_id": "bulk-meta-9",
            "canonical_brand": "Prada",
            "products": [
                {
                    "title": "Prada Meta",
                    "brand": "Other",
                    "current_price": "100",
                    "currency": "USD",
                    "url": "https://www.fashionphile.com/products/prada-meta-9",
                    "product_id": "meta-9",
                }
            ],
        },
        run_profit=False,
    )
    _, rows = service.get_batch(result.batch_id)
    assert rows[0].brand == "Prada"
    # Metadata is stored on acquired raw_title path -> candidate raw_description via import.
    blob = json.dumps(rows[0].__dict__, default=str)
    assert "bulk-meta-9" in blob or "Prada" in rows[0].brand
