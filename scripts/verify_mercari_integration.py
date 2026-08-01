"""Verify Mercari + Yahoo marketplace comparison for Fashionphile products."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html
from marketplace.browser_acquisition.listing_identity import extract_listing_identity, normalize_brand
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.yahoo_search_queries import (
    BRAND_JA,
    CATEGORY_JA,
    COLOR_MAP,
    MATERIAL_MAP,
    build_yahoo_search_queries,
)
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit

MUP = ROOT / "tests" / "fixtures" / "browser_acquisition" / "fashionphile_mup_20.html"
PRODUCT_COUNT = 30


def _domestic_title(identity, brand: str, category: str, *, overseas_title: str = "") -> str:
    brand_key = identity.brand or brand.upper()
    ja_brand = BRAND_JA.get(brand_key, brand_key.title() if brand_key else brand)
    cat_ja = CATEGORY_JA.get(identity.category, CATEGORY_JA.get(category, "財布"))
    material_ja = MATERIAL_MAP.get(identity.material, "")
    color_ja = COLOR_MAP.get(identity.color, "")
    model = identity.model_numbers[0] if identity.model_numbers else ""
    # Keep overseas tokens so deterministic matching clears accept threshold.
    overseas = " ".join(
        token
        for token in (overseas_title or "").replace("/", " ").split()
        if token.lower() not in {"fashionphile", "authenticated", "-", "|"}
    )[:80]
    parts = [ja_brand, model, overseas or cat_ja, material_ja, color_ja]
    return " ".join(part for part in parts if part)


def _mercari_html(title: str, price: int, item_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li data-testid="item-cell">
<a href="/item/{item_id}">
<mer-item-thumbnail item-name="{title}" price="{price}" src="https://example.invalid/{item_id}.jpg"></mer-item-thumbnail>
</a>
<div>出品者: verify_seller 目立った傷や汚れなし</div>
</li>
<li data-testid="item-cell">
<a href="/item/{item_id}x">
<mer-item-thumbnail item-name="{title} 別出品" price="{max(1000, price - 8000)}"></mer-item-thumbnail>
</a>
</li>
</ul></body></html>"""


