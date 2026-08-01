"""Title matching and domestic estimate helpers for controlled live checks."""

from __future__ import annotations

import re
from decimal import Decimal
from statistics import median

from marketplace.browser_acquisition.models import (
    AcquiredListing,
    DomesticEstimate,
    ReliabilityLevel,
    YahooSoldSample,
)

SIMILARITY_THRESHOLD = 60

NOISE_WORDS = {
    "fashionphile",
    "authenticated",
    "authentic",
    "excellent",
    "very",
    "good",
    "condition",
    "pre-owned",
    "preowned",
    "luxury",
    "designer",
    "free",
    "shipping",
    "sale",
    "clearance",
}

EXCLUDE_PATTERNS = (
    "box only",
    "dust bag only",
    "dustbag only",
    "strap only",
    "parts only",
    "for parts",
    "repair",
    "replica",
    "bulk lot",
    "lot of",
    "only box",
    "only dust",
    "箱のみ",
    "空箱",
    "ストラップのみ",
    "部品のみ",
)

WALLET_TOKENS = {
    "wallet",
    "coin",
    "purse",
    "card",
    "holder",
    "compact",
    "zip",
    "ウォレット",
    "財布",
    "コイン",
    "コインケース",
    "マトラッセ",
}
MATERIAL_TOKENS = {
    "caviar",
    "lambskin",
    "leather",
    "canvas",
    "patent",
    "quilted",
    "カビアン",
    "カーフ",
    "ラム",
    "レザー",
}
COLOR_TOKENS = {
    "black",
    "white",
    "beige",
    "navy",
    "red",
    "pink",
    "green",
    "blue",
    "gold",
    "silver",
    "gray",
    "grey",
    "黒",
    "白",
    "赤",
    "ピンク",
    "金",
}


def build_yahoo_search_terms(*, title: str, brand: str, category: str) -> str:
    """Build a Yahoo search query from one Fashionphile listing title."""
    tokens = _tokenize(title)
    tokens.update(_tokenize(brand))
    tokens.update(_tokenize(category))
    filtered = [
        token
        for token in sorted(tokens)
        if token not in NOISE_WORDS and len(token) > 1
    ]
    return " ".join(filtered[:8])


def compute_similarity_score(purchase: AcquiredListing, sample: YahooSoldSample) -> int:
    """Score purchase/sample similarity from 0 to 100."""
    if purchase.brand and purchase.brand.lower() not in sample.title.lower():
        return 0

    purchase_tokens = _tokenize(f"{purchase.title} {purchase.category}")
    sample_tokens = _tokenize(sample.title)
    if _is_excluded(sample.title):
        return 0
    if not _wallet_match(purchase_tokens, sample_tokens):
        return 0

    overlap = purchase_tokens & sample_tokens
    if not overlap:
        return 0

    score = 40
    if purchase.brand.lower() in sample.title.lower():
        score += 20
    if purchase_tokens & WALLET_TOKENS and sample_tokens & WALLET_TOKENS:
        score += 15
    if purchase_tokens & MATERIAL_TOKENS and sample_tokens & MATERIAL_TOKENS:
        score += 10
    if purchase_tokens & COLOR_TOKENS and sample_tokens & COLOR_TOKENS:
        score += 10
    score += min(15, len(overlap) * 3)
    return min(100, score)


def filter_matched_samples(
    purchase: AcquiredListing,
    samples: list[YahooSoldSample],
    *,
    min_score: int = SIMILARITY_THRESHOLD,
) -> list[tuple[YahooSoldSample, int]]:
    """Return Yahoo samples meeting the similarity threshold."""
    matched: list[tuple[YahooSoldSample, int]] = []
    for sample in samples:
        score = compute_similarity_score(purchase, sample)
        if score >= min_score:
            matched.append((sample, score))
    matched.sort(key=lambda item: (-item[1], -item[0].sold_price_jpy))
    return matched


def compute_domestic_estimate(
    matched: list[tuple[YahooSoldSample, int]],
    *,
    listing_url: str = "",
) -> DomesticEstimate:
    """Compute domestic sold estimate from matched samples."""
    samples = [sample for sample, _score in matched]
    prices = [sample.sold_price_jpy for sample in samples]
    if not prices:
        return DomesticEstimate(
            sample_count=0,
            minimum_jpy=0,
            maximum_jpy=0,
            average_jpy=Decimal("0"),
            median_jpy=Decimal("0"),
            trimmed_average_jpy=None,
            reliability=ReliabilityLevel.LOW,
            listing_url=listing_url,
            matched_samples=(),
        )

    sorted_prices = sorted(prices)
    trimmed = _trimmed_average(sorted_prices)
    reliability = _reliability(len(prices))
    return DomesticEstimate(
        sample_count=len(prices),
        minimum_jpy=min(prices),
        maximum_jpy=max(prices),
        average_jpy=Decimal(str(round(sum(prices) / len(prices)))),
        median_jpy=Decimal(str(int(median(prices)))),
        trimmed_average_jpy=Decimal(str(round(trimmed))) if trimmed is not None else None,
        reliability=reliability,
        listing_url=listing_url or (samples[0].url if samples else ""),
        matched_samples=tuple(samples),
    )


def best_matching_score(matched: list[tuple[YahooSoldSample, int]]) -> float:
    """Return the highest similarity score among matched samples."""
    if not matched:
        return 0.0
    return float(max(score for _sample, score in matched))


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", text.lower()))
    return {token for token in tokens if token}


def is_excluded_title(title: str) -> bool:
    """Return True when a listing title indicates accessory-only or unrelated inventory."""
    lowered = title.lower()
    return any(pattern in lowered for pattern in EXCLUDE_PATTERNS)


def _is_excluded(title: str) -> bool:
    return is_excluded_title(title)


def _wallet_match(purchase_tokens: set[str], sample_tokens: set[str]) -> bool:
    purchase_wallet = bool(purchase_tokens & WALLET_TOKENS)
    sample_wallet = bool(sample_tokens & WALLET_TOKENS)
    if purchase_wallet:
        return sample_wallet
    return True


def _trimmed_average(prices: list[int]) -> float | None:
    if len(prices) < 4:
        return None
    trimmed = prices[1:-1]
    if not trimmed:
        return None
    return sum(trimmed) / len(trimmed)


def _reliability(count: int) -> ReliabilityLevel:
    if count >= 8:
        return ReliabilityLevel.HIGH
    if count >= 3:
        return ReliabilityLevel.MEDIUM
    return ReliabilityLevel.LOW
