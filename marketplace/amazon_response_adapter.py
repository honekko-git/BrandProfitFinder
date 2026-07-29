"""
Convert Amazon PA-API 5.0 raw responses into the internal standard JSON contract.
"""

from __future__ import annotations

import logging
from typing import Any

from marketplace.amazon_exceptions import AmazonResponseParseError

logger = logging.getLogger(__name__)


def adapt_amazon_search_response(raw: dict[str, Any]) -> dict[str, object]:
    """
    Adapt a raw Amazon SearchItems response to the internal parser contract.

    Args:
        raw: Parsed JSON from Amazon Product Advertising API.

    Returns:
        Internal standard payload with items, total_results, next_page_token.

    Raises:
        AmazonResponseParseError: When the payload structure is invalid.
    """
    if not isinstance(raw, dict):
        raise AmazonResponseParseError("Amazon API response must be a JSON object")

    if "items" in raw and isinstance(raw.get("items"), list):
        return _normalize_internal_payload(raw)

    errors = raw.get("Errors")
    if isinstance(errors, list) and errors:
        message = _format_api_errors(errors)
        raise AmazonResponseParseError(message)

    search_result = raw.get("SearchResult")
    if not isinstance(search_result, dict):
        raise AmazonResponseParseError("Amazon API response missing SearchResult")

    items_raw = search_result.get("Items")
    items: list[dict[str, object]] = []
    if isinstance(items_raw, list):
        for item in items_raw:
            if isinstance(item, dict):
                adapted = _adapt_item(item)
                if adapted is not None:
                    items.append(adapted)

    total_results = search_result.get("TotalResultCount")
    parsed_total = total_results if isinstance(total_results, int) and total_results >= 0 else len(items)
    next_page_token = _extract_next_page_token(search_result)

    return {
        "items": items,
        "total_results": parsed_total,
        "next_page_token": next_page_token,
    }


def _normalize_internal_payload(raw: dict[str, Any]) -> dict[str, object]:
    items = raw.get("items")
    if not isinstance(items, list):
        raise AmazonResponseParseError("Amazon items must be a list when present")
    total_results = raw.get("total_results")
    parsed_total = total_results if isinstance(total_results, int) and total_results >= 0 else len(items)
    token = raw.get("next_page_token")
    next_page_token = str(token) if token else None
    return {
        "items": items,
        "total_results": parsed_total,
        "next_page_token": next_page_token,
    }


def _adapt_item(item: dict[str, Any]) -> dict[str, object] | None:
    asin = str(item.get("ASIN") or item.get("asin") or "").strip()
    if not asin:
        logger.warning("Skipping Amazon item without ASIN")
        return None

    title = _display_value(item.get("ItemInfo", {}).get("Title")) if isinstance(item.get("ItemInfo"), dict) else ""
    if not title:
        title = str(item.get("title") or "").strip()

    brand = ""
    item_info = item.get("ItemInfo")
    if isinstance(item_info, dict):
        by_line = item_info.get("ByLineInfo")
        if isinstance(by_line, dict):
            brand = _display_value(by_line.get("Brand"))

    model_number = ""
    if isinstance(item_info, dict):
        manufacture = item_info.get("ManufactureInfo")
        if isinstance(manufacture, dict):
            model_number = _display_value(manufacture.get("Model"))

    jan_code = _extract_jan(item_info if isinstance(item_info, dict) else None)

    detail_page_url = str(item.get("DetailPageURL") or item.get("detail_page_url") or "").strip()
    image_url = _extract_image_url(item)

    price_amount, currency, shipping, is_prime, seller_name, is_amazon_seller, condition, availability = _extract_offer(
        item.get("Offers")
    )

    adapted: dict[str, object] = {
        "asin": asin,
        "title": title or asin,
        "brand": brand,
        "model_number": model_number,
        "jan_code": jan_code,
        "detail_page_url": detail_page_url,
        "image_url": image_url,
        "price": {"amount": price_amount, "currency": currency},
        "shipping": shipping,
        "seller": {"name": seller_name, "is_amazon": is_amazon_seller},
        "condition": condition,
        "availability": availability,
        "is_prime": is_prime,
    }
    return adapted


