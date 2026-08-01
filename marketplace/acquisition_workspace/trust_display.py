"""Display-only trust and transparency helpers.

Combines existing comparable quality, freshness, and new-market validation
into UI-facing evidence. Does not calculate profit or change ranking order.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class TrustRisk(StrEnum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"


@dataclass(frozen=True, slots=True)
class TrustSummary:
    """Unified risk summary for ranking / detail display."""

    overall_risk: str
    selling_confidence: str
    freshness_label: str
    new_market_risk: str
    comparable_quality: str
    sample_count: str
    same_model_count: str
    marketplaces: str
    latest_sold_date: str
    oldest_sold_date: str
    selling_note: str
    risk_reason: str
    display_rows: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["display_rows"] = [list(row) for row in self.display_rows]
        return payload


def build_trust_summary(
    *,
    comparable_quality: dict | None = None,
    new_market_validation: dict | None = None,
    new_market_warning: dict | None = None,
) -> TrustSummary:
    """Build SAFE / WARNING / DANGER summary from existing trace payloads."""
    quality = comparable_quality if isinstance(comparable_quality, dict) else {}
    nm = new_market_validation if isinstance(new_market_validation, dict) else {}
    if not nm and isinstance(new_market_warning, dict):
        nm = new_market_warning

    qlabel = str(quality.get("quality") or "")
    publish = bool(quality.get("publish_price", True)) if quality else True
    sold = quality.get("sold_confirmed_count")
    same_model = quality.get("same_model_matches")
    freshness = str(quality.get("freshness_label") or "")
    latest = str(quality.get("latest_sold_date") or "")
    oldest = str(quality.get("oldest_sold_date") or "")
    markets = str(quality.get("marketplaces") or "")

    nm_risk = str(nm.get("risk") or "")
    if nm_risk in {"", "NONE"} and nm.get("new_market_warning"):
        nm_risk = str(nm.get("risk") or "WARNING")

    # Selling confidence from comparable quality only (display).
    if not quality:
        selling_confidence = "-"
    elif not publish or qlabel in {"SUSPECT", "INSUFFICIENT"}:
        selling_confidence = qlabel or "INSUFFICIENT"
    else:
        selling_confidence = qlabel or "MEDIUM"

    reasons: list[str] = []
    overall = TrustRisk.SAFE

    if nm_risk == "CRITICAL":
        overall = TrustRisk.DANGER
        reasons.append("新品価格が中古予想を下回る")
    elif nm_risk == "WARNING":
        overall = TrustRisk.WARNING
        reasons.append("新品価格が中古予想を下回っています")

    if qlabel == "SUSPECT" or (quality and not publish):
        overall = TrustRisk.DANGER if overall == TrustRisk.DANGER else TrustRisk.WARNING
        reasons.append("比較データ品質不足")
    elif qlabel in {"INSUFFICIENT", "LOW"}:
        if overall == TrustRisk.SAFE:
            overall = TrustRisk.WARNING
        reasons.append("比較データ: 少ない")
    elif sold is not None and int(sold or 0) < 3 and qlabel not in {"HIGH", "MEDIUM"}:
        if overall == TrustRisk.SAFE:
            overall = TrustRisk.WARNING
        reasons.append("比較データ: 少ない")

    if not freshness and latest:
        freshness = latest

    nm_display = {
        "CRITICAL": "危険",
        "WARNING": "注意",
        "NORMAL": "問題なし",
        "NONE": "-",
        "": "-",
    }.get(nm_risk, nm_risk or "-")

    if overall == TrustRisk.SAFE and not reasons:
        reasons.append("販売データ・新品価格に重大な問題なし")

    note_parts = []
    if sold is not None:
        note_parts.append(f"比較件数: {sold}件")
    if same_model is not None:
        note_parts.append(f"同一モデル: {same_model}件")
    if markets:
        note_parts.append(f"マーケット: {markets}")
    if freshness:
        note_parts.append(f"データ期間: {freshness}")
    if latest:
        note_parts.append(f"最新販売: {latest}")
    if selling_confidence and selling_confidence != "-":
        note_parts.append(f"品質: {selling_confidence}")

    display_rows = (
        ("総合リスク", overall),
        ("販売データ", selling_confidence if selling_confidence != "-" else "不明"),
        ("データ期間", freshness or "-"),
        ("最新販売", latest or "-"),
        ("新品価格", nm_display),
        ("理由", " / ".join(reasons)),
    )

    return TrustSummary(
        overall_risk=overall,
        selling_confidence=selling_confidence,
        freshness_label=freshness,
        new_market_risk=nm_risk or "NONE",
        comparable_quality=qlabel,
        sample_count=str(sold) if sold is not None else "-",
        same_model_count=str(same_model) if same_model is not None else "-",
        marketplaces=markets or "-",
        latest_sold_date=latest,
        oldest_sold_date=oldest,
        selling_note=" / ".join(note_parts),
        risk_reason=" / ".join(reasons),
        display_rows=display_rows,
    )


def trust_summary_from_profit_trace(profit: dict | None) -> TrustSummary:
    """Extract trust summary from operational_trace.profit."""
    payload = profit if isinstance(profit, dict) else {}
    return build_trust_summary(
        comparable_quality=payload.get("comparable_quality"),
        new_market_validation=payload.get("new_market_validation"),
        new_market_warning=payload.get("new_market_warning"),
    )


def format_latest_sold_display(value: str) -> str:
    """Format ISO-ish date to 2026年8月1日 when possible."""
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            y, m, d = int(text[0:4]), int(text[5:7]), int(text[8:10])
            return f"{y}年{m}月{d}日"
        except ValueError:
            return text
    return text or "-"
