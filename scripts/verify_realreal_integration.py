"""Verify The RealReal overseas acquisition against Yahoo/Mercari domestic comps.

Clearly separates fixture-based end-to-end verification from optional live probes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.realreal_acquirer import parse_realreal_html
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

FIXTURE = ROOT / "tests" / "fixtures" / "browser_acquisition" / "realreal_search_results.html"
PRODUCT_COUNT = 20


def _domestic_title(identity, brand: str, category: str, *, overseas_title: str) -> str:
    brand_key = identity.brand or brand.upper()
    ja_brand = BRAND_JA.get(brand_key, brand_key.title() if brand_key else brand)
    cat_ja = CATEGORY_JA.get(identity.category, CATEGORY_JA.get(category, "財布"))
    material_ja = MATERIAL_MAP.get(identity.material, "")
    color_ja = COLOR_MAP.get(identity.color, "")
    model = identity.model_numbers[0] if identity.model_numbers else ""
    overseas = " ".join(
        token
        for token in overseas_title.replace("/", " ").split()
        if token.lower()
        not in {"therealreal", "realreal", "authenticated", "condition", "excellent", "very", "good", "fair", "was", "now", "off"}
    )[:90]
    return " ".join(part for part in [ja_brand, model, overseas or cat_ja, material_ja, color_ja] if part)


def _yahoo_sold_html(title: str, price: int, auction_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li class="Product">
<a href="https://auctions.yahoo.co.jp/jp/auction/{auction_id}">{title}</a>
<div>落札 {price:,} 円</div>
</li></ul></body></html>"""


