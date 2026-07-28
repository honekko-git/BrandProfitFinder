"""Generate StockX internal standard fixtures (fictional data only)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def market_block(
    *,
    lowest_ask: int = 24500,
    highest_bid: int = 22800,
    last_sale: int = 23800,
    sales_72h: int = 6,
    sales_30d: int = 42,
    asks: int = 18,
    bids: int = 14,
    premium: float = 0.18,
    volatility: float = 0.07,
    lowest_known: bool = True,
    bid_known: bool = True,
    last_known: bool = True,
    currency: str = "JPY",
) -> dict:
    return {
        "lowest_ask": {
            "amount": lowest_ask if lowest_known else None,
            "currency": currency,
            "known": lowest_known,
        },
        "highest_bid": {
            "amount": highest_bid if bid_known else None,
            "currency": currency,
            "known": bid_known,
        },
        "last_sale": {
            "amount": last_sale if last_known else None,
            "currency": currency,
            "known": last_known,
        },
        "sales_last_72_hours": sales_72h,
        "sales_last_30_days": sales_30d,
        "asks_count": asks,
        "bids_count": bids,
        "price_premium_rate": premium,
        "volatility_rate": volatility,
    }


def base_item(
    listing_id: str = "stockx-demo-001",
    *,
    title: str = "NIKE Dunk Low Black White",
    price: int = 24500,
    size: str = "US 9",
    size_system: str = "US_MEN",
    condition_raw: str = "New",
    sale_status: str = "ACTIVE",
    inventory_status: str = "AVAILABLE",
    product_id: str = "stockx-product-demo-001",
    variant_id: str = "stockx-variant-demo-001",
    style_code: str = "DD1391-100",
    currency: str = "JPY",
    price_source: str = "LOWEST_ASK",
    shipping_known: bool = False,
    fees_known: bool = False,
    market: dict | None = None,
    **overrides,
) -> dict:
    item = {
        "listing_id": listing_id,
        "product_id": product_id,
        "variant_id": variant_id,
        "title": title,
        "description": "Internal fixture for marketplace foundation demo.",
        "brand": "NIKE",
        "model_number": "DD1391-100",
        "style_code": style_code,
        "sku": "INTERNAL-DEMO-SKU-001",
        "jan": None,
        "category": "sneakers",
        "sub_category": "low_top",
        "color": "black white",
        "size": size,
        "size_system": size_system,
        "gender": "men",
        "release_year": 2021,
        "release_date": "2021-03-10",
        "condition": {"raw": condition_raw, "description": f"{condition_raw} marketplace item"},
        "price": {"amount": price, "currency": currency, "source": price_source},
        "shipping": {"amount": None, "currency": currency, "known": shipping_known},
        "fees": {"amount": None, "currency": currency, "known": fees_known},
        "market": market if market is not None else market_block(),
        "inventory": {"status": inventory_status, "quantity": None},
        "sale_status": sale_status,
        "authentication": {
            "status": "PLATFORM_PROCESS",
            "seller_claimed_authentic": None,
            "platform_authenticated": None,
            "third_party_authenticated": False,
        },
        "url": f"https://example.invalid/stockx/{listing_id}",
        "image_url": f"https://example.invalid/images/{listing_id}.jpg",
        "listed_at": "2026-07-28T10:00:00Z",
        "metadata": {"source_format": "brandprofitfinder_internal_fixture"},
    }
    item.update(overrides)
    return item


def wrap(items: list, *, page: int = 1, total: int | None = None) -> dict:
    return {
        "marketplace": "stockx",
        "query": "Nike Dunk Low Panda",
        "page": page,
        "page_size": 20,
        "total": total if total is not None else len(items),
        "items": items,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    demo_items = [
        base_item("stockx-demo-001"),
        base_item(
            "stockx-demo-002",
            title="ADIDAS Samba OG White Black",
            brand="ADIDAS",
            model_number="B75806",
            style_code="B75806",
            size="US 10",
            price=18200,
            product_id="stockx-product-demo-002",
            variant_id="stockx-variant-demo-002",
        ),
        base_item(
            "stockx-demo-003",
            title="NEW BALANCE 550 White Green",
            brand="NEW BALANCE",
            model_number="BB550WT1",
            style_code="BB550WT1",
            size="US 8.5",
            price=16800,
            product_id="stockx-product-demo-003",
            variant_id="stockx-variant-demo-003",
        ),
    ]
    for i, it in enumerate(demo_items):
        if i == 1:
            it["brand"] = "ADIDAS"
        if i == 2:
            it["brand"] = "NEW BALANCE"

    fixtures = {
        "stockx_search_normal.json": wrap(demo_items, total=3),
        "stockx_search_multiple.json": wrap(demo_items, total=3),
        "stockx_search_empty.json": wrap([]),
        "stockx_search_missing_fields.json": wrap(
            [{"listing_id": "stockx-missing-001", "title": "Incomplete Sneaker"}]
        ),
        "stockx_search_malformed.json": {"marketplace": "stockx", "items": "bad"},
        "stockx_search_duplicate.json": wrap(
            [base_item("stockx-dup-001"), base_item("stockx-dup-001")]
        ),
        "stockx_search_unknown_condition.json": wrap(
            [base_item("stockx-cond-unknown", condition_raw="Unknown")]
        ),
        "stockx_search_non_jpy.json": wrap(
            [
                base_item(
                    "stockx-usd-001",
                    currency="USD",
                    price=180,
                    market=market_block(lowest_known=False, currency="USD"),
                )
            ]
        ),
        "stockx_search_shipping_unknown.json": wrap([base_item("stockx-ship-unknown")]),
        "stockx_search_fees_unknown.json": wrap([base_item("stockx-fees-unknown")]),
        "stockx_search_fees_invalid.json": wrap(
            [base_item("stockx-fees-bad", fees={"amount": True, "currency": "JPY", "known": False})]
        ),
        "stockx_search_lowest_ask_unknown.json": wrap(
            [
                base_item(
                    "stockx-ask-unknown",
                    market=market_block(lowest_known=False, lowest_ask=0),
                )
            ]
        ),
        "stockx_search_highest_bid_unknown.json": wrap(
            [base_item("stockx-bid-unknown", market=market_block(bid_known=False))]
        ),
        "stockx_search_last_sale_unknown.json": wrap(
            [base_item("stockx-last-unknown", market=market_block(last_known=False))]
        ),
        "stockx_search_market_invalid.json": wrap(
            [base_item("stockx-market-bad", market={"lowest_ask": {"amount": -100, "known": True}})]
        ),
        "stockx_search_market_counts_invalid.json": wrap(
            [base_item("stockx-counts-bad", market={**market_block(), "asks_count": True})]
        ),
        "stockx_search_premium_invalid.json": wrap(
            [base_item("stockx-premium-bad", market={**market_block(), "price_premium_rate": -0.2})]
        ),
        "stockx_search_volatility_invalid.json": wrap(
            [base_item("stockx-vol-bad", market={**market_block(), "volatility_rate": -0.1})]
        ),
        "stockx_search_low_liquidity.json": wrap(
            [base_item("stockx-low-liq", market=market_block(sales_30d=2, asks=1, bids=1))]
        ),
        "stockx_search_high_volatility.json": wrap(
            [base_item("stockx-high-vol", market=market_block(volatility=0.45))]
        ),
        "stockx_search_sold.json": wrap(
            [base_item("stockx-sold", sale_status="SOLD", inventory_status="SOLD_OUT")]
        ),
        "stockx_search_unavailable.json": wrap(
            [base_item("stockx-unavail", inventory_status="UNAVAILABLE", sale_status="INACTIVE")]
        ),
        "stockx_search_inactive.json": wrap(
            [base_item("stockx-inactive", sale_status="INACTIVE")]
        ),
        "stockx_search_inventory_invalid.json": wrap(
            [base_item("stockx-inv-bad", inventory={"status": "AVAILABLE", "quantity": True})]
        ),
        "stockx_search_product_id_missing.json": wrap([base_item("stockx-no-prod", product_id="")]),
        "stockx_search_variant_id_missing.json": wrap([base_item("stockx-no-var", variant_id="")]),
        "stockx_search_style_code_missing.json": wrap([base_item("stockx-no-style", style_code="")]),
        "stockx_search_size_missing.json": wrap([base_item("stockx-no-size", size="")]),
        "stockx_search_size_system_unknown.json": wrap(
            [base_item("stockx-size-sys", size_system="")]
        ),
        "stockx_search_size_mismatch.json": wrap(
            [base_item("stockx-size-a", size="US 9"), base_item("stockx-size-b", size="US 11")]
        ),
        "stockx_search_release_year_invalid.json": wrap(
            [base_item("stockx-year-bad", release_year="nineteen")]
        ),
        "stockx_search_release_date_invalid.json": wrap(
            [base_item("stockx-date-bad", release_date="03/10/2021")]
        ),
        "stockx_search_deadstock.json": wrap([base_item("stockx-deadstock", condition_raw="Deadstock")]),
        "stockx_search_new_without_box.json": wrap(
            [base_item("stockx-nobox", condition_raw="New without Box")]
        ),
        "stockx_search_new_with_defects.json": wrap(
            [base_item("stockx-defects", condition_raw="New with Defects")]
        ),
        "stockx_search_preowned.json": wrap([base_item("stockx-preowned", condition_raw="Pre-Owned")]),
        "stockx_search_refurbished.json": wrap(
            [base_item("stockx-refurb", condition_raw="Refurbished")]
        ),
        "stockx_search_damaged.json": wrap([base_item("stockx-damaged", condition_raw="Damaged")]),
        "stockx_search_for_parts.json": wrap([base_item("stockx-parts", condition_raw="For Parts")]),
        "stockx_search_authentication_unknown.json": wrap(
            [
                base_item(
                    "stockx-auth-unknown",
                    authentication={"status": "UNKNOWN", "platform_authenticated": None},
                )
            ]
        ),
        "stockx_search_page_1.json": wrap(
            [base_item("stockx-page1-a"), base_item("stockx-page1-b")],
            page=1,
            total=3,
        ),
        "stockx_search_page_2.json": wrap([base_item("stockx-page2-a")], page=2, total=3),
    }

    for name, payload in fixtures.items():
        path = OUT / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
