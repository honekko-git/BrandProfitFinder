"""Live local verification for capture continuation + profit progression."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
BATCH = "ws-20260731183118-b673ef"
OUT = Path("output/fashionphile_capture_continuation_verification.json")


def fetch(method: str, path: str, data=None, headers=None):
    body = None
    hdrs = dict(headers or {})
    if data is not None:
        if isinstance(data, dict) and hdrs.get("Content-Type") != "application/json":
            # form unless JSON header forced
            if "application/json" in str(hdrs.get("Content-Type", "")):
                body = json.dumps(data).encode()
            else:
                body = urlencode(data).encode()
                hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = json.dumps(data).encode()
            hdrs.setdefault("Content-Type", "application/json")
    req = Request(BASE + path, data=body, method=method, headers=hdrs)
    try:
        with urlopen(req, timeout=900) as response:
            return (
                response.status,
                response.geturl(),
                response.read().decode("utf-8", "replace"),
            )
    except HTTPError as exc:
        return (
            exc.code,
            getattr(exc, "url", path),
            exc.read().decode("utf-8", "replace"),
        )


def parse_workspace(html: str) -> dict:
    notices = re.findall(r'class="[^"]*notice[^"]*"[^>]*>(.*?)</div>', html, re.S)
    notices = [re.sub(r"<[^>]+>", "", item).strip() for item in notices]
    notices = [item for item in notices if item]
    candidate_ids = sorted(set(re.findall(r"\bac-[a-f0-9]+\b", html)))
    values = re.findall(r'class="dash-card-value[^"]*"[^>]*>(.*?)</p>', html, re.S)
    values = [re.sub(r"<[^>]+>", "", item).strip() for item in values]
    profit_progress = None
    for value in values:
        if "/" in value and "件" in value:
            profit_progress = value
            break
    return {
        "candidate_id_count": len(candidate_ids),
        "dash_values": values,
        "profit_progress": profit_progress,
        "notices": notices[:8],
        "has_profit_done": (
            "対象候補の利益分析はすべて完了" in html
            or "profit_done=1" in html
            or "すべて完了" in html
        ),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    _st, _url, html = fetch("GET", f"/acquisition-workspace?batch_id={BATCH}")
    before = parse_workspace(html)
    print("BEFORE", json.dumps(before, ensure_ascii=False))

    profit_clicks = []
    for index in range(1, 7):
        started = time.time()
        status, final_url, html = fetch(
            "POST", f"/acquisition-workspace/{BATCH}/run-profit", data={}
        )
        after = parse_workspace(html)
        click = {
            "click": index,
            "http_status": status,
            "final_url": final_url,
            "duration_sec": round(time.time() - started, 2),
            "workspace": after,
            "user_visible_message": after.get("notices") or [],
            "already_complete": after.get("has_profit_done"),
            "internal_server_error": status >= 500 or "Internal Server Error" in html,
        }
        profit_clicks.append(click)
        print(
            f"CLICK {index}",
            status,
            after.get("profit_progress"),
            after.get("has_profit_done"),
            (after.get("notices") or [""])[:1],
        )

    headers = {
        "X-BrandProfitFinder-Capture": "1",
        "Origin": "chrome-extension://liveverify",
        "Content-Type": "application/json",
    }
    stamp = int(time.time())
    products = [
        {
            "title": f"Verify Prada Cont {stamp}-{i}",
            "brand": "Prada",
            "current_price": "120",
            "currency": "USD",
            "url": f"https://www.fashionphile.com/products/verify-cont-{stamp}-{i}",
            "product_id": f"{stamp}{i}",
            "condition": "Excellent",
        }
        for i in range(1, 121)
    ]
    visible = [item["url"] for item in products]

    def capture_post(slice_products):
        payload = {
            "source_marketplace": "Fashionphile",
            "source_page_url": f"https://www.fashionphile.com/search?q=verify-cont-{stamp}",
            "extension_version": "1.0.0",
            "run_profit": False,
            "detected_count": 120,
            "visible_urls": visible,
            "products": slice_products,
        }
        status, _url, body = fetch(
            "POST",
            "/acquisition-workspace/import/browser-capture",
            data=payload,
            headers=headers,
        )
        return status, json.loads(body)

    def known_post(urls):
        status, _url, body = fetch(
            "POST",
            "/acquisition-workspace/import/browser-capture/known-urls",
            data={"source_marketplace": "Fashionphile", "urls": urls},
            headers=headers,
        )
        return status, json.loads(body)

    captures = []
    status1, body1 = capture_post(products[:80])
    captures.append({"capture": 1, "http_status": status1, "body": body1})
    print("CAP1", status1, body1.get("imported_this_run"), body1.get("remaining_count"))

    _status_k, known = known_post(visible)
    known_set = set(known.get("known_urls") or [])
    remaining = [item for item in products if item["url"] not in known_set]
    print("KNOWN", known.get("known_count"), "REMAINING", len(remaining))

    status2, body2 = capture_post(remaining)
    captures.append({"capture": 2, "http_status": status2, "body": body2})
    print(
        "CAP2",
        status2,
        body2.get("imported_this_run"),
        body2.get("remaining_count"),
        "submitted",
        len(body2.get("submitted_urls") or []),
    )

    status3, body3 = capture_post(products[:80])
    captures.append({"capture": 3, "http_status": status3, "body": body3})
    print("CAP3", status3, body3.get("imported_this_run"), body3.get("user_message"))

    batch_id = body2.get("batch_id") or body1.get("batch_id")
    _st, _url, ws_html = fetch("GET", f"/acquisition-workspace?batch_id={batch_id}")
    ws = parse_workspace(ws_html)

    prada = "ac-15889fd519f1"
    status_d, _url, detail_html = fetch(
        "GET", f"/acquisition-workspace/{BATCH}/candidate/{prada}"
    )
    detail = {
        "http_status": status_d,
        "has_predicted": any(
            token in detail_html for token in ("予測販売価格", "想定販売価格", "販売価格")
        ),
        "has_purchase": ("仕入" in detail_html) or ("購入価格" in detail_html),
        "has_intl_ship": ("国際送料" in detail_html) or ("海外送料" in detail_html),
        "has_duty": "関税" in detail_html,
        "has_import_tax": ("輸入消費税" in detail_html) or ("消費税" in detail_html),
        "has_domestic_ship": "国内送料" in detail_html,
        "has_fee": ("販売手数料" in detail_html) or ("国内販売手数料" in detail_html),
        "has_ebay_label": "eBay手数料" in detail_html,
        "has_profit_4580": ("4,580" in detail_html) or ("4580" in detail_html),
        "has_net_incomplete": "NET_COST_INCOMPLETE" in detail_html,
    }
    print("DETAIL", detail)

    failures = []
    if any(item.get("internal_server_error") for item in profit_clicks):
        failures.append("profit click ISE")
    if not (
        body1.get("imported_this_run") == 80
        and body2.get("imported_this_run") == 40
        and body3.get("imported_this_run") == 0
    ):
        failures.append("continuation counts unexpected")
    if len(body2.get("submitted_urls") or []) != 40:
        failures.append("second capture did not submit only remaining 40")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_page_url": f"https://www.fashionphile.com/search?q=verify-cont-{stamp}",
        "verification_mode": "live_server_api_protocol",
        "note": (
            "Capture continuation exercised against the live local BrandProfitFinder "
            "server using the Chrome extension API contract and unique Fashionphile "
            "product URLs. This is not a Chrome Extension click on a live Fashionphile "
            "search DOM page."
        ),
        "visible_product_count": 120,
        "workspace_batch_existing": BATCH,
        "before_profit": before,
        "profit_analysis_progression": profit_clicks,
        "per_capture": [
            {
                "capture": item["capture"],
                "http_status": item["http_status"],
                "detected_count": item["body"].get("detected_count"),
                "imported_this_run": item["body"].get("imported_this_run"),
                "already_imported_count": item["body"].get("already_imported_count"),
                "remaining_count": item["body"].get("remaining_count"),
                "batch_id": item["body"].get("batch_id"),
                "user_message": item["body"].get("user_message"),
                "submitted_url_count": len(item["body"].get("submitted_urls") or []),
                "imported_urls": item["body"].get("imported_urls"),
                "duplicate_urls": item["body"].get("duplicate_urls"),
            }
            for item in captures
        ],
        "known_urls_after_capture1": known.get("known_count"),
        "continuation_batch_ids": [body1.get("batch_id"), body2.get("batch_id")],
        "duplicate_verification": {
            "capture2_submitted_only_remaining": len(body2.get("submitted_urls") or []) == 40,
            "capture2_imported": body2.get("imported_this_run"),
            "capture3_imported": body3.get("imported_this_run"),
            "capture3_message": body3.get("user_message"),
            "final_workspace_candidate_mentions": ws.get("candidate_id_count"),
        },
        "profit_breakdown_verification": detail,
        "http_statuses": [item["http_status"] for item in profit_clicks]
        + [status1, status2, status3],
        "ui_messages": {
            "profit": [item.get("user_visible_message") for item in profit_clicks],
            "capture": [item["body"].get("user_message") for item in captures],
        },
        "failures": failures,
        "total_durations_sec": [item["duration_sec"] for item in profit_clicks],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", OUT)
    print("FAILURES", failures)


if __name__ == "__main__":
    main()