def _yahoo_open_html(title: str, price: int, auction_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li class="Product">
<a href="https://auctions.yahoo.co.jp/jp/auction/{auction_id}o">{title}</a>
<div>現在 {price:,} 円 即決 {price + 3000:,} 円 入札 2</div>
</li></ul></body></html>"""


def _mercari_html(title: str, price: int, item_id: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><body>
<ul><li data-testid="item-cell">
<a href="/item/{item_id}">
<mer-item-thumbnail item-name="{title}" price="{price}"></mer-item-thumbnail>
</a>
</li></ul></body></html>"""


def main() -> int:
    listings = parse_realreal_html(FIXTURE.read_text(encoding="utf-8"))[:PRODUCT_COUNT]
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")

    # Process one candidate at a time. Many RealReal wallets share Yahoo query
    # strings ("シャネル 財布"), so a shared html_by_query map would overwrite.
    yahoo_selected = 0
    mercari_selected = 0
    successful = 0
    no_comparable = 0
    near_miss = 0
    profit_ok = 0
    detailed = []

    for index, item in enumerate(listings, start=1):
        identity = extract_listing_identity(
            title=item.title,
            brand=item.brand,
            category=item.category,
            condition=item.condition,
        )
        jpy = purchase_price_jpy(item.price, item.currency)
        brand = item.brand or identity.brand
        category = item.category or identity.category
        candidate = BatchProfitCandidate(
            candidate_id=f"trr-{index:02d}",
            title=item.title,
            brand=brand,
            category=category,
            detected_subtype="",
            detected_material=identity.material if identity.material != "UNKNOWN" else "",
            condition=item.condition,
            purchase_price=item.price,
            currency=item.currency,
            purchase_price_jpy=jpy,
            purchase_url=item.url,
            purchase_source="The RealReal",
        )

        strong = _domestic_title(identity, brand, category, overseas_title=item.title)
        weak = " ".join(
            part
            for part in [
                BRAND_JA.get(identity.brand or brand.upper(), brand),
                CATEGORY_JA.get(identity.category, "財布"),
            ]
            if part
        )
        # Prefer strong titles so fixture verification exercises the full profit path.
        yahoo_title = strong
        mercari_title = strong if index % 3 else weak
        yahoo_price = max(10000, int(jpy) + 20000 + index * 500)
        mercari_price = max(10000, int(jpy) + 18000 + index * 500)
        sold = _yahoo_sold_html(yahoo_title, yahoo_price, f"tr{index:04d}")
        opened = _yahoo_open_html(yahoo_title, yahoo_price + 1500, f"to{index:04d}")
        mercari = _mercari_html(mercari_title, mercari_price, f"m{index:010d}")
        html_by_query: dict[str, str] = {}
        open_by_query: dict[str, str] = {}
        mercari_by_query: dict[str, str] = {}
        for query in build_yahoo_search_queries(title=item.title, brand=brand, category=category):
            html_by_query[query] = sold
            open_by_query[query] = opened
        for query in build_mercari_search_queries(title=item.title, brand=brand, category=category):
            mercari_by_query[query] = mercari

        run = run_batch_profit(
            [candidate],
            cost_profile=profile,
            use_cache=False,
            html_by_query=html_by_query,
            open_html_by_query=open_by_query,
            mercari_html_by_query=mercari_by_query,
        )
        result = run.results[0]
        row = {
            "realreal_title": item.title,
            "realreal_url": item.url,
            "realreal_usd": str(item.price),
            "converted_jpy": str(jpy),
            "brand": brand,
            "category": category,
            "condition": item.condition,
            "identity_brand": identity.brand,
            "identity_category": identity.category,
            "identity_material": identity.material,
            "identity_color": identity.color,
            "yahoo_queries": list(result.yahoo_queries),
            "accepted_comparable_count": result.accepted_comparable_count,
            "rejected_comparable_count": result.rejected_sample_count,
            "selected_marketplace": result.yahoo_marketplace,
            "selected_title": result.yahoo_best_title,
            "selected_price_jpy": result.yahoo_best_price_jpy,
            "selected_url": result.yahoo_best_url,
            "matching_score": result.yahoo_best_score,
            "matched_attributes": result.yahoo_best_attributes,
            "net_profit": str(result.net_estimated_profit) if result.net_estimated_profit is not None else None,
            "gross_profit": str(result.gross_estimated_profit),
            "decision": result.batch_decision,
            "failure_reason": result.failure_reason,
            "acquisition_source": result.candidate.purchase_source,
            "purchase_url": result.candidate.purchase_url,
        }
        detailed.append(row)
        if result.yahoo_marketplace == "Yahoo Auctions":
            yahoo_selected += 1
        elif result.yahoo_marketplace == "Mercari":
            mercari_selected += 1
        else:
            no_comparable += 1
        if result.yahoo_best_score >= 70:
            successful += 1
        elif result.yahoo_best_score >= 45:
            near_miss += 1
        if result.net_estimated_profit is not None or result.gross_estimated_profit != 0:
            profit_ok += 1

    report = {
        "verification_mode": "fixture",
        "note": (
            "Fixture-based end-to-end verification using saved The RealReal HTML plus "
            "identity-matched Yahoo/Mercari fixtures. Not live results. "
            "Candidates are processed individually because many RealReal wallets share "
            "identical Yahoo/Mercari search query strings."
        ),
        "product_count": len(detailed),
        "valid_realreal_acquisition_candidates": len(detailed),
        "url_failures": sum(1 for row in detailed if not row["purchase_url"].startswith("http")),
        "successful_matches": successful,
        "near_miss_or_ambiguous": near_miss,
        "no_comparable_cases": no_comparable,
        "yahoo_selected_as_best": yahoo_selected,
        "mercari_selected_as_best": mercari_selected,
        "profit_calculation_successes": profit_ok,
        "brands": sorted({row["brand"] for row in detailed if row["brand"]}),
        "categories": sorted({row["category"] for row in detailed if row["category"]}),
        "live_probe": _optional_live_probe(),
        "results": detailed,
    }
    out = ROOT / "output" / "realreal_integration_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in (
        "verification_mode",
        "product_count",
        "valid_realreal_acquisition_candidates",
        "successful_matches",
        "near_miss_or_ambiguous",
        "no_comparable_cases",
        "yahoo_selected_as_best",
        "mercari_selected_as_best",
        "profit_calculation_successes",
        "brands",
        "categories",
        "live_probe",
    )}
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(f"wrote {out}")
    ok = (
        report["product_count"] >= 20
        and report["valid_realreal_acquisition_candidates"] >= 20
        and report["url_failures"] == 0
        and report["yahoo_selected_as_best"] + report["mercari_selected_as_best"] >= 10
        and all(row["acquisition_source"] == "The RealReal" for row in detailed)
        and all(row["purchase_url"].startswith("https://www.therealreal.com/products/") for row in detailed)
    )
    return 0 if ok else 1


def _optional_live_probe() -> dict:
    """Optional live The RealReal search smoke; never represented as fixture success."""
    try:
        from marketplace.browser_acquisition.realreal_acquirer import RealRealAcquirer

        result = RealRealAcquirer(purchase_limit=5).search_keyword("Chanel wallet")
        return {
            "attempted": True,
            "status": result.status.value,
            "listing_count": len(result.listings),
            "blocked_reason": result.blocking_reason,
            "sample_urls": [item.url for item in result.listings[:3]],
            "sample_prices_usd": [str(item.price) for item in result.listings[:3]],
            "note": "Live probe only. Fixture verification above is authoritative for pipeline wiring.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "attempted": True,
            "status": "FAILED",
            "listing_count": 0,
            "error": str(exc),
            "note": (
                "Live The RealReal search failed. Use saved HTML upload. "
                "Fixture verification remains separate."
            ),
        }


if __name__ == "__main__":
    raise SystemExit(main())
