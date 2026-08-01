"""Collision-safe Vestiaire verification + four-source operational smoke test."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.acquisition_workspace.normalization import purchase_price_jpy
from marketplace.browser_acquisition.comparable_candidate import (
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.rebag_acquirer import parse_rebag_html
from marketplace.browser_acquisition.realreal_acquirer import parse_realreal_html
from marketplace.browser_acquisition.vestiaire_acquirer import VestiaireAcquirer, parse_vestiaire_html
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable
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
from profit_discovery.discovery_validation.real_profit_config import resolve_currency_jpy_exchange_rate
from tests.acquisition_test_helpers import make_candidate

FIXTURE = ROOT / "tests" / "fixtures" / "browser_acquisition" / "vestiaire_search_results.html"
PRODUCT_COUNT = 20


def _domestic_title(identity, brand: str, category: str, *, overseas_title: str) -> str:
    brand_key = identity.brand or brand.upper()
    ja_brand = BRAND_JA.get(brand_key, brand_key.title() if brand_key else brand)
    cat_ja = CATEGORY_JA.get(identity.category, CATEGORY_JA.get(category, "バッグ"))
    material_ja = MATERIAL_MAP.get(identity.material, "")
    color_ja = COLOR_MAP.get(identity.color, "")
    model = identity.model_numbers[0] if identity.model_numbers else ""
    overseas = " ".join(
        token
        for token in overseas_title.replace("/", " ").split()
        if token.lower()
        not in {
            "vestiaire",
            "collective",
            "authenticated",
            "condition",
            "excellent",
            "very",
            "good",
            "fair",
            "we",
            "love",
        }
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


def _process_one(item, index: int, profile, source_type: str) -> dict:
    identity = extract_listing_identity(
        title=item.title,
        brand=item.brand,
        category=item.category,
        condition=item.condition,
    )
    try:
        jpy = purchase_price_jpy(item.price, item.currency)
        fx_rate = resolve_currency_jpy_exchange_rate(item.currency)
        fx_error = ""
    except ValueError as exc:
        return {
            "verification_source_type": source_type,
            "vestiaire_title": item.title,
            "source_url": item.url,
            "original_price": str(item.price),
            "original_currency": item.currency,
            "converted_jpy": None,
            "failure_reason": str(exc),
            "profit_calculation_success": False,
        }

    brand = item.brand or identity.brand
    category = item.category or identity.category
    candidate = BatchProfitCandidate(
        candidate_id=f"vc-{index:02d}",
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
        purchase_source="Vestiaire Collective",
    )
    strong = _domestic_title(identity, brand, category, overseas_title=item.title)
    yahoo_price = max(10000, int(jpy) + 20000 + index * 500)
    mercari_price = max(10000, int(jpy) + 18000 + index * 500)
    sold = _yahoo_sold_html(strong, yahoo_price, f"vc{index:04d}")
    opened = _yahoo_open_html(strong, yahoo_price + 1500, f"vo{index:04d}")
    mercari = _mercari_html(strong, mercari_price, f"m{index:010d}")
    html_by_query = {
        query: sold for query in build_yahoo_search_queries(title=item.title, brand=brand, category=category)
    }
    open_by_query = {query: opened for query in html_by_query}
    mercari_by_query = {
        query: mercari
        for query in build_mercari_search_queries(title=item.title, brand=brand, category=category)
    }
    run = run_batch_profit(
        [candidate],
        cost_profile=profile,
        use_cache=False,
        html_by_query=html_by_query,
        open_html_by_query=open_by_query,
        mercari_html_by_query=mercari_by_query,
    )
    result = run.results[0]
    return {
        "verification_source_type": source_type,
        "vestiaire_title": item.title,
        "source_url_present": bool(item.url),
        "source_url": item.url,
        "original_price": str(item.price),
        "original_currency": item.currency,
        "converted_jpy": str(jpy),
        "exchange_rate_source": f"{item.currency}/JPY={fx_rate}",
        "normalized_brand": identity.brand,
        "normalized_model_number": list(identity.model_numbers),
        "normalized_product_family": list(identity.model_family_tokens),
        "normalized_category": identity.category,
        "normalized_material": identity.material,
        "normalized_color": identity.color,
        "normalized_hardware": identity.hardware,
        "normalized_condition": identity.condition,
        "yahoo_queries": list(result.yahoo_queries),
        "yahoo_result_count": result.raw_sample_count,
        "mercari_queries": list(
            build_mercari_search_queries(title=item.title, brand=brand, category=category)
        ),
        "accepted_comparable_count": result.accepted_comparable_count,
        "rejected_comparable_count": result.rejected_sample_count,
        "selected_domestic_marketplace": result.yahoo_marketplace,
        "selected_comparable_title": result.yahoo_best_title,
        "selected_comparable_url": result.yahoo_best_url,
        "selected_comparable_price": result.yahoo_best_price_jpy,
        "matching_score": result.yahoo_best_score,
        "matched_attributes": result.yahoo_best_attributes,
        "match_status": (
            "accepted"
            if result.yahoo_best_score >= 70
            else "near_miss"
            if result.yahoo_best_score >= 45
            else "none"
        ),
        "net_profit": str(result.net_estimated_profit) if result.net_estimated_profit is not None else None,
        "roi": str(result.net_roi) if result.net_roi is not None else None,
        "decision": result.batch_decision,
        "failure_reason": result.failure_reason,
        "acquisition_source": result.candidate.purchase_source,
        "purchase_url": result.candidate.purchase_url,
        "profit_calculation_success": bool(
            result.net_estimated_profit is not None or result.gross_estimated_profit != 0
        ),
        "warnings": list(result.warnings),
    }


def _optional_live_probe() -> dict:
    from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError

    queries = [
        "Louis Vuitton Neverfull",
        "Chanel Classic",
        "Hermes Kelly",
        "Gucci Marmont",
        "Prada Re Edition",
        "Dior Lady",
        "Saint Laurent Loulou",
        "Bottega Cassette",
        "Fendi Peekaboo",
        "Celine Triomphe",
    ]
    all_listings = []
    blocked = 0
    errors: list[str] = []
    for query in queries:
        try:
            result = VestiaireAcquirer(purchase_limit=5).search_keyword(query)
        except AcquisitionBlockedError as exc:
            blocked += 1
            errors.append(f"{query}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            blocked += 1
            errors.append(f"{query}: {exc}")
            continue
        if result.status.value == "LIVE" and result.listings:
            all_listings.extend(result.listings)
        else:
            blocked += 1
            errors.append(f"{query}: {result.status.value} {result.detail or result.blocking_reason}")
    # Deduplicate by URL
    seen: set[str] = set()
    unique = []
    for item in all_listings:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return {
        "attempted": True,
        "queries": queries,
        "listing_count": len(unique),
        "blocked_or_empty_queries": blocked,
        "errors": errors[:20],
        "sample_urls": [item.url for item in unique[:5]],
        "sample_currencies": sorted({item.currency for item in unique}),
        "sample_brands": sorted({item.brand for item in unique if item.brand}),
        "note": "Live probe only. Fixture/saved-HTML sections remain authoritative for pipeline wiring.",
        "listings": [
            {
                "title": item.title,
                "url": item.url,
                "price": str(item.price),
                "currency": item.currency,
                "brand": item.brand,
                "category": item.category,
            }
            for item in unique[:20]
        ],
    }


def _four_source_smoke() -> dict:
    fixtures = ROOT / "tests" / "fixtures" / "browser_acquisition"
    sources = {
        "Fashionphile": parse_fashionphile_html(
            (fixtures / "fashionphile_search_results.html").read_text(encoding="utf-8")
        )[:1],
        "Rebag": parse_rebag_html((fixtures / "rebag_search_results.html").read_text(encoding="utf-8"))[:1],
        "The RealReal": parse_realreal_html(
            (fixtures / "realreal_search_results.html").read_text(encoding="utf-8")
        )[:1],
        "Vestiaire Collective": parse_vestiaire_html(
            (fixtures / "vestiaire_search_results.html").read_text(encoding="utf-8")
        )[:1],
    }
    rows = []
    for source_name, listings in sources.items():
        assert listings, f"missing fixture listing for {source_name}"
        item = listings[0]
        assert item.url.startswith("http")
        jpy = purchase_price_jpy(item.price, item.currency)
        yahoo = candidate_from_best_comparable(
            YahooBestComparable(
                title="yahoo",
                price_jpy=int(jpy) + 30000,
                url="https://auctions.yahoo.co.jp/jp/auction/smoke1",
                matching_score=88,
                matched_attributes="score:88",
            ),
            marketplace="Yahoo Auctions",
        )
        mercari = candidate_from_best_comparable(
            YahooBestComparable(
                title="mercari",
                price_jpy=int(jpy) + 25000,
                url="https://jp.mercari.com/item/msmoke1",
                matching_score=70,
                matched_attributes="score:70",
            ),
            marketplace="Mercari",
        )
        selected = select_best_comparable_candidate([yahoo, mercari])
        assert selected is not None
        assert selected.marketplace in {"Yahoo Auctions", "Mercari"}
        assert selected.marketplace not in {
            "Fashionphile",
            "Rebag",
            "The RealReal",
            "Vestiaire Collective",
        }
        candidate = make_candidate(
            source_name=source_name,
            purchase_url=item.url,
            currency=item.currency,
        )
        detail = build_sourcing_detail(candidate=candidate, batch_result=None, batch_id="smoke")
        rows.append(
            {
                "acquisition_source": source_name,
                "acquisition_url": item.url,
                "converted_jpy": str(jpy),
                "selected_domestic_marketplace": selected.marketplace,
                "selected_domestic_url": selected.listing_url,
                "detail_marketplace": detail.marketplace,
                "detail_purchase_url": detail.purchase_url,
            }
        )
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "status": "PASS",
        "sources": rows,
        "note": "Deterministic fixture smoke; no live network.",
    }


def main() -> int:
    listings = parse_vestiaire_html(FIXTURE.read_text(encoding="utf-8"))[:PRODUCT_COUNT]
    profile = CostProfileStore(profiles=default_cost_profiles()).get("standard")
    detailed = []
    for index, item in enumerate(listings, start=1):
        detailed.append(_process_one(item, index, profile, "fixture"))

    live = _optional_live_probe()
    live_rows = []
    for index, payload in enumerate(live.get("listings") or [], start=1):
        # Re-parse as AcquiredListing-like via mini HTML card for pipeline
        from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus

        item = AcquiredListing(
            external_id=str(index),
            title=payload["title"],
            brand=payload.get("brand") or "",
            category=payload.get("category") or "",
            condition="Used",
            price=__import__("decimal").Decimal(payload["price"]),
            currency=payload["currency"],
            url=payload["url"],
            image_url="",
            retrieved_at=datetime.now(tz=UTC).isoformat(),
            source="Vestiaire Collective",
            raw_title=payload["title"],
            acquisition_status=AcquisitionStatus.LIVE,
        )
        live_rows.append(_process_one(item, 100 + index, profile, "live"))

    # Saved-HTML section: diverse sample across brands (explicitly labeled, not live).
    saved_rows = []
    by_brand: dict[str, list] = {}
    for item in listings:
        by_brand.setdefault(item.brand or "Unknown", []).append(item)
    diverse_saved = []
    for brand_items in by_brand.values():
        diverse_saved.extend(brand_items[:2])
    for index, item in enumerate(diverse_saved[:20], start=1):
        saved_rows.append(_process_one(item, 200 + index, profile, "saved_html"))

    smoke = _four_source_smoke()

    def _summarize(rows: list[dict]) -> dict:
        return {
            "count": len(rows),
            "url_failures": sum(1 for row in rows if not str(row.get("source_url") or "").startswith("http")),
            "currency_failures": sum(1 for row in rows if row.get("converted_jpy") is None),
            "yahoo_selected": sum(1 for row in rows if row.get("selected_domestic_marketplace") == "Yahoo Auctions"),
            "mercari_selected": sum(1 for row in rows if row.get("selected_domestic_marketplace") == "Mercari"),
            "near_miss": sum(1 for row in rows if row.get("match_status") == "near_miss"),
            "no_comparable": sum(1 for row in rows if row.get("match_status") == "none"),
            "profit_successes": sum(1 for row in rows if row.get("profit_calculation_success")),
            "brands": sorted({row.get("normalized_brand") for row in rows if row.get("normalized_brand")}),
            "categories": sorted({row.get("normalized_category") for row in rows if row.get("normalized_category")}),
            "currencies": sorted({row.get("original_currency") for row in rows if row.get("original_currency")}),
        }

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "schema_version": "v3-7",
        "live": {
            "probe": {k: v for k, v in live.items() if k != "listings"},
            "pipeline_rows": live_rows,
            "summary": _summarize(live_rows),
        },
        "saved_html": {
            "note": "Saved-HTML labeled run using the Vestiaire fixture file (not live retrieval).",
            "pipeline_rows": saved_rows,
            "summary": _summarize(saved_rows),
        },
        "fixture": {
            "note": "Fixture-based end-to-end verification. Candidates processed one-at-a-time (collision-safe).",
            "pipeline_rows": detailed,
            "summary": _summarize(detailed),
        },
        "aggregate": {
            "fixture_product_count": len(detailed),
            "live_listing_count": live.get("listing_count", 0),
            "saved_html_count": len(saved_rows),
            "four_source_smoke": smoke["status"],
        },
        "four_source_operational_smoke_test": smoke,
        "known_limitations": [
            "Live locale may localize prices to JPY; parser reads displayed currency.",
            "Identical Yahoo/Mercari query strings require one-candidate-at-a-time verification harness.",
            "Buyer service fees shown by Vestiaire are not extracted into ProfitCalculator in this phase.",
        ],
    }

    out = ROOT / "output" / "vestiaire_integration_verification.json"
    smoke_out = ROOT / "output" / "four_source_operational_smoke_test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    smoke_out.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "fixture": report["fixture"]["summary"],
        "live_probe_count": live.get("listing_count", 0),
        "saved_html": report["saved_html"]["summary"],
        "four_source_smoke": smoke["status"],
        "wrote": [str(out), str(smoke_out)],
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    ok = (
        len(detailed) >= 20
        and report["fixture"]["summary"]["url_failures"] == 0
        and (
            report["fixture"]["summary"]["yahoo_selected"]
            + report["fixture"]["summary"]["mercari_selected"]
            >= 10
        )
        and smoke["status"] == "PASS"
        and all(row.get("acquisition_source") == "Vestiaire Collective" for row in detailed)
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
