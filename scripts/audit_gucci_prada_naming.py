"""Live naming-pattern audit for Gucci Dionysus and Prada Re-Edition.

Fetches real Yahoo/Mercari results via production acquirers and classifies
each sample for dictionary expansion (group A only).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from marketplace.browser_acquisition.bag_model_family import extract_handbag_model_identity
from marketplace.browser_acquisition.comparable_matching import evaluate_comparables
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.mercari_acquirer import MercariAcquirer
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer

OUT = Path("output/gucci_prada_naming_audit.json")

TARGETS = (
    {
        "brand": "Gucci",
        "family": "Dionysus",
        "title": "Gucci Dionysus Handbag GG Supreme",
        "category": "Bag",
    },
    {
        "brand": "Prada",
        "family": "Re-Edition",
        "title": "Prada Re-Edition 2005 Nylon Bag",
        "category": "Bag",
    },
)


def _purchase(title: str, brand: str, category: str) -> AcquiredListing:
    return AcquiredListing(
        external_id="audit",
        title=title,
        brand=brand,
        category=category,
        condition="UNKNOWN",
        price=Decimal("1500"),
        currency="USD",
        url="https://example.com/p",
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        source="Audit",
        raw_title=title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _classify(purchase_family: str, sample_family: str, reasons: tuple[str, ...], title: str) -> str:
    t = title.lower()
    if sample_family == purchase_family:
        if any(r == "SCORE_BELOW_THRESHOLD" for r in reasons):
            return "A_same_family_score_miss"
        return "A_same_family_other"
    if sample_family and sample_family != purchase_family:
        return "B_different_family"
    # Heuristic hints for audit notes only (not used for matching).
    if purchase_family == "Dionysus":
        if any(x in title for x in ("マーモント", "jackie", "ジャッキー", "オフィディア", "バンブー")):
            return "B_related_other_gucci"
        if "タイガー" in title or "tiger" in t:
            return "A_candidate_tiger_head_compound"
        if "gg" in t or "ＧＧ" in title or "スプリーム" in title:
            return "C_generic_gg_or_insufficient"
    if purchase_family == "Re-Edition":
        if any(x in title for x in ("ガレリア", "クレオ", "galleria", "cleo")):
            return "B_different_family"
        if "1BH204" in title or "1bh204" in t or "2005" in title or "2000" in title:
            return "A_candidate_year_or_sku"
        if "ナイロン" in title or "tessuto" in t or "テスート" in title:
            return "C_generic_nylon_or_tessuto"
        if "三角" in title:
            return "C_generic_triangle"
    if not sample_family:
        return "C_generic_same_brand_or_unknown"
    return "D_irrelevant"


def audit_one(target: dict) -> dict:
    brand = target["brand"]
    title = target["title"]
    category = target["category"]
    family = target["family"]
    purchase = _purchase(title, brand, category)
    queries = build_yahoo_search_queries(title=title, brand=brand, category=category)
    print(f"[{brand}] queries={queries}", flush=True)

    yahoo = YahooSoldAcquirer()
    mercari = MercariAcquirer()
    y_samples, y_queries, _ = yahoo.acquire_multi(title=title, brand=brand, category=category, queries=queries)
    m_samples, m_queries = mercari.acquire_multi(title=title, brand=brand, category=category, queries=queries)

    rows = []
    for marketplace, samples in (("Yahoo", y_samples), ("Mercari", m_samples)):
        result = evaluate_comparables(purchase, list(samples), purchase_price_jpy=Decimal("250000"))
        by_title = {d.title: d for d in list(result.accepted_diagnostics) + list(result.rejected_diagnostics)}
        for sample in samples:
            diag = by_title.get(sample.title)
            identity = extract_handbag_model_identity(title=sample.title, brand=brand, category="Bag")
            listing = extract_listing_identity(title=sample.title, brand=brand, category="")
            material = detect_luxury_material(sample.title).value
            reasons = tuple(diag.rejection_reasons) if diag else ()
            group = _classify(family, identity.model_family, reasons, sample.title)
            rows.append(
                {
                    "marketplace": marketplace,
                    "title": sample.title,
                    "url": sample.url,
                    "sold_or_active": sample.auction_status,
                    "price_jpy": sample.sold_price_jpy,
                    "extracted_brand": listing.brand,
                    "extracted_model_family": identity.model_family,
                    "aliases_matched": list(identity.aliases_matched),
                    "material": material,
                    "category": listing.category,
                    "score": diag.matching_score if diag else None,
                    "accepted": bool(diag and diag.accepted),
                    "rejection_reasons": list(reasons),
                    "audit_group": group,
                }
            )

    accepted = [r for r in rows if r["accepted"]]
    group_a = [r for r in rows if r["audit_group"].startswith("A_")]
    return {
        "brand": brand,
        "family": family,
        "purchase_title": title,
        "queries_generated": queries,
        "queries_yahoo_executed": list(y_queries),
        "queries_mercari_executed": list(m_queries),
        "yahoo_raw": len(y_samples),
        "mercari_raw": len(m_samples),
        "accepted_count": len(accepted),
        "accepted": accepted,
        "group_a_candidates": group_a,
        "all_rows": rows,
        "group_counts": {
            k: sum(1 for r in rows if r["audit_group"] == k)
            for k in sorted({r["audit_group"] for r in rows})
        },
    }


def main() -> int:
    reports = [audit_one(t) for t in TARGETS]
    payload = {
        "started_at": datetime.now(tz=UTC).isoformat(),
        "reports": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)
    for r in reports:
        print(
            r["brand"],
            "accepted",
            r["accepted_count"],
            "groups",
            r["group_counts"],
            "queries_exec",
            len(r["queries_yahoo_executed"]),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
