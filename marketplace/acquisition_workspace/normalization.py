"""Candidate normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from marketplace.browser_acquisition.comparable_matching import detect_model_tokens
from marketplace.browser_acquisition.listing_identity import (
    extract_listing_identity,
    normalize_color as normalize_identity_color,
    normalize_hardware,
)
from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.product_subtype import detect_wallet_subtype
from profit_discovery.discovery_validation.batch_profit.condition import detect_condition
from profit_discovery.discovery_validation.real_profit_config import resolve_currency_jpy_exchange_rate

BRAND_ALIASES = {
    "chanel": "Chanel",
    "シャネル": "Chanel",
    "louis vuitton": "Louis Vuitton",
    "lv": "Louis Vuitton",
    "ルイヴィトン": "Louis Vuitton",
    "ヴィトン": "Louis Vuitton",
}

# Non-bag categories checked first so jewelry/shoes/etc. never collapse to Bag.
NON_BAG_CATEGORY_ALIASES = {
    "jewelry": "Jewelry",
    "jewellery": "Jewelry",
    "earring": "Jewelry",
    "earrings": "Jewelry",
    "bracelet": "Jewelry",
    "necklace": "Jewelry",
    "ring": "Jewelry",
    "jewel": "Jewelry",
    "shoe": "Shoes",
    "shoes": "Shoes",
    "sneaker": "Shoes",
    "mule": "Shoes",
    "boot": "Shoes",
    "sandal": "Shoes",
    "heel": "Shoes",
    "clothing": "Clothing",
    "sweater": "Clothing",
    "dress": "Clothing",
    "shirt": "Clothing",
    "jacket": "Clothing",
    "coat": "Clothing",
    "pants": "Clothing",
    "watch": "Watch",
    "watches": "Watch",
}

WALLET_CATEGORY_ALIASES = {
    "wallet": "Wallet",
    "財布": "Wallet",
    "ウォレット": "Wallet",
}

# Handbag labels canonicalize to Bag (eligibility uses Bag only).
BAG_CATEGORY_ALIASES = {
    "handbag": "Bag",
    "tote bag": "Bag",
    "shoulder bag": "Bag",
    "crossbody bag": "Bag",
    "flap bag": "Bag",
    "top handle bag": "Bag",
    "boston bag": "Bag",
    "バッグ": "Bag",
    "ハンドバッグ": "Bag",
    "トートバッグ": "Bag",
    "ショルダーバッグ": "Bag",
    "bag": "Bag",
}

CATEGORY_ALIASES = {
    **NON_BAG_CATEGORY_ALIASES,
    **WALLET_CATEGORY_ALIASES,
    **BAG_CATEGORY_ALIASES,
}

SUPPORTED_CURRENCIES = {"USD", "JPY", "EUR", "GBP"}
NOISE_TOKENS = (
    "fashionphile",
    "rebag",
    "therealreal",
    "realreal",
    "vestiaire",
    "vestiairecollective",
    "vestiaire collective",
    "authenticated",
    "free shipping",
    "sale",
    "clearance",
    "investment piece",
    "we love",
)

TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}


def normalize_brand(value: str) -> str:
    raw = value.strip()
    if not raw:
        detected = ""
    else:
        key = raw.lower()
        detected = BRAND_ALIASES.get(key, raw)
    if not detected:
        for alias, canonical in BRAND_ALIASES.items():
            if alias in raw.lower():
                return canonical
    return detected


def normalize_category(value: str, *, title: str = "") -> str:
    """Normalize category to a canonical workspace value.

    Non-bag signals in the title still win over bag aliases so earrings,
    shoes, garments, and watches are never treated as Bag. A soft
    category-field label like ``Clothing`` does not override an explicit
    bag token in the title (e.g. ``… Bag …`` mis-tagged as Clothing).
    """
    category_text = (value or "").strip().lower()
    title_text = (title or "").strip().lower()
    title_has_bag = any(_token_match(alias, title_text) for alias in BAG_CATEGORY_ALIASES)

    for alias, canonical in sorted(NON_BAG_CATEGORY_ALIASES.items(), key=lambda item: -len(item[0])):
        in_category = _token_match(alias, category_text)
        in_title = _token_match(alias, title_text)
        if not in_category and not in_title:
            continue
        # Soft marketplace category "Clothing" must not beat title bag evidence.
        if canonical == "Clothing" and title_has_bag and in_category and not in_title:
            continue
        return canonical

    for alias, canonical in sorted(WALLET_CATEGORY_ALIASES.items(), key=lambda item: -len(item[0])):
        if _token_match(alias, category_text) or (not category_text and _token_match(alias, title_text)):
            return canonical

    # Prefer longer bag phrases before the generic "bag" token.
    for alias, canonical in sorted(BAG_CATEGORY_ALIASES.items(), key=lambda item: -len(item[0])):
        if _token_match(alias, category_text) or _token_match(alias, title_text):
            return canonical

    stripped = value.strip() if value else ""
    if stripped:
        return stripped
    return "Unknown"


def _token_match(alias: str, text: str) -> bool:
    """Substring match with word-ish boundaries for short English tokens.

    Prevents ``coat`` matching inside ``coated canvas`` while still matching
    plurals (``mule``→``mules``), Japanese aliases, and multi-word phrases.
    """
    if not alias or not text:
        return False
    if alias in text and not alias.isascii():
        return True
    if " " in alias:
        return alias in text
    if len(alias) <= 4 and alias.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}s?(?![a-z0-9])", text) is not None
    return alias in text



def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title)
    normalized = normalized.lower()
    for token in NOISE_TOKENS:
        normalized = normalized.replace(token, " ")
    normalized = re.sub(r"[^\w\s\u3040-\u30ff\u4e00-\u9fff-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_currency(value: str) -> str:
    return value.strip().upper()


def normalize_price(value: str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    cleaned = str(value).replace(",", "").replace("$", "").replace("¥", "").strip()
    return Decimal(cleaned)


def normalize_url(url: str) -> str:
    if not url.strip():
        return ""
    parsed = urlparse(url.strip())
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key not in TRACKING_QUERY_KEYS]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), hostname, path, "", urlencode(query), ""))


def detect_brand_from_title(title: str) -> str:
    lowered = title.lower()
    for alias, canonical in BRAND_ALIASES.items():
        if alias in lowered or alias in title:
            return canonical
    return ""


def detect_color(title: str) -> str:
    canonical = normalize_identity_color(title)
    if canonical:
        return canonical.lower()
    return ""


def build_detection_fields(*, title: str, brand: str, category: str, condition: str) -> dict[str, object]:
    detected_brand = normalize_brand(brand) or detect_brand_from_title(title)
    detected_category = normalize_category(category, title=title)
    combined = f"{title} {condition}".strip()
    identity = extract_listing_identity(
        title=title,
        brand=detected_brand,
        category=detected_category,
        condition=condition,
        model_family_tokens=detect_model_tokens(title),
    )
    return {
        "brand": detected_brand,
        "category": detected_category,
        "detected_subtype": detect_wallet_subtype(title).value,
        "detected_material": detect_luxury_material(title).value,
        "detected_model_tokens": detect_model_tokens(title),
        "detected_color": detect_color(title),
        "detected_condition": detect_condition(combined).value,
        # Normalized identity for Yahoo comparable matching / future auction search
        "identity_brand": identity.brand,
        "identity_category": identity.category,
        "identity_material": identity.material,
        "identity_color": identity.color,
        "identity_hardware": identity.hardware or normalize_hardware(title),
        "identity_condition": identity.condition,
        "identity_model_numbers": identity.model_numbers,
        "identity_cleaned_title": identity.cleaned_title,
    }


def purchase_price_jpy(price: Decimal, currency: str) -> Decimal:
    """Convert purchase price to JPY via the shared FX resolver (not USD-only)."""
    code = normalize_currency(currency)
    rate = Decimal(str(resolve_currency_jpy_exchange_rate(code)))
    return price * rate


def is_supported_currency(currency: str) -> bool:
    return normalize_currency(currency) in SUPPORTED_CURRENCIES


def is_valid_price(price: Decimal) -> bool:
    try:
        return price > 0
    except InvalidOperation:
        return False
