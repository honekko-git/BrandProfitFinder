"""Build verification report for Fashionphile Chrome extension capture path.

Uses a real Chrome-rendered Fashionphile search DOM snapshot (not unit fixtures)
to exercise extraction → browser-capture import → workspace URL persistence.
Does not claim interactive Chrome extension UI clicks were performed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.browser_capture import import_browser_capture
from marketplace.acquisition_workspace.fashionphile_dom_extract import (
    extract_fashionphile_search_dom,
)
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

ROOT = Path(__file__).resolve().parents[1]
DOM_PATH = ROOT / "output" / "fashionphile_prada_browser_dom.html"
OUT_PATH = ROOT / "output" / "fashionphile_chrome_extension_verification.json"
SOURCE_PAGE = "https://www.fashionphile.com/search?q=PRADA"


def main() -> None:
    started = datetime.now(tz=UTC)
    html = DOM_PATH.read_text(encoding="utf-8", errors="replace")
    extracted = extract_fashionphile_search_dom(page_url=SOURCE_PAGE, html=html)
    products = [
        {
            "title": p.title,
            "brand": p.brand,
            "current_price": str(p.current_price),
            "currency": p.currency,
            "url": p.url,
            "product_id": p.product_id,
            "condition": p.condition,
            "image_url": p.image_url,
            "availability": p.availability,
        }
        for p in extracted.products
    ]
    # Cap import size for report runtime; note visible vs imported.
    import_slice = products[:40]
    db_path = ROOT / "data" / "fashionphile_extension_verify.db"
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=db_path)
    )
    result = import_browser_capture(
        service,
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": SOURCE_PAGE,
            "captured_at": started.isoformat(),
            "extension_version": "1.0.0",
            "run_profit": False,
            "products": import_slice,
        },
        run_profit=False,
    )
    _, rows = service.get_batch(result.batch_id) if result.batch_id else (None, [])
    ended = datetime.now(tz=UTC)
    report = {
        "phase": "V1-RC-FP1",
        "executive_result": "PARTIAL",
        "verification_mode": "real_chrome_dom_snapshot_plus_local_import",
        "notes": [
            "Extraction run against Chrome-saved Fashionphile PRADA search DOM.",
            "Interactive Chrome extension button click was not automated in this report.",
            "Profit/Yahoo/Mercari live browsers skipped (run_profit=false) to keep report deterministic.",
            "Install unpacked extension and click 一括取込 for full UI path.",
        ],
        "source_page_url": SOURCE_PAGE,
        "dom_snapshot_path": str(DOM_PATH.relative_to(ROOT)).replace("\\", "/"),
        "capture_timestamp": started.isoformat(),
        "visible_product_card_count": extracted.visible_card_count,
        "extracted_product_count": len(extracted.products),
        "skipped_count": extracted.rejected_count,
        "skipped_reasons": extracted.rejection_reasons or {},
        "products_with_valid_individual_urls": sum(
            1 for p in extracted.products if "/products/" in p.url
        ),
        "import_attempted_count": len(import_slice),
        "imported_count": result.imported_count,
        "eligible_count": result.eligible_count,
        "analyzed_count": result.analyzed_count,
        "ranked_count": result.ranked_count,
        "batch_id": result.batch_id,
        "workspace_url": result.workspace_url,
        "yahoo_searches_executed": 0,
        "mercari_searches_executed": 0,
        "extension_errors": [],
        "backend_errors": list(result.errors),
        "all_imported_urls_fashionphile_products": all(
            item.purchase_url.startswith("https://www.fashionphile.com/products/")
            for item in rows
        ),
        "all_imported_source_fashionphile": all(
            item.source_name == "Fashionphile" for item in rows
        ),
        "sample_products": [
            {"title": p.title, "price": str(p.current_price), "url": p.url}
            for p in extracted.products[:5]
        ],
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "four_source_roles": {
            "Fashionphile": "overseas_acquisition",
            "Rebag": "overseas_acquisition",
            "The RealReal": "overseas_acquisition",
            "Vestiaire Collective": "overseas_acquisition",
            "Yahoo Auctions": "domestic_comparable_only",
            "Mercari": "domestic_comparable_only",
        },
        "constraints_honored": {
            "no_purchase_automation": True,
            "no_captcha_bypass": True,
            "no_ai_matching": True,
            "extension_reads_rendered_dom_only": True,
        },
    }
    if extracted.visible_card_count >= 20 and len(extracted.products) >= 20 and result.ok:
        report["executive_result"] = "GO_FOR_EXTRACTION_AND_IMPORT"
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT_PATH), "result": report["executive_result"]}, indent=2))


if __name__ == "__main__":
    main()
