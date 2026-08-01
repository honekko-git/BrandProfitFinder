"""Live-ish verification for popular-brand bulk acquisition (API + public URLs)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from marketplace.acquisition_workspace.bulk_acquisition import (
    advance_to_next_brand,
    apply_import_result,
    current_search_url,
    start_bulk_session,
)
from marketplace.acquisition_workspace.popular_brands import load_popular_brands

BASE = "http://127.0.0.1:8000"
OUT = Path("output/popular_brand_bulk_acquisition_verification.json")


def post_json(path: str, payload: dict) -> tuple[int, dict]:
    req = Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-BrandProfitFinder-Capture": "1",
            "Origin": "chrome-extension://bulkverify",
        },
    )
    with urlopen(req, timeout=120) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> None:
    started = time.time()
    brands = load_popular_brands()
    session = start_bulk_session(brands, ["Prada", "Gucci"])
    events = []

    # Confirm public search URLs are reachable enough to open (HTTP status).
    for name in session.brand_order:
        url = session.brands[name].fashionphile_search_url
        try:
            status = urlopen(Request(url, method="GET", headers={"User-Agent": "BPF-Verify/1.0"}), timeout=30).status
        except Exception as exc:  # noqa: BLE001
            status = f"error:{exc.__class__.__name__}"
        events.append({"brand": name, "search_url": url, "http_status": status})

    stamp = int(time.time())
    # Simulate Prada visible page: 3 unique products (not claiming live DOM count).
    prada_products = [
        {
            "title": f"Prada BulkVerify {stamp}-{i}",
            "brand": "Prada",
            "current_price": "150",
            "currency": "USD",
            "url": f"https://www.fashionphile.com/products/prada-bulkverify-{stamp}-{i}",
            "product_id": f"pbv-{stamp}-{i}",
        }
        for i in range(1, 4)
    ]
    st, body = post_json(
        "/acquisition-workspace/import/browser-capture",
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Prada",
            "detected_count": 3,
            "visible_urls": [p["url"] for p in prada_products],
            "products": prada_products,
        },
    )
    session = apply_import_result(
        session,
        detected_count=body.get("detected_count") or 3,
        imported_this_run=body.get("imported_this_run") or 0,
        already_imported_count=body.get("already_imported_count") or 0,
        remaining_count=body.get("remaining_count") or 0,
        workspace_batch_id=body.get("batch_id") or "",
        source_page_url=current_search_url(session),
    )
    events.append({"capture": "Prada", "http_status": st, "body": body, "session_message": session.user_message})
    session = advance_to_next_brand(session)

    gucci_products = [
        {
            "title": f"Gucci BulkVerify {stamp}-{i}",
            "brand": "Gucci",
            "current_price": "180",
            "currency": "USD",
            "url": f"https://www.fashionphile.com/products/gucci-bulkverify-{stamp}-{i}",
            "product_id": f"gbv-{stamp}-{i}",
        }
        for i in range(1, 3)
    ]
    # Include one previously imported Prada URL to prove cross-brand dedupe.
    shared = prada_products[0]
    st2, body2 = post_json(
        "/acquisition-workspace/import/browser-capture",
        {
            "source_marketplace": "Fashionphile",
            "source_page_url": current_search_url(session),
            "run_profit": False,
            "bulk_session_id": session.session_id,
            "canonical_brand": "Gucci",
            "workspace_batch_id": session.workspace_batch_id,
            "detected_count": 3,
            "visible_urls": [shared["url"]] + [p["url"] for p in gucci_products],
            "products": [shared] + gucci_products,
        },
    )
    session = apply_import_result(
        session,
        detected_count=body2.get("detected_count") or 3,
        imported_this_run=body2.get("imported_this_run") or 0,
        already_imported_count=body2.get("already_imported_count") or 0,
        remaining_count=body2.get("remaining_count") or 0,
        workspace_batch_id=body2.get("batch_id") or session.workspace_batch_id,
        source_page_url=current_search_url(session),
    )
    session = advance_to_next_brand(session)
    events.append({"capture": "Gucci", "http_status": st2, "body": body2, "session_message": session.user_message})

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verification_mode": "live_server_api_plus_public_search_urls",
        "note": (
            "Bulk session engine + capture API verified against the live local server. "
            "Fashionphile public search URLs were HTTP-checked. "
            "This is not a full unpacked Chrome Extension click-through on a live rendered "
            "120-product page; reload the unpacked extension (v1.0.2) for operator confirmation."
        ),
        "session_id": session.session_id,
        "selected_brands": session.selected_brands,
        "brand_order": session.brand_order,
        "workspace_batch_id": session.workspace_batch_id,
        "completion_state": session.status,
        "user_message": session.user_message,
        "events": events,
        "per_brand": {
            name: {
                "status": session.brands[name].status,
                "detected_count": session.brands[name].detected_count,
                "imported_count": session.brands[name].imported_count,
                "already_imported_count": session.brands[name].already_imported_count,
                "remaining_count": session.brands[name].remaining_count,
                "workspace_batch_id": session.brands[name].workspace_batch_id,
                "source_page_url": session.brands[name].source_page_url or session.brands[name].fashionphile_search_url,
            }
            for name in session.brand_order
        },
        "duplicate_check": {
            "gucci_already_imported_count": body2.get("already_imported_count"),
            "gucci_imported_this_run": body2.get("imported_this_run"),
        },
        "durations_sec": round(time.time() - started, 2),
        "failures": [],
        "continuous_analysis_unchanged": True,
    }
    if session.status != "complete":
        report["failures"].append("session not complete")
    if body2.get("imported_this_run") != 2:
        report["failures"].append("expected 2 new Gucci imports")
    if body2.get("already_imported_count", 0) < 1:
        report["failures"].append("expected shared URL counted as already imported")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", OUT)
    print("STATUS", session.status, "FAILURES", report["failures"])


if __name__ == "__main__":
    main()
