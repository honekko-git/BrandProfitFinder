"""Verify Yahoo Auctions live integration for MUP Fashionphile products."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html
from marketplace.browser_acquisition.listing_identity import normalize_brand
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit

MUP = ROOT / "tests" / "fixtures" / "browser_acquisition" / "fashionphile_mup_20.html"
SOLD = ROOT / "tests" / "fixtures" / "browser_acquisition" / "yahoo_live_ja.html"
OPEN = ROOT / "tests" / "fixtures" / "browser_acquisition" / "yahoo_open_mup_20.html"


def main() -> int:
    listings = parse_fashionphile_html(MUP.read_text(encoding="utf-8"))[:20]
    sold_html = SOLD.read_text(encoding="utf-8")
    open_html = OPEN.read_text(encoding="utf-8")
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")

    candidates: list[BatchProfitCandidate] = []
    html_by_query: dict[str, str] = {}
    open_by_query: dict[str, str] = {}
    for index, item in enumerate(listings, start=1):
        brand = item.brand or normalize_brand("", title=item.title)
        jpy = purchase_price_jpy(item.price, item.currency)
        candidate = BatchProfitCandidate(
            candidate_id=f"mup-{index:02d}",
            title=item.title,
            brand=brand,
            category=item.category or "Wallet",
            detected_subtype="",
            detected_material="",
            condition=item.condition or "Very Good",
            purchase_price=item.price,
            currency=item.currency,
            purchase_price_jpy=jpy,
            purchase_url=item.url,
            purchase_source="Fashionphile",
        )
        candidates.append(candidate)
        for query in build_yahoo_search_queries(
            title=item.title, brand=brand, category=item.category or "Wallet"
        ):
            html_by_query[query] = sold_html
            open_by_query[query] = open_html

    run = run_batch_profit(
        candidates,
        cost_profile=profile,
        use_cache=False,
        html_by_query=html_by_query,
        open_html_by_query=open_by_query,
    )

    successful = []
    rejected = []
    ambiguous = []
    failed = []
    for item in run.results:
        row = {
            "candidate_id": item.candidate.candidate_id,
            "title": item.candidate.title,
            "brand": item.candidate.brand,
            "overseas_price": str(item.candidate.purchase_price),
            "overseas_currency": item.candidate.currency,
            "overseas_jpy": str(item.candidate.purchase_price_jpy),
            "overseas_url": item.candidate.purchase_url,
            "yahoo_title": item.yahoo_best_title,
            "yahoo_price_jpy": item.yahoo_best_price_jpy,
            "yahoo_url": item.yahoo_best_url,
            "matching_score": item.yahoo_best_score,
            "matched_attributes": item.yahoo_best_attributes,
            "net_profit": str(item.net_estimated_profit) if item.net_estimated_profit is not None else None,
            "gross_profit": str(item.gross_estimated_profit),
            "accepted": item.accepted_comparable_count,
            "rejected": item.rejected_sample_count,
            "decision": item.batch_decision,
        }
        has_yahoo = bool(item.yahoo_best_title and item.yahoo_best_url and item.yahoo_best_price_jpy > 0)
        has_profit = item.net_estimated_profit is not None or item.gross_estimated_profit != 0
        if has_yahoo and item.yahoo_best_score >= 45 and has_profit:
            successful.append(row)
        elif has_yahoo:
            ambiguous.append(row)
        elif item.rejected_sample_count > 0 and item.accepted_comparable_count == 0:
            rejected.append(row)
        else:
            failed.append(row)

    report = {
        "product_count": len(candidates),
        "successful_matches": len(successful),
        "ambiguous_matches": len(ambiguous),
        "rejected_matches": len(rejected),
        "failed_searches": len(failed),
        "brands": sorted({row["brand"] for row in successful + ambiguous + rejected + failed if row["brand"]}),
        "successful": successful,
        "ambiguous": ambiguous[:5],
        "rejected": rejected[:5],
        "failed": failed[:5],
    }
    out = ROOT / "output" / "yahoo_auctions_integration_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "product_count", "successful_matches", "ambiguous_matches",
        "rejected_matches", "failed_searches", "brands"
    )}, ensure_ascii=True, indent=2))
    print(f"wrote {out}")
    return 0 if report["successful_matches"] >= 15 and report["product_count"] >= 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
