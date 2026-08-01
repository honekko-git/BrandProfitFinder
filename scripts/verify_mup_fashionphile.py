"""Verify MUP Fashionphile path against fixture (and optional live network).

Usage:
  python scripts/verify_mup_fashionphile.py
  python scripts/verify_mup_fashionphile.py --live
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.live_fashionphile_intake import search_fashionphile_listings
from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.browser_acquisition.fashionphile_acquirer import (
    FashionphileAcquirer,
    parse_fashionphile_html,
)

FIXTURE = ROOT / "tests" / "fixtures" / "browser_acquisition" / "fashionphile_mup_20.html"


@dataclass
class VerifyRow:
    title: str
    price: str
    currency: str
    jpy: str
    condition: str
    url: str
    ok: bool
    error: str = ""


def verify_listings(listings) -> list[VerifyRow]:
    rows: list[VerifyRow] = []
    for item in listings:
        error = ""
        ok = True
        if not item.title:
            ok = False
            error = "missing title"
        elif item.price is None or item.price <= 0:
            ok = False
            error = "invalid price"
        elif not item.currency:
            ok = False
            error = "missing currency"
        elif not item.url:
            ok = False
            error = "missing url"
        jpy = purchase_price_jpy(item.price, item.currency) if ok else Decimal("0")
        rows.append(
            VerifyRow(
                title=item.title,
                price=str(item.price),
                currency=item.currency,
                jpy=str(jpy),
                condition=item.condition or "-",
                url=item.url,
                ok=ok,
                error=error,
            )
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fashionphile MUP intake")
    parser.add_argument("--live", action="store_true", help="Hit live Fashionphile search")
    parser.add_argument("--keyword", default="Chanel wallet")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    report: dict = {
        "mode": "live" if args.live else "fixture",
        "keyword": args.keyword,
        "limit": args.limit,
        "count": 0,
        "ok_count": 0,
        "fail_count": 0,
        "failures": [],
        "samples": [],
    }

    if args.live:
        listings, status, detail = search_fashionphile_listings(
            args.keyword,
            limit=args.limit,
            acquirer=FashionphileAcquirer(purchase_limit=args.limit),
        )
        report["status"] = status
        report["detail"] = detail
    else:
        html = FIXTURE.read_text(encoding="utf-8")
        listings = parse_fashionphile_html(html)[: args.limit]
        report["status"] = "LIVE"
        report["detail"] = f"fixture:{FIXTURE.name}"

    rows = verify_listings(listings)
    report["count"] = len(rows)
    report["ok_count"] = sum(1 for row in rows if row.ok)
    report["fail_count"] = sum(1 for row in rows if not row.ok)
    report["failures"] = [asdict(row) for row in rows if not row.ok]
    report["samples"] = [asdict(row) for row in rows[:5]]

    out = ROOT / "output" / "mup_fashionphile_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    safe = json.dumps(report, ensure_ascii=True, indent=2)
    print(safe)
    print(f"wrote {out}")
    return 0 if report["ok_count"] >= min(20, args.limit) and report["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
