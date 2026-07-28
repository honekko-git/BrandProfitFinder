"""Generate Farfetch internal standard fixtures (fictional data only)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def base_item(
    listing_id: str = "farfetch-demo-001",
    *,
    title: str = "GUCCI GG Marmont Small Shoulder Bag",
    price: int = 298000,
    original_price: int | None = 330000,
    condition_raw: str = "New",
    sale_status: str = "ACTIVE",
    inventory_status: str = "IN_STOCK",
    low_stock: bool = False,
    boutique_type: str = "PARTNER_BOUTIQUE",
    discount_active: bool = True,
    product_id: str = "farfetch-product-demo-001",
    variant_id: str = "farfetch-variant-demo-001",
    style_code: str = "447632-DTD1T-1000",
    jan: str | None = None,
    currency: str = "JPY",
    shipping_known: bool = False,
    shipping_amount: int | None = None,
    duties_known: bool = False,
    duties_included: bool | None = None,
    duties_amount: int | None = None,
    final_sale: bool = False,
    return_accepted: bool = True,
    return_period_days: int = 14,
    variants: list | None = None,
    **overrides,
) -> dict:
    item = {
        "listing_id": listing_id,
        "product_id": product_id,
        "variant_id": variant_id,
        "title": title,
        "description": "New season shoulder bag in black leather.",
        "price": {"amount": price, "currency": currency},
        "original_price": {
            "amount": original_price,
            "currency": currency,
            "known": original_price is not None,
        }
        if original_price is not None
        else {"amount": None, "currency": currency, "known": False},
        "shipping": {
            "amount": shipping_amount,
            "currency": currency,
            "known": shipping_known,
        },
        "duties": {
            "included": duties_included,
            "amount": duties_amount,
            "currency": currency,
            "known": duties_known,
        },
        "url": f"https://example.invalid/farfetch/{listing_id}",
        "image_url": f"https://example.invalid/images/{listing_id}.jpg",
        "brand": "GUCCI",
        "designer": "GUCCI",
        "model_number": "447632",
        "style_code": style_code,
        "jan": jan,
        "category": "bags",
        "sub_category": "shoulder_bags",
        "color": "black",
        "size": "ONE SIZE",
        "material": "leather",
        "gender": "women",
        "season": "2026",
        "collection": "new_season",
        "condition": {"raw": condition_raw, "description": f"{condition_raw} retail item"},
        "boutique": {
            "type": boutique_type,
            "name": None,
            "country": "IT",
            "verified": None,
        },
        "inventory": {
            "status": inventory_status,
            "quantity": 1,
            "low_stock": low_stock,
        },
        "variants": variants
        if variants is not None
        else [
            {
                "variant_id": variant_id,
                "size": "ONE SIZE",
                "color": "black",
                "sku": "INTERNAL-DEMO-SKU-001",
                "available": True,
                "quantity": 1,
                "price": {"amount": price, "currency": currency},
            }
        ],
        "discount": {
            "active": discount_active,
            "amount": (original_price - price) if original_price and discount_active else 0,
            "rate": round((original_price - price) / original_price, 4)
            if original_price and discount_active and original_price > 0
            else 0.0,
            "previous_price": original_price,
        },
        "return_policy": {
            "accepted": return_accepted,
            "period_days": return_period_days,
            "final_sale": final_sale,
        },
        "sale_status": sale_status,
        "listed_at": "2026-07-25T10:00:00Z",
        "metadata": {"source_format": "brandprofitfinder_internal_fixture"},
    }
    item.update(overrides)
    return item


def wrap(items: list, *, page: int = 1, total: int | None = None) -> dict:
    return {
        "marketplace": "farfetch",
        "query": "Gucci GG Marmont Small Bag",
        "page": page,
        "page_size": 20,
        "total": total if total is not None else len(items),
        "items": items,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    normal_items = [
        base_item("farfetch-demo-001"),
        base_item(
            "farfetch-demo-002",
            title="PRADA Re-Edition 2005 Nylon Bag",
            brand="PRADA",
            price=185000,
            original_price=None,
            discount_active=False,
            product_id="farfetch-product-demo-002",
            variant_id="farfetch-variant-demo-002",
            style_code="1BH204-2CE9-F0002",
            model_number="1BH204",
            color="black",
            boutique_type="PLATFORM_INVENTORY",
        ),
        base_item(
            "farfetch-demo-003",
            title="SAINT LAURENT Loulou Small Bag",
            brand="SAINT LAURENT",
            price=245000,
            original_price=260000,
            product_id="farfetch-product-demo-003",
            variant_id="farfetch-variant-demo-003",
            style_code="577475-1EL07-1000",
            model_number="577475",
            color="black",
        ),
    ]
    for i, it in enumerate(normal_items):
        if i == 1:
            it["brand"] = "PRADA"
            it["designer"] = "PRADA"
        if i == 2:
            it["brand"] = "SAINT LAURENT"
            it["designer"] = "SAINT LAURENT"

    fixtures = {
        "farfetch_search_normal.json": wrap([normal_items[0]]),
        "farfetch_search_multiple.json": wrap(normal_items, total=3),
        "farfetch_search_empty.json": wrap([]),
        "farfetch_search_missing_fields.json": wrap(
            [{"listing_id": "farfetch-missing-001", "title": "Incomplete Item"}]
        ),
        "farfetch_search_malformed.json": {"marketplace": "farfetch", "items": "bad"},
        "farfetch_search_duplicate.json": wrap(
            [base_item("farfetch-dup-001"), base_item("farfetch-dup-001")]
        ),
        "farfetch_search_unknown_condition.json": wrap(
            [base_item("farfetch-cond-unknown", condition_raw="Unknown")]
        ),
        "farfetch_search_non_jpy.json": wrap(
            [base_item("farfetch-usd-001", currency="USD", price=2100, original_price=2400)]
        ),
        "farfetch_search_shipping_unknown.json": wrap(
            [base_item("farfetch-ship-unknown", shipping_known=False)]
        ),
        "farfetch_search_duties_unknown.json": wrap(
            [base_item("farfetch-duties-unknown", duties_known=False)]
        ),
        "farfetch_search_duties_included.json": wrap(
            [
                base_item(
                    "farfetch-duties-incl",
                    duties_known=True,
                    duties_included=True,
                    duties_amount=None,
                )
            ]
        ),
        "farfetch_search_duties_invalid.json": wrap(
            [
                base_item(
                    "farfetch-duties-bad",
                    duties={"included": "yes", "amount": True, "currency": "JPY", "known": False},
                )
            ]
        ),
        "farfetch_search_sold.json": wrap(
            [base_item("farfetch-sold", sale_status="SOLD", inventory_status="SOLD")]
        ),
        "farfetch_search_reserved.json": wrap(
            [base_item("farfetch-reserved", sale_status="RESERVED", inventory_status="RESERVED")]
        ),
        "farfetch_search_unavailable.json": wrap(
            [
                base_item(
                    "farfetch-unavail",
                    sale_status="INACTIVE",
                    inventory_status="UNAVAILABLE",
                )
            ]
        ),
        "farfetch_search_low_stock.json": wrap(
            [base_item("farfetch-low", inventory_status="LOW_STOCK", low_stock=True)]
        ),
        "farfetch_search_discounted.json": wrap(
            [base_item("farfetch-disc", discount_active=True, original_price=330000)]
        ),
        "farfetch_search_full_price.json": wrap(
            [
                base_item(
                    "farfetch-full",
                    discount_active=False,
                    original_price=None,
                    price=298000,
                )
            ]
        ),
        "farfetch_search_discount_inconsistent.json": wrap(
            [
                base_item(
                    "farfetch-disc-bad",
                    discount={
                        "active": True,
                        "amount": 50000,
                        "rate": 0.01,
                        "previous_price": 330000,
                    },
                )
            ]
        ),
        "farfetch_search_original_price_invalid.json": wrap(
            [
                {
                    **base_item("farfetch-orig-bad", price=298000),
                    "original_price": {"amount": 100000, "currency": "JPY", "known": True},
                }
            ]
        ),
        "farfetch_search_inventory_invalid.json": wrap(
            [
                base_item(
                    "farfetch-inv-bad",
                    inventory={"status": "IN_STOCK", "quantity": True, "low_stock": "maybe"},
                )
            ]
        ),
        "farfetch_search_variant_normal.json": wrap([base_item("farfetch-var-norm")]),
        "farfetch_search_variant_multiple.json": wrap(
            [
                base_item(
                    "farfetch-var-multi",
                    variants=[
                        {
                            "variant_id": "farfetch-variant-a",
                            "size": "38",
                            "color": "black",
                            "sku": "INTERNAL-DEMO-SKU-A",
                            "available": True,
                            "quantity": 2,
                            "price": {"amount": 298000, "currency": "JPY"},
                        },
                        {
                            "variant_id": "farfetch-variant-b",
                            "size": "40",
                            "color": "black",
                            "sku": "INTERNAL-DEMO-SKU-B",
                            "available": True,
                            "quantity": 1,
                            "price": {"amount": 298000, "currency": "JPY"},
                        },
                    ],
                )
            ]
        ),
        "farfetch_search_variant_unavailable.json": wrap(
            [
                base_item(
                    "farfetch-var-unavail",
                    variants=[
                        {
                            "variant_id": "farfetch-variant-u",
                            "size": "ONE SIZE",
                            "color": "black",
                            "sku": "INTERNAL-DEMO-SKU-U",
                            "available": False,
                            "quantity": 0,
                            "price": {"amount": 298000, "currency": "JPY"},
                        }
                    ],
                )
            ]
        ),
        "farfetch_search_variant_invalid.json": wrap(
            [base_item("farfetch-var-bad", variants="not-a-list")],
        ),
        "farfetch_search_variant_price_invalid.json": wrap(
            [
                base_item(
                    "farfetch-var-price-bad",
                    variants=[
                        {
                            "variant_id": "farfetch-variant-p",
                            "size": "ONE SIZE",
                            "color": "black",
                            "sku": "INTERNAL-DEMO-SKU-P",
                            "available": True,
                            "quantity": 1,
                            "price": {"amount": -100, "currency": "JPY"},
                        }
                    ],
                )
            ]
        ),
        "farfetch_search_product_id_missing.json": wrap(
            [base_item("farfetch-no-prod", product_id="")]
        ),
        "farfetch_search_variant_id_missing.json": wrap(
            [base_item("farfetch-no-var", variant_id="")]
        ),
        "farfetch_search_style_code_missing.json": wrap(
            [base_item("farfetch-no-style", style_code="")]
        ),
        "farfetch_search_partner_boutique.json": wrap(
            [base_item("farfetch-partner", boutique_type="PARTNER_BOUTIQUE")]
        ),
        "farfetch_search_platform_inventory.json": wrap(
            [base_item("farfetch-platform", boutique_type="PLATFORM_INVENTORY")]
        ),
        "farfetch_search_boutique_invalid.json": wrap(
            [
                base_item(
                    "farfetch-boutique-bad",
                    boutique={"type": "INVALID", "country": "it", "verified": "yes"},
                )
            ]
        ),
        "farfetch_search_final_sale.json": wrap(
            [base_item("farfetch-final", final_sale=True, return_accepted=True)]
        ),
        "farfetch_search_return_policy_invalid.json": wrap(
            [
                base_item(
                    "farfetch-return-bad",
                    return_policy={"accepted": "maybe", "period_days": True, "final_sale": None},
                )
            ]
        ),
        "farfetch_search_display_item.json": wrap(
            [base_item("farfetch-display", condition_raw="Display Item")]
        ),
        "farfetch_search_shop_worn.json": wrap(
            [base_item("farfetch-shop-worn", condition_raw="Shop Worn")]
        ),
        "farfetch_search_preowned.json": wrap(
            [base_item("farfetch-preowned", condition_raw="Pre-Owned")]
        ),
        "farfetch_search_page_1.json": wrap(
            [base_item("farfetch-page1-a"), base_item("farfetch-page1-b")],
            page=1,
            total=3,
        ),
        "farfetch_search_page_2.json": wrap(
            [base_item("farfetch-page2-a")],
            page=2,
            total=3,
        ),
    }

    for name, payload in fixtures.items():
        path = OUT / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {name}")

    # Demo uses normal with 3 items via multiple; update normal to single for parser tests
    # and set demo path in settings to multiple - keep as spec: demo_fixture_path = normal
    # Put 3 items in normal for demo CLI
    demo_path = OUT / "farfetch_search_normal.json"
    demo_path.write_text(
        json.dumps(wrap(normal_items, total=3), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("updated farfetch_search_normal.json with 3 demo items")


if __name__ == "__main__":
    main()