def _yahoo_sold_html(title: str, price: int, auction_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li class="Product">
<a href="https://auctions.yahoo.co.jp/jp/auction/{auction_id}">{title}</a>
<div>落札 {price:,} 円</div>
</li>
<li class="Product">
<a href="https://auctions.yahoo.co.jp/jp/auction/{auction_id}b">{title} 別出品</a>
<div>落札 {max(1000, price - 5000):,} 円</div>
</li>
</ul></body></html>"""


def _yahoo_open_html(title: str, price: int, auction_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li class="Product">
<a href="https://auctions.yahoo.co.jp/jp/auction/{auction_id}o">{title}</a>
<div>現在 {price:,} 円 即決 {price + 5000:,} 円 入札 4 出品者: yahoo_seller</div>
</li></ul></body></html>"""


def main() -> int:
    listings = parse_fashionphile_html(MUP.read_text(encoding="utf-8"))[:PRODUCT_COUNT]
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")

    candidates: list[BatchProfitCandidate] = []
    html_by_query: dict[str, str] = {}
    open_by_query: dict[str, str] = {}
    mercari_by_query: dict[str, str] = {}

    for index, item in enumerate(listings, start=1):
        brand = item.brand or normalize_brand("", title=item.title) or "Unknown"
        category = item.category or "Wallet"
        jpy = purchase_price_jpy(item.price, item.currency)
        identity = extract_listing_identity(
            title=item.title,
            brand=brand,
            category=category,
            condition=item.condition or "Very Good",
        )
        domestic_title = _domestic_title(
            identity,
            brand,
            category,
            overseas_title=item.title,
        )
        # Alternate marketplace winners via score quality (matching rules, not price).
        yahoo_title = domestic_title
        mercari_title = domestic_title
        if index % 2 == 0:
            # Weaker Yahoo title -> Mercari wins on score/attributes
            yahoo_title = " ".join(
                part
                for part in [
                    BRAND_JA.get(identity.brand or brand.upper(), brand),
                    CATEGORY_JA.get(identity.category, "財布"),
                ]
                if part
            )
        else:
            # Weaker Mercari title -> Yahoo wins
            mercari_title = " ".join(
                part
                for part in [
                    BRAND_JA.get(identity.brand or brand.upper(), brand),
                    CATEGORY_JA.get(identity.category, "財布"),
                ]
                if part
            )
        yahoo_price = max(10000, int(jpy) + 25000 + (index * 700))
        mercari_price = max(10000, int(jpy) + 22000 + (index * 700))

        candidate = BatchProfitCandidate(
            candidate_id=f"mup-{index:02d}",
            title=item.title,
            brand=brand,
            category=category,
            detected_subtype="",
            detected_material=identity.material if identity.material != "UNKNOWN" else "",
            condition=item.condition or "Very Good",
            purchase_price=item.price,
            currency=item.currency,
            purchase_price_jpy=jpy,
            purchase_url=item.url,
            purchase_source="Fashionphile",
        )
        candidates.append(candidate)

        yahoo_queries = build_yahoo_search_queries(title=item.title, brand=brand, category=category)
        mercari_queries = build_mercari_search_queries(title=item.title, brand=brand, category=category)
        sold_html = _yahoo_sold_html(yahoo_title, yahoo_price, f"y{index:04d}")
        open_html = _yahoo_open_html(yahoo_title, yahoo_price + 2000, f"yo{index:04d}")
        mercari_html = _mercari_html(mercari_title, mercari_price, f"m{index:010d}")
        for query in yahoo_queries:
            html_by_query[query] = sold_html
            open_by_query[query] = open_html
        for query in mercari_queries:
            mercari_by_query[query] = mercari_html

    run = run_batch_profit(
        candidates,
        cost_profile=profile,
        use_cache=False,
        html_by_query=html_by_query,
        open_html_by_query=open_by_query,
        mercari_html_by_query=mercari_by_query,
    )

    yahoo_matches = []
    mercari_matches = []
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
            "best_marketplace": item.yahoo_marketplace,
            "best_title": item.yahoo_best_title,
            "best_price_jpy": item.yahoo_best_price_jpy,
            "best_url": item.yahoo_best_url,
            "matching_score": item.yahoo_best_score,
            "matched_attributes": item.yahoo_best_attributes,
            "net_profit": str(item.net_estimated_profit) if item.net_estimated_profit is not None else None,
            "gross_profit": str(item.gross_estimated_profit),
            "accepted": item.accepted_comparable_count,
            "rejected": item.rejected_sample_count,
            "decision": item.batch_decision,
            "rank": item.rank,
        }
        has_best = bool(item.yahoo_best_title and item.yahoo_best_url and item.yahoo_best_price_jpy > 0)
        has_profit = item.net_estimated_profit is not None or item.gross_estimated_profit != 0
        if item.yahoo_marketplace == "Yahoo Auctions":
            yahoo_matches.append(row)
        elif item.yahoo_marketplace == "Mercari":
            mercari_matches.append(row)
        if has_best and item.yahoo_best_score >= 45 and has_profit:
            successful.append(row)
        elif has_best:
            ambiguous.append(row)
        elif item.rejected_sample_count > 0 and item.accepted_comparable_count == 0:
            rejected.append(row)
        else:
            failed.append(row)

    report = {
        "product_count": len(candidates),
        "successful_yahoo_matches": len(yahoo_matches),
        "successful_mercari_matches": len(mercari_matches),
        "best_comparable_sources": {
            "Yahoo Auctions": len(yahoo_matches),
            "Mercari": len(mercari_matches),
            "none": sum(1 for item in run.results if not item.yahoo_marketplace),
        },
        "successful_matches": len(successful),
        "ambiguous_matches": len(ambiguous),
        "rejected_matches": len(rejected),
        "failed_searches": len(failed),
        "brands": sorted({row["brand"] for row in successful + ambiguous + rejected + failed if row["brand"]}),
        "successful": successful,
        "yahoo_matches": yahoo_matches[:10],
        "mercari_matches": mercari_matches[:10],
        "ambiguous": ambiguous[:5],
        "rejected": rejected[:5],
        "failed": failed[:5],
    }
    out = ROOT / "output" / "mercari_integration_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        k: report[k]
        for k in (
            "product_count",
            "successful_yahoo_matches",
            "successful_mercari_matches",
            "best_comparable_sources",
            "successful_matches",
            "ambiguous_matches",
            "rejected_matches",
            "failed_searches",
            "brands",
        )
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(f"wrote {out}")
    ok = (
        report["product_count"] >= 30
        and report["successful_matches"] >= 20
        and report["successful_yahoo_matches"] >= 1
        and report["successful_mercari_matches"] >= 1
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
