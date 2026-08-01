"""New-market price validation (used estimate vs new retail reference).

Validation-only layer. Does not invent prices, does not change ProfitCalculator
or comparable matching. Stores results in operational_trace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from marketplace.browser_acquisition.product_identity import (
    ProductIdentity,
    extract_product_identity,
    is_generic_model_family,
)

# Match priority weights (reference > family > material > category).
SCORE_REFERENCE = 55
SCORE_FAMILY = 40
SCORE_MATERIAL = 20
SCORE_CATEGORY = 15
SCORE_BRAND = 0

# Must beat category-only (brand+category) — category alone is never enough.
MIN_ACCEPT_MATCH_SCORE = 55

# Risk thresholds on used/new ratio.
CRITICAL_USED_OVER_NEW_RATIO = Decimal("2.0")


class NewMarketRisk(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    NONE = "NONE"  # no comparable new-market evidence


@dataclass(frozen=True, slots=True)
class NewMarketEvidence:
    """One new-market price observation (no DB persistence required)."""

    marketplace: str
    title: str
    price: int
    currency: str = "JPY"
    url: str = ""
    retrieved_at: str = ""
    availability: str = ""
    condition: str = "NEW"
    match_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NewMarketValidationResult:
    """Outcome of used-vs-new validation for one product."""

    risk: str
    code: str
    reason: str
    used_predicted_price_jpy: int
    new_market_price_jpy: int | None
    currency: str
    marketplace: str
    evidence: NewMarketEvidence | None
    match_score: int
    ranking_safe: bool
    display_label: str
    user_message: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = self.evidence.to_dict() if self.evidence is not None else None
        return payload


def score_new_market_match(
    identity: ProductIdentity,
    evidence: NewMarketEvidence,
) -> int:
    """Score how well a new-market listing matches product identity."""
    sample = extract_product_identity(title=evidence.title, brand="", category="")
    score = 0

    purchase_refs = {ref.upper() for ref in identity.reference_numbers}
    sample_refs = {ref.upper() for ref in sample.reference_numbers}
    # Also scan raw title for spaced references already normalized by extractor.
    if purchase_refs and sample_refs and purchase_refs & sample_refs:
        score += SCORE_REFERENCE

    purchase_family = (identity.collection or identity.family or "").strip().lower()
    sample_family = (sample.collection or sample.family or "").strip().lower()
    if (
        purchase_family
        and sample_family
        and purchase_family == sample_family
        and not is_generic_model_family(purchase_family)
    ):
        score += SCORE_FAMILY

    if (
        identity.material not in {"", "UNKNOWN", "OTHER"}
        and sample.material == identity.material
    ):
        score += SCORE_MATERIAL

    if (
        identity.category not in {"", "UNKNOWN"}
        and sample.category == identity.category
    ):
        score += SCORE_CATEGORY

    # Brand presence is required for any accept path but adds no points.
    brand = (identity.brand or "").strip().upper()
    title_u = (evidence.title or "").upper()
    brand_ok = (not brand) or (brand in title_u) or (brand.title() in evidence.title)
    if not brand_ok and brand:
        # Soft: Japanese brand aliases are rare here; reject if English brand missing.
        if brand.lower() not in (evidence.title or "").lower():
            return 0

    return min(100, score)


def is_acceptable_new_market_match(score: int, *, has_reference_or_family: bool) -> bool:
    """Category-only matches must not create warnings."""
    if score < MIN_ACCEPT_MATCH_SCORE:
        return False
    return has_acceptable_identity_signal(score, has_reference_or_family=has_reference_or_family)


def has_acceptable_identity_signal(score: int, *, has_reference_or_family: bool) -> bool:
    if has_reference_or_family:
        return score >= MIN_ACCEPT_MATCH_SCORE
    # Without reference/family, even high category+material is insufficient for warnings.
    return False


def _has_reference_or_family_overlap(
    identity: ProductIdentity,
    evidence: NewMarketEvidence,
) -> bool:
    sample = extract_product_identity(title=evidence.title)
    purchase_refs = {ref.upper() for ref in identity.reference_numbers}
    sample_refs = {ref.upper() for ref in sample.reference_numbers}
    if purchase_refs and sample_refs and purchase_refs & sample_refs:
        return True
    purchase_family = (identity.collection or identity.family or "").strip().lower()
    sample_family = (sample.collection or sample.family or "").strip().lower()
    if (
        purchase_family
        and sample_family
        and purchase_family == sample_family
        and not is_generic_model_family(purchase_family)
    ):
        return True
    return False


def select_best_new_market_evidence(
    identity: ProductIdentity,
    candidates: list[NewMarketEvidence] | tuple[NewMarketEvidence, ...],
) -> NewMarketEvidence | None:
    """Pick best accepted new-market evidence (highest match, then lowest price)."""
    accepted: list[NewMarketEvidence] = []
    for raw in candidates or []:
        score = score_new_market_match(identity, raw)
        strong = _has_reference_or_family_overlap(identity, raw)
        if not is_acceptable_new_market_match(score, has_reference_or_family=strong):
            continue
        accepted.append(
            NewMarketEvidence(
                marketplace=raw.marketplace,
                title=raw.title,
                price=int(raw.price),
                currency=raw.currency or "JPY",
                url=raw.url,
                retrieved_at=raw.retrieved_at or datetime.now(tz=UTC).isoformat(),
                availability=raw.availability,
                condition=raw.condition or "NEW",
                match_score=score,
            )
        )
    if not accepted:
        return None
    accepted.sort(key=lambda item: (-item.match_score, item.price))
    return accepted[0]


def classify_used_vs_new_risk(
    *,
    used_predicted_price_jpy: Decimal | int | None,
    new_market_price_jpy: Decimal | int | None,
) -> tuple[str, str, str]:
    """Return (risk, code, reason) for used vs new comparison."""
    if used_predicted_price_jpy is None or new_market_price_jpy is None:
        return NewMarketRisk.NONE.value, "", ""
    used = int(used_predicted_price_jpy)
    new_price = int(new_market_price_jpy)
    if used <= 0 or new_price <= 0:
        return NewMarketRisk.NONE.value, "", ""
    if new_price >= used:
        return (
            NewMarketRisk.NORMAL.value,
            "NEW_PRICE_OK",
            "新品参考価格は中古予想以上です",
        )
    ratio = Decimal(used) / Decimal(new_price)
    if ratio >= CRITICAL_USED_OVER_NEW_RATIO:
        return (
            NewMarketRisk.CRITICAL.value,
            "NEW_PRICE_LOWER_THAN_USED",
            "新品価格が中古予想を大きく下回っています",
        )
    return (
        NewMarketRisk.WARNING.value,
        "NEW_PRICE_LOWER_THAN_USED",
        "新品価格が中古予想を下回っています",
    )


def validate_new_market_price(
    *,
    identity: ProductIdentity,
    used_predicted_price_jpy: Decimal | int | None,
    candidates: list[NewMarketEvidence] | tuple[NewMarketEvidence, ...] | None = None,
) -> NewMarketValidationResult:
    """Validate used predicted price against new-market evidence."""
    used = int(used_predicted_price_jpy or 0)
    best = select_best_new_market_evidence(identity, candidates or ())
    if best is None or used <= 0:
        return NewMarketValidationResult(
            risk=NewMarketRisk.NONE.value,
            code="",
            reason="",
            used_predicted_price_jpy=used,
            new_market_price_jpy=None,
            currency="JPY",
            marketplace="",
            evidence=None,
            match_score=0,
            ranking_safe=True,
            display_label="販売価格チェック",
            user_message="",
        )

    risk, code, reason = classify_used_vs_new_risk(
        used_predicted_price_jpy=used,
        new_market_price_jpy=best.price,
    )
    ranking_safe = risk != NewMarketRisk.CRITICAL.value
    if risk == NewMarketRisk.CRITICAL.value:
        label = "⚠ 要確認"
        message = (
            f"新品価格: ¥{best.price:,} / 中古予想: ¥{used:,} / 利益ランキング: 注意"
        )
    elif risk == NewMarketRisk.WARNING.value:
        label = "⚠ 新品価格確認"
        message = f"中古予想: ¥{used:,} / 新品参考: ¥{best.price:,} / 理由: {reason}"
    else:
        label = "販売価格チェック"
        message = f"中古予想: ¥{used:,} / 新品参考: ¥{best.price:,} / 判定: 正常"

    return NewMarketValidationResult(
        risk=risk,
        code=code,
        reason=reason,
        used_predicted_price_jpy=used,
        new_market_price_jpy=best.price,
        currency=best.currency or "JPY",
        marketplace=best.marketplace,
        evidence=best,
        match_score=best.match_score,
        ranking_safe=ranking_safe,
        display_label=label,
        user_message=message,
    )


# ---------------------------------------------------------------------------
# Backward-compatible helper used by earlier foundation wiring
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NewMarketPriceWarning:
    used_estimate_jpy: int
    new_market_price_jpy: int
    warning: str
    new_market_warning: bool = True
    risk: str = NewMarketRisk.WARNING.value
    code: str = "NEW_PRICE_LOWER_THAN_USED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_new_market_warning(
    *,
    used_estimate_jpy: Decimal | int | None,
    new_market_price_jpy: Decimal | int | None = None,
) -> NewMarketPriceWarning | None:
    """Legacy helper: warn when a supplied new price is below the used estimate."""
    risk, code, reason = classify_used_vs_new_risk(
        used_predicted_price_jpy=used_estimate_jpy,
        new_market_price_jpy=new_market_price_jpy,
    )
    if risk in {NewMarketRisk.NONE.value, NewMarketRisk.NORMAL.value}:
        return None
    return NewMarketPriceWarning(
        used_estimate_jpy=int(used_estimate_jpy or 0),
        new_market_price_jpy=int(new_market_price_jpy or 0),
        warning=reason or "新品価格が中古予想を下回っています",
        new_market_warning=True,
        risk=risk,
        code=code,
    )