def _extract_offer(offers: Any) -> tuple[int | None, str, dict[str, object], bool, str, bool, str, str]:
    if not isinstance(offers, dict):
        return None, "JPY", {"amount": 0, "is_free": True}, False, "", False, "NEW", "IN_STOCK"

    listings = offers.get("Listings")
    if not isinstance(listings, list) or not listings:
        summaries = offers.get("Summaries")
        listing = summaries[0] if isinstance(summaries, list) and summaries else {}
    else:
        listing = listings[0] if isinstance(listings[0], dict) else {}

    price_data = listing.get("Price") if isinstance(listing, dict) else None
    amount: int | None = None
    currency = "JPY"
    if isinstance(price_data, dict):
        raw_amount = price_data.get("Amount")
        if isinstance(raw_amount, (int, float)):
            amount = int(raw_amount)
        currency = str(price_data.get("Currency") or "JPY").strip().upper() or "JPY"

    delivery = listing.get("DeliveryInfo") if isinstance(listing, dict) else None
    is_prime = isinstance(delivery, dict) and delivery.get("IsPrimeEligible") is True

    merchant = listing.get("MerchantInfo") if isinstance(listing, dict) else None
    seller_name = ""
    is_amazon_seller = False
    if isinstance(merchant, dict):
        seller_name = str(merchant.get("Name") or "").strip()
        is_amazon_seller = merchant.get("IsAmazonFulfilled") is True or seller_name.lower().startswith("amazon")

    condition = "NEW"
    condition_data = listing.get("Condition") if isinstance(listing, dict) else None
    if isinstance(condition_data, dict):
        value = str(condition_data.get("Value") or "New").strip().upper()
        condition = value if value else "NEW"

    availability = "IN_STOCK"
    availability_data = listing.get("Availability") if isinstance(listing, dict) else None
    if isinstance(availability_data, dict):
        availability = str(availability_data.get("Type") or "IN_STOCK").strip().upper()

    shipping: dict[str, object] = {"amount": 0, "is_free": True}
    return amount, currency, shipping, is_prime, seller_name, is_amazon_seller, condition, availability


def _extract_image_url(item: dict[str, Any]) -> str:
    images = item.get("Images")
    if isinstance(images, dict):
        primary = images.get("Primary")
        if isinstance(primary, dict):
            for size in ("Medium", "Large", "Small"):
                sized = primary.get(size)
                if isinstance(sized, dict):
                    url = str(sized.get("URL") or "").strip()
                    if url:
                        return url
    return str(item.get("image_url") or "").strip()


def _extract_jan(item_info: dict[str, Any] | None) -> str:
    if not item_info:
        return ""
    external_ids = item_info.get("ExternalIds")
    if not isinstance(external_ids, dict):
        return ""
    eans = external_ids.get("EANs")
    if isinstance(eans, dict):
        values = eans.get("DisplayValues")
        if isinstance(values, list) and values:
            return str(values[0]).strip()
    return ""


def _extract_next_page_token(search_result: dict[str, Any]) -> str | None:
    token = search_result.get("next_page_token") or search_result.get("NextPageToken")
    if token:
        return str(token)
    page = search_result.get("ItemPage")
    if isinstance(page, int) and page > 0:
        return str(page + 1)
    return None


def _display_value(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("DisplayValue") or node.get("Label") or "").strip()
    if isinstance(node, str):
        return node.strip()
    return ""


def _format_api_errors(errors: list[Any]) -> str:
    messages: list[str] = []
    for error in errors:
        if isinstance(error, dict):
            code = str(error.get("Code") or "").strip()
            message = str(error.get("Message") or "").strip()
            if code and message:
                messages.append(f"{code}: {message}")
            elif message:
                messages.append(message)
    return "; ".join(messages) if messages else "Amazon API returned errors"
