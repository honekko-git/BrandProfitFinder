"""Comparable sold-price quality gates (generic, brand-agnostic).

Filters and classification run BEFORE robust price estimation.
Does not change ProfitCalculator or ranking formulas.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from marketplace.browser_acquisition.models import YahooSoldSample


class SoldStatus(StrEnum):
    SOLD_COMPLETED = "SOLD_COMPLETED"
    ACTIVE = "ACTIVE"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class ComparableQuality(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SUSPECT = "SUSPECT"
    INSUFFICIENT = "INSUFFICIENT"


SOLD_STATUS_TOKENS = frozenset(
    {
        "sold",
        "sold_out",
        "soldout",
        "trading",
        "completed",
        "sold_completed",
        "closed",
        "ended",
        "rakusatsu",
    }
)

ACTIVE_STATUS_TOKENS = frozenset(
    {
        "active",
        "on_sale",
        "onsale",
        "buy_now",
        "buynow",
        "auction",
        "open",
        "bidding",
        "current",
        "listing",
    }
)

JUNK_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ジャンク",
        r"現状品",
        r"部品取り",
        r"破損",
        r"壊れ",
        r"修理",
        r"1円",
        r"１円",
        r"箱のみ",
        r"空箱",
        r"ノベルティ",
        r"ケースのみ",
        r"ポーチのみ",
        r"\bjunk\b",
        r"\bdamaged\b",
        r"\bbroken\b",
        r"\brepair\b",
        r"parts\s*only",
        r"box\s*only",
        r"empty\s*box",
        r"pouch\s*only",
        r"accessory\s*only",
    )
)

COMPARABLE_CATEGORY_SCORE = 70
STRONG_MATCH_SCORE = 90
# Generic relative floor: comps far below purchase are treated as contamination risk.
SUSPICIOUS_LOW_PRICE_RATIO = Decimal("0.30")


@dataclass(frozen=True, slots=True)
class ComparableEvidenceItem:
    marketplace: str
    title: str
    sale_price: int
    status: str
    sold_date: str
    match_score: int
    url: str = ""
    match_attributes: str = ""
    rejected_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ComparableQualityReport:
    quality: str
    publish_price: bool
    reason: str
    sold_confirmed_count: int
    junk_excluded_count: int
    active_excluded_count: int
    unknown_excluded_count: int
    same_model_matches: int
    category_matches: int
    evidence: tuple[ComparableEvidenceItem, ...]
    latest_sold_date: str = ""
    oldest_sold_date: str = ""
    median_calculation_count: int = 0
    marketplaces: str = ""
    freshness_label: str = ""
    user_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


def normalize_auction_status(raw: str) -> str:
    return re.sub(r"[\s|]+", "_", str(raw or "").strip().lower())


def classify_sold_status(sample: YahooSoldSample) -> str:
    """Classify whether a sample is a confirmed sold price."""
    status = normalize_auction_status(sample.auction_status)
    source = str(sample.source or "").strip().lower()

    if any(token in status for token in ACTIVE_STATUS_TOKENS):
        return SoldStatus.ACTIVE.value
    if status and any(token in status for token in SOLD_STATUS_TOKENS):
        return SoldStatus.SOLD_COMPLETED.value

    # Closed Yahoo sold acquirer: blank status + Yahoo source ⇒ completed 落札.
    if not status and "yahoo" in source:
        return SoldStatus.SOLD_COMPLETED.value

    if not status:
        return SoldStatus.UNKNOWN.value
    return SoldStatus.UNKNOWN.value


def is_confirmed_sold_sample(sample: YahooSoldSample) -> bool:
    return classify_sold_status(sample) == SoldStatus.SOLD_COMPLETED.value


def is_low_quality_title(title: str) -> bool:
    text = str(title or "")
    if not text.strip():
        return True
    return any(pattern.search(text) for pattern in JUNK_TITLE_PATTERNS)


def filter_estimation_samples(
    samples: list[YahooSoldSample] | tuple[YahooSoldSample, ...],
    *,
    purchase_price_jpy: Decimal | None = None,
) -> tuple[list[YahooSoldSample], dict[str, int]]:
    """Keep only confirmed sold, non-junk samples for price estimation.

    When purchase_price_jpy is provided, also drop comps below 30% of purchase
    (suspicious low-price contamination) before matching/estimation.
    """
    kept: list[YahooSoldSample] = []
    counts = {
        "input": 0,
        "junk_excluded": 0,
        "active_excluded": 0,
        "unknown_excluded": 0,
        "suspicious_low_excluded": 0,
        "sold_kept": 0,
    }
    floor: int | None = None
    if purchase_price_jpy is not None and purchase_price_jpy > 0:
        floor = int(purchase_price_jpy * SUSPICIOUS_LOW_PRICE_RATIO)
    for sample in samples or []:
        counts["input"] += 1
        if is_low_quality_title(sample.title):
            counts["junk_excluded"] += 1
            continue
        status = classify_sold_status(sample)
        if status == SoldStatus.ACTIVE.value:
            counts["active_excluded"] += 1
            continue
        if status != SoldStatus.SOLD_COMPLETED.value:
            counts["unknown_excluded"] += 1
            continue
        if floor is not None and int(sample.sold_price_jpy or 0) < floor:
            counts["suspicious_low_excluded"] += 1
            continue
        kept.append(sample)
        counts["sold_kept"] += 1
    return kept, counts


def is_strong_match_diagnostic(diagnostic: Any) -> bool:
    """True when diagnostic indicates strong model / family identity match."""
    score = int(getattr(diagnostic, "matching_score", 0) or 0)
    if score >= STRONG_MATCH_SCORE:
        return True
    components = getattr(diagnostic, "score_components", ()) or ()
    for name, points in components:
        key = str(name or "").lower()
        if key in {"model_number", "model_family"} and int(points or 0) > 0:
            # Broad taxonomy labels like generic "Tote" alone are not strong.
            if key == "model_family" and int(points or 0) < 40:
                return False
            family = str(getattr(diagnostic, "model_family", "") or "").strip().lower()
            # Require material/model-number evidence or high overall score for family-only.
            if key == "model_family" and family in {"tote", "bag", "handbag", ""}:
                return score >= STRONG_MATCH_SCORE
            return True
    return False


def prefer_strong_matches_for_estimation(
    accepted_rows: list[tuple[YahooSoldSample, Any]],
) -> tuple[list[tuple[YahooSoldSample, Any]], dict[str, int]]:
    """Prefer strong model matches so weak category comps cannot dilute the median."""
    counts = {
        "accepted_before_prefer": len(accepted_rows),
        "strong_matches": 0,
        "weak_matches_dropped": 0,
        "used_strong_only": 0,
    }
    if not accepted_rows:
        return accepted_rows, counts
    strong = [row for row in accepted_rows if is_strong_match_diagnostic(row[1])]
    counts["strong_matches"] = len(strong)
    if len(strong) >= 1:
        counts["weak_matches_dropped"] = len(accepted_rows) - len(strong)
        counts["used_strong_only"] = 1
        return strong, counts
    return accepted_rows, counts


def build_evidence_item(
    sample: YahooSoldSample,
    *,
    match_score: int = 0,
    match_attributes: str = "",
    rejected_reason: str = "",
) -> ComparableEvidenceItem:
    status = classify_sold_status(sample)
    return ComparableEvidenceItem(
        marketplace=str(sample.source or ""),
        title=sample.title,
        sale_price=int(sample.sold_price_jpy or 0),
        status=status,
        sold_date=str(sample.sold_at or ""),
        match_score=int(match_score or 0),
        url=str(sample.url or ""),
        match_attributes=match_attributes,
        rejected_reason=rejected_reason,
    )


def classify_comparable_quality(
    *,
    purchase_price_jpy: Decimal | None,
    accepted_samples: list[YahooSoldSample] | tuple[YahooSoldSample, ...],
    accepted_diagnostics: tuple | list | None = None,
    comparable_warning: str = "",
    filter_counts: dict[str, int] | None = None,
) -> ComparableQualityReport:
    """Classify estimate quality and whether a selling price may be published."""
    counts = filter_counts or {}
    diagnostics = list(accepted_diagnostics or [])
    same_model = 0
    category_matches = 0
    evidence: list[ComparableEvidenceItem] = []

    diag_by_title: dict[str, Any] = {}
    for diag in diagnostics:
        title = str(getattr(diag, "title", "") or "")
        if title:
            diag_by_title[title] = diag

    for sample in accepted_samples or []:
        diag = diag_by_title.get(sample.title)
        score = int(getattr(diag, "matching_score", 0) or 0) if diag is not None else 0
        attrs = ""
        if diag is not None:
            components = getattr(diag, "score_components", ()) or ()
            attrs = ", ".join(f"{name}:{points}" for name, points in components)
            family = str(getattr(diag, "model_family", "") or "")
            if family:
                attrs = f"family:{family}; {attrs}".strip("; ")
            if is_strong_match_diagnostic(diag):
                same_model += 1
            elif score >= COMPARABLE_CATEGORY_SCORE:
                category_matches += 1
        elif score >= STRONG_MATCH_SCORE:
            same_model += 1
        elif score >= COMPARABLE_CATEGORY_SCORE:
            category_matches += 1
        evidence.append(
            build_evidence_item(
                sample,
                match_score=score,
                match_attributes=attrs,
            )
        )

    sold_count = len(accepted_samples or [])
    latest = ""
    oldest = ""
    dates = [str(s.sold_at) for s in (accepted_samples or []) if s.sold_at]
    if dates:
        latest = max(dates)
        oldest = min(dates)
    markets = sorted({str(s.source or "").strip() for s in (accepted_samples or []) if str(s.source or "").strip()})
    marketplaces = " / ".join(markets)
    freshness = _format_freshness_label(oldest, latest)

    def _report(**kwargs) -> ComparableQualityReport:
        base = {
            "latest_sold_date": latest,
            "oldest_sold_date": oldest,
            "median_calculation_count": sold_count,
            "marketplaces": marketplaces,
            "freshness_label": freshness,
        }
        base.update(kwargs)
        return ComparableQualityReport(**base)

    suspect = comparable_warning == "COMPARABLE_DATA_SUSPECT"
    low_excluded = int(counts.get("suspicious_low_excluded", 0))
    if purchase_price_jpy is not None and sold_count > 0:
        prices = sorted(int(s.sold_price_jpy) for s in accepted_samples)
        mid = prices[len(prices) // 2]
        if purchase_price_jpy > 0 and Decimal(mid) < (purchase_price_jpy * SUSPICIOUS_LOW_PRICE_RATIO):
            suspect = True
    # Heavy low-price exclusion with few remaining comps ⇒ contamination risk.
    if low_excluded >= 5 and same_model == 0 and sold_count < 3:
        suspect = True
    if same_model == 0 and category_matches >= 5 and sold_count >= 5:
        # Broad category-only pool without model identity is treated as suspect.
        if purchase_price_jpy is not None and sold_count > 0:
            prices = sorted(int(s.sold_price_jpy) for s in accepted_samples)
            spread = max(prices) - min(prices) if prices else 0
            if spread > int(purchase_price_jpy or 0):
                suspect = True

    if sold_count == 0:
        reason = "同一モデル販売データ不足"
        if low_excluded or int(counts.get("junk_excluded", 0)):
            reason = "比較データ品質不足"
            quality = ComparableQuality.SUSPECT.value if low_excluded >= 3 else ComparableQuality.INSUFFICIENT.value
        else:
            quality = ComparableQuality.INSUFFICIENT.value
        return _report(
            quality=quality,
            publish_price=False,
            reason=reason,
            sold_confirmed_count=0,
            junk_excluded_count=int(counts.get("junk_excluded", 0)),
            active_excluded_count=int(counts.get("active_excluded", 0)),
            unknown_excluded_count=int(counts.get("unknown_excluded", 0)),
            same_model_matches=0,
            category_matches=0,
            evidence=tuple(evidence),
            user_message=(
                "販売予想価格: 信頼性不足（比較データ品質不足）"
                if quality == ComparableQuality.SUSPECT.value
                else "販売予想価格: 算出不可（同一モデル販売データ不足）"
            ),
        )

    if suspect:
        return _report(
            quality=ComparableQuality.SUSPECT.value,
            publish_price=False,
            reason="比較データ品質不足",
            sold_confirmed_count=sold_count,
            junk_excluded_count=int(counts.get("junk_excluded", 0)),
            active_excluded_count=int(counts.get("active_excluded", 0)),
            unknown_excluded_count=int(counts.get("unknown_excluded", 0)),
            same_model_matches=same_model,
            category_matches=max(category_matches, sold_count - same_model),
            evidence=tuple(evidence),
            user_message=(
                "販売予想価格: 信頼性不足（比較データ品質不足） "
                f"同一モデル一致:{same_model} / カテゴリ一致:{max(category_matches, sold_count - same_model)}"
            ),
        )

    if same_model >= 3 and sold_count >= 3:
        quality = ComparableQuality.HIGH.value
        reason = "落札済・同一モデル一致が十分"
        publish = True
    elif same_model >= 1 and sold_count >= 3:
        quality = ComparableQuality.MEDIUM.value
        reason = "落札済・ファミリー/カテゴリ一致"
        publish = True
    elif sold_count >= 3 and same_model == 0:
        # Weak category-only pool: do not publish a selling price.
        return _report(
            quality=ComparableQuality.SUSPECT.value,
            publish_price=False,
            reason="同一モデル販売データ不足",
            sold_confirmed_count=sold_count,
            junk_excluded_count=int(counts.get("junk_excluded", 0)),
            active_excluded_count=int(counts.get("active_excluded", 0)),
            unknown_excluded_count=int(counts.get("unknown_excluded", 0)),
            same_model_matches=0,
            category_matches=max(category_matches, sold_count),
            evidence=tuple(evidence),
            user_message=(
                "販売予想価格: 算出不可（同一モデル販売データ不足） "
                f"同一モデル一致:0 / カテゴリ一致:{sold_count}"
            ),
        )
    else:
        quality = ComparableQuality.INSUFFICIENT.value
        reason = "同一モデル販売データ不足"
        publish = False

    return _report(
        quality=quality,
        publish_price=publish,
        reason=reason,
        sold_confirmed_count=sold_count,
        junk_excluded_count=int(counts.get("junk_excluded", 0)),
        active_excluded_count=int(counts.get("active_excluded", 0)),
        unknown_excluded_count=int(counts.get("unknown_excluded", 0)),
        same_model_matches=same_model,
        category_matches=max(category_matches, sold_count - same_model),
        evidence=tuple(evidence),
        user_message=(
            (
                f"根拠: 比較件数 {sold_count}件 / 同一モデル {same_model}件"
                f" / マーケット {marketplaces or '-'} / 最新販売 {latest or '-'}"
                f" / 品質 {quality}"
                + (f" / 販売データ {freshness}" if freshness else "")
            )
            if publish
            else f"販売予想価格: 算出不可（{reason}）"
        ),
    )


def _format_freshness_label(oldest: str, latest: str) -> str:
    """Build a short JP freshness label from ISO-ish date strings."""
    if not oldest and not latest:
        return ""

    def _ym(value: str) -> str:
        text = str(value or "")
        if len(text) >= 7 and text[4] == "-":
            year, month = text[:4], text[5:7]
            try:
                return f"{int(year)}年{int(month)}月"
            except ValueError:
                return text[:10]
        return text[:10] if text else ""

    left = _ym(oldest)
    right = _ym(latest)
    if left and right and left != right:
        return f"{left}〜{right}"
    return right or left



def apply_publish_gate(
    recommended_jpy: Decimal,
    report: ComparableQualityReport,
) -> Decimal:
    """Return 0 when quality forbids publishing a selling estimate."""
    if not report.publish_price:
        return Decimal("0")
    if recommended_jpy is None or recommended_jpy <= 0:
        return Decimal("0")
    return recommended_jpy
