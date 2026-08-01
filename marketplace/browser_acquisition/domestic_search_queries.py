"""Marketplace-neutral domestic search query generation contract.

Used by Yahoo Auctions and Mercari. Reuses ProductIdentity / ListingIdentity /
HandbagModelIdentity — does not re-extract with a second ad-hoc parser.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.product_identity import extract_product_identity

MAX_SEARCH_QUERIES = 4

# Tier labels (deterministic priority order).
TIER_REFERENCE_EXACT = "REFERENCE_EXACT"
TIER_REFERENCE_EXACT_EN = "REFERENCE_EXACT_EN"
TIER_COLLECTION_FAMILY_SIZE = "COLLECTION_FAMILY_SIZE"
TIER_COLLECTION_FAMILY_SIZE_EN = "COLLECTION_FAMILY_SIZE_EN"
TIER_COLLECTION_FAMILY_MATERIAL = "COLLECTION_FAMILY_MATERIAL"
TIER_COLLECTION_FAMILY_MATERIAL_EN = "COLLECTION_FAMILY_MATERIAL_EN"
TIER_COLLECTION_FAMILY_CATEGORY = "COLLECTION_FAMILY_CATEGORY"
TIER_COLLECTION_FAMILY_CATEGORY_EN = "COLLECTION_FAMILY_CATEGORY_EN"
TIER_DISTINCTIVE_MODEL = "DISTINCTIVE_MODEL"
TIER_DISTINCTIVE_MODEL_EN = "DISTINCTIVE_MODEL_EN"
TIER_CATEGORY_FALLBACK = "CATEGORY_FALLBACK"
TIER_CATEGORY_FALLBACK_EN = "CATEGORY_FALLBACK_EN"

STATUS_OK = "OK"
STATUS_OK_WITH_FALLBACK = "OK_WITH_CATEGORY_FALLBACK"
STATUS_NO_SAFE_QUERY = "NO_SAFE_QUERY"

REASON_OK = "IDENTITY_QUERIES_GENERATED"
REASON_FALLBACK = "STRONG_IDENTITY_MISSING_USED_CATEGORY_FALLBACK"
REASON_NO_SAFE = "REFERENCE_AND_MODEL_FAMILY_MISSING"

BRAND_JA = {
    "CHANEL": "シャネル",
    "LOUIS VUITTON": "ルイヴィトン",
    "HERMES": "エルメス",
    "GUCCI": "グッチ",
    "PRADA": "プラダ",
    "DIOR": "ディオール",
    "CELINE": "セリーヌ",
    "FENDI": "フェンディ",
    "BOTTEGA VENETA": "ボッテガ",
    "SAINT LAURENT": "サンローラン",
    "BALENCIAGA": "バレンシアガ",
}

CATEGORY_JA = {
    "WALLET": "財布",
    "LONG_WALLET": "長財布",
    "ZIP_WALLET": "ジップウォレット",
    "ROUND_ZIP": "ラウンドファスナー",
    "WALLET_ON_CHAIN": "チェーンウォレット",
    "SHOULDER_BAG": "ショルダーバッグ",
    "TOTE_BAG": "トートバッグ",
    "BACKPACK": "リュック",
    "BAG": "バッグ",
    "HANDBAG": "ハンドバッグ",
    "SUNGLASSES": "サングラス",
    "SHOES": "シューズ",
    "SANDALS": "サンダル",
    "HAT": "帽子",
    "CARD_HOLDER": "カードケース",
    "Wallet": "財布",
    "Bag": "バッグ",
    "Sunglasses": "サングラス",
}

COLOR_MAP = {
    "black": "黒",
    "white": "白",
    "beige": "ベージュ",
    "navy": "ネイビー",
    "red": "赤",
    "pink": "ピンク",
    "green": "グリーン",
    "blue": "ブルー",
    "gold": "ゴールド",
    "silver": "シルバー",
    "gray": "グレー",
    "grey": "グレー",
}

MATERIAL_MAP = {
    "caviar": "キャビアスキン",
    "lambskin": "ラムスキン",
    "leather": "レザー",
    "canvas": "キャンバス",
    "patent": "パテント",
    "quilted": "マトラッセ",
    "EPI": "エピ",
    "DAMIER": "ダミエ",
    "MONOGRAM": "モノグラム",
    "SAFFIANO": "サフィアーノ",
    "ACETATE": "アセテート",
    "NYLON": "ナイロン",
    "saffiano": "サフィアーノ",
    "acetate": "アセテート",
    "nylon": "ナイロン",
}


@dataclass(frozen=True, slots=True)
class GeneratedQuery:
    """One deterministic domestic search query with tier metadata."""

    query: str
    tier: str
    signals: tuple[str, ...]
    language: str = "ja"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QueryGenerationResult:
    """Full query-generation contract output for tracing and acquisition."""

    queries: tuple[GeneratedQuery, ...]
    status: str
    reason: str
    available_signals: tuple[str, ...]
    missing_signals: tuple[str, ...]
    dropped: tuple[dict[str, str], ...] = ()
    identity_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def query_strings(self) -> list[str]:
        return [item.query for item in self.queries]

    @property
    def has_strong_identity(self) -> bool:
        return any(
            signal in self.available_signals
            for signal in ("reference", "collection", "family", "model_number")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "available_signals": list(self.available_signals),
            "missing_signals": list(self.missing_signals),
            "queries": [item.to_dict() for item in self.queries],
            "dropped": list(self.dropped),
            "identity_snapshot": dict(self.identity_snapshot),
        }


def build_domestic_search_queries(
    *,
    title: str,
    brand: str = "",
    category: str = "",
    max_queries: int = MAX_SEARCH_QUERIES,
) -> QueryGenerationResult:
    """Build deterministic ordered domestic queries from existing identity objects."""
    from marketplace.browser_acquisition.bag_model_family import (
        build_bag_model_queries,
        extract_handbag_model_identity,
    )

    product = extract_product_identity(title=title, brand=brand, category=category)
    listing = extract_listing_identity(title=title, brand=brand, category=category)
    bag = extract_handbag_model_identity(title=title, brand=brand, category=category)

    brand_key = product.brand or listing.brand or (brand or "").strip().upper()
    ja_brand = BRAND_JA.get(brand_key, "")
    en_brand = brand_key.title() if brand_key else (brand or "").strip()
    # Prefer title-derived category so mislabeled candidate.category cannot force バッグ.
    effective_category = (
        product.category
        if product.category not in {"", "UNKNOWN"}
        else (listing.category if listing.category not in {"", "UNKNOWN"} else (category or ""))
    )
    cat_ja = CATEGORY_JA.get(effective_category, CATEGORY_JA.get(str(category), ""))
    material = product.material if product.material not in {"", "UNKNOWN", "OTHER"} else ""
    material_ja = MATERIAL_MAP.get(material, MATERIAL_MAP.get(material.upper(), ""))
    color = product.color or listing.color or ""
    color_ja = COLOR_MAP.get(str(color).lower(), "")
    size = product.size or ""

    available: list[str] = []
    missing: list[str] = []
    if product.reference_numbers or listing.model_numbers:
        available.append("reference" if product.reference_numbers else "model_number")
    else:
        missing.append("reference")
    if product.collection or bag.model_family:
        available.append("collection" if product.collection else "family")
    else:
        missing.append("collection")
    if product.family or bag.model_family:
        if "family" not in available and "collection" not in available:
            available.append("family")
    else:
        missing.append("family")
    if material:
        available.append("material")
    else:
        missing.append("material")
    if size:
        available.append("size")
    else:
        missing.append("size")
    if brand_key:
        available.append("brand")
    else:
        missing.append("brand")
    if effective_category and effective_category != "UNKNOWN":
        available.append("category")
    else:
        missing.append("category")

    candidates: list[GeneratedQuery] = []

    # Tier 1 — exact reference / SKU
    refs = tuple(dict.fromkeys([*product.reference_numbers, *listing.model_numbers]))[:2]
    for ref in refs:
        if ja_brand:
            candidates.append(
                GeneratedQuery(
                    query=f"{ja_brand} {ref}",
                    tier=TIER_REFERENCE_EXACT,
                    signals=("brand", "reference"),
                    language="ja",
                )
            )
        if en_brand:
            en_parts = [en_brand, ref]
            if str(effective_category).upper() == "SUNGLASSES":
                en_parts.append("sunglasses")
            candidates.append(
                GeneratedQuery(
                    query=" ".join(en_parts),
                    tier=TIER_REFERENCE_EXACT_EN,
                    signals=("brand", "reference"),
                    language="en",
                )
            )

    # Tier 2–4 — collection / family (+ size / material / category)
    collection = product.collection or bag.model_family or ""
    family = product.family or bag.model_family or collection
    strong_model = bool(collection or (family and product.has_strong_model) or bag.has_distinct_model_family)

    if strong_model and (collection or family):
        model_token = collection or family
        if bag.has_distinct_model_family:
            bag_queries = build_bag_model_queries(bag, brand=brand or brand_key)
            for idx, raw in enumerate(bag_queries):
                lang = (
                    "ja"
                    if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in raw)
                    else "en"
                )
                tier = TIER_COLLECTION_FAMILY_SIZE if lang == "ja" else TIER_COLLECTION_FAMILY_SIZE_EN
                if idx >= 2:
                    tier = (
                        TIER_COLLECTION_FAMILY_CATEGORY
                        if lang == "ja"
                        else TIER_COLLECTION_FAMILY_CATEGORY_EN
                    )
                candidates.append(
                    GeneratedQuery(
                        query=raw,
                        tier=tier,
                        signals=("brand", "family", "dictionary_alias"),
                        language=lang,
                    )
                )
        else:
            if ja_brand:
                if size:
                    candidates.append(
                        GeneratedQuery(
                            query=" ".join(p for p in [ja_brand, model_token, size, cat_ja] if p),
                            tier=TIER_COLLECTION_FAMILY_SIZE,
                            signals=("brand", "collection", "size", "category"),
                            language="ja",
                        )
                    )
                if material_ja or material:
                    candidates.append(
                        GeneratedQuery(
                            query=" ".join(
                                p for p in [ja_brand, model_token, material_ja or material] if p
                            ),
                            tier=TIER_COLLECTION_FAMILY_MATERIAL,
                            signals=("brand", "collection", "material"),
                            language="ja",
                        )
                    )
                candidates.append(
                    GeneratedQuery(
                        query=" ".join(p for p in [ja_brand, model_token, cat_ja] if p),
                        tier=TIER_COLLECTION_FAMILY_CATEGORY,
                        signals=("brand", "collection", "category"),
                        language="ja",
                    )
                )
            if en_brand:
                en_cat = (
                    "Tote"
                    if "TOTE" in str(effective_category).upper()
                    else (
                        effective_category.replace("_", " ").title() if effective_category else ""
                    )
                )
                if size:
                    candidates.append(
                        GeneratedQuery(
                            query=" ".join(p for p in [en_brand, model_token, size, en_cat] if p),
                            tier=TIER_COLLECTION_FAMILY_SIZE_EN,
                            signals=("brand", "collection", "size", "category"),
                            language="en",
                        )
                    )
                if material:
                    candidates.append(
                        GeneratedQuery(
                            query=" ".join(p for p in [en_brand, model_token, material.title()] if p),
                            tier=TIER_COLLECTION_FAMILY_MATERIAL_EN,
                            signals=("brand", "collection", "material"),
                            language="en",
                        )
                    )
                candidates.append(
                    GeneratedQuery(
                        query=" ".join(p for p in [en_brand, model_token, en_cat] if p),
                        tier=TIER_COLLECTION_FAMILY_CATEGORY_EN,
                        signals=("brand", "collection", "category"),
                        language="en",
                    )
                )

    # Tier 5 — distinctive model tokens
    if product.has_strong_model and not refs:
        tokens = [t for t in product.primary_query_tokens() if t]
        if tokens and ja_brand:
            candidates.append(
                GeneratedQuery(
                    query=" ".join([ja_brand, *tokens]),
                    tier=TIER_DISTINCTIVE_MODEL,
                    signals=("brand", "model_tokens"),
                    language="ja",
                )
            )
        if tokens and en_brand:
            candidates.append(
                GeneratedQuery(
                    query=" ".join([en_brand, *tokens]),
                    tier=TIER_DISTINCTIVE_MODEL_EN,
                    signals=("brand", "model_tokens"),
                    language="en",
                )
            )

    has_strong = bool(refs or strong_model or product.has_strong_model)

    # Controlled category fallback ONLY when stronger identity is absent.
    if not has_strong and (ja_brand or en_brand):
        fallback_ja = " ".join(
            p
            for p in [
                ja_brand or en_brand,
                cat_ja or _category_token_ja(effective_category, category),
                material_ja,
                color_ja,
            ]
            if p
        )
        fallback_en = " ".join(
            p
            for p in [
                en_brand or ja_brand,
                (effective_category or category or "").replace("_", " ").lower(),
                material.lower() if material else "",
                str(color).lower() if color and color != "UNKNOWN" else "",
            ]
            if p
        )
        if fallback_ja:
            candidates.append(
                GeneratedQuery(
                    query=fallback_ja,
                    tier=TIER_CATEGORY_FALLBACK,
                    signals=("brand", "category"),
                    language="ja",
                )
            )
        if fallback_en and _normalize(fallback_en) != _normalize(fallback_ja):
            candidates.append(
                GeneratedQuery(
                    query=fallback_en,
                    tier=TIER_CATEGORY_FALLBACK_EN,
                    signals=("brand", "category"),
                    language="en",
                )
            )

    capped, dropped = _dedupe_and_cap(candidates, max_queries=max_queries)
    identity_snapshot = {
        "brand": brand_key,
        "category": effective_category,
        "references": list(refs),
        "collection": collection,
        "family": family,
        "material": material,
        "size": size,
        "color": color,
        "bag_model_family": bag.model_family,
    }

    if not capped:
        return QueryGenerationResult(
            queries=(),
            status=STATUS_NO_SAFE_QUERY,
            reason=REASON_NO_SAFE,
            available_signals=tuple(dict.fromkeys(available)),
            missing_signals=tuple(dict.fromkeys(missing)),
            dropped=tuple(dropped),
            identity_snapshot=identity_snapshot,
        )

    used_fallback = (not has_strong) and any(
        item.tier in {TIER_CATEGORY_FALLBACK, TIER_CATEGORY_FALLBACK_EN} for item in capped
    )

    if has_strong:
        status, reason = STATUS_OK, REASON_OK
    elif used_fallback:
        status, reason = STATUS_OK_WITH_FALLBACK, REASON_FALLBACK
    else:
        status, reason = STATUS_OK, REASON_OK

    return QueryGenerationResult(
        queries=tuple(capped),
        status=status,
        reason=reason,
        available_signals=tuple(dict.fromkeys(available)),
        missing_signals=tuple(dict.fromkeys(missing)),
        dropped=tuple(dropped),
        identity_snapshot=identity_snapshot,
    )


def _category_token_ja(effective: str, raw: str) -> str:
    combined = f"{effective} {raw}".lower()
    if any(t in combined for t in ("sun", "サングラス")):
        return "サングラス"
    if any(t in combined for t in ("wallet", "財布", "card")):
        return "財布"
    if any(t in combined for t in ("shoe", "sandal", "pump", "靴", "サンダル")):
        return "シューズ"
    if any(t in combined for t in ("hat", "cap", "帽子")):
        return "帽子"
    if any(t in combined for t in ("bag", "tote", "バッグ")):
        return "バッグ"
    return CATEGORY_JA.get(effective, CATEGORY_JA.get(raw, ""))


def _normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())


def _dedupe_and_cap(
    candidates: list[GeneratedQuery],
    *,
    max_queries: int,
) -> tuple[list[GeneratedQuery], list[dict[str, str]]]:
    seen: set[str] = set()
    out: list[GeneratedQuery] = []
    dropped: list[dict[str, str]] = []
    for item in candidates:
        normalized = _normalize(item.query)
        if not normalized:
            dropped.append({"query": item.query, "reason": "empty"})
            continue
        key = normalized.casefold()
        if key in seen:
            dropped.append({"query": normalized, "reason": "duplicate"})
            continue
        if len(normalized.split()) < 2:
            dropped.append({"query": normalized, "reason": "too_broad_brand_only"})
            continue
        seen.add(key)
        if len(out) >= max_queries:
            dropped.append({"query": normalized, "reason": "cap"})
            continue
        out.append(
            GeneratedQuery(
                query=normalized,
                tier=item.tier,
                signals=item.signals,
                language=item.language,
            )
        )
    return out, dropped
