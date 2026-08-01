"""Presentation helpers for capital-aware ranking table cells.

Uses existing stored values only. Does not calculate profit or change ranking.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path


def format_yen(value: Decimal | int | float | str | None) -> str:
    """Format a JPY amount for ranking table display."""
    if value is None or value == "":
        return "-"
    try:
        amount = Decimal(str(value))
    except Exception:
        return "-"
    if amount <= 0:
        return "-"
    return f"¥{int(amount):,}"


def resolve_purchase_text(row) -> str:
    """Resolve purchase display using existing acquisition cost fields only."""
    jpy_text = format_yen(getattr(row, "purchase_price_jpy", None))
    if jpy_text != "-":
        return jpy_text

    price = getattr(row, "purchase_price", None)
    currency = str(getattr(row, "currency", "") or "").strip().upper()
    if price is None or price == "":
        return "-"
    try:
        amount = Decimal(str(price))
    except Exception:
        return "-"
    if amount <= 0:
        return "-"
    if currency in {"", "JPY", "円"}:
        return format_yen(amount)
    if amount == amount.to_integral_value():
        return f"{int(amount):,} {currency}"
    return f"{amount} {currency}"


def split_brand_title(brand: str | None, title: str | None) -> tuple[str, str]:
    """Split brand and remaining product name for ranking display."""
    brand_text = str(brand or "").strip()
    title_text = str(title or "").strip()
    if not brand_text:
        return "", title_text
    if title_text.lower().startswith(brand_text.lower()):
        remainder = title_text[len(brand_text) :].lstrip(" \t-–—|/・")
        return brand_text, remainder or title_text
    return brand_text, title_text


def analysis_badge(confidence: str | None, *, has_warning: bool = False) -> str:
    """Map existing confidence / warning state to a compact semantic badge."""
    if has_warning:
        return "⚠"
    raw = str(confidence or "").strip()
    upper = raw.upper()
    if raw in {"高"} or upper == "HIGH":
        return "◎"
    if raw in {"中"} or upper == "MEDIUM":
        return "○"
    if raw in {"低"} or upper == "LOW":
        return "△"
    return "○"


def build_analysis_badges(
    rows: list,
    ranking_by_id: dict | None = None,
    *,
    url_warning_fn=None,
) -> dict[str, str]:
    """Precompute AI analysis badges for ranking rows (presentation only)."""
    ranks = ranking_by_id or {}
    badges: dict[str, str] = {}
    for row in rows:
        rank = ranks.get(row.candidate_id)
        if rank is not None:
            confidence = getattr(rank, "confidence_level", None)
        else:
            truth = getattr(row, "data_truth_summary", None)
            confidence = getattr(truth, "confidence_level", None) if truth is not None else None
        has_warning = False
        if url_warning_fn is not None:
            has_warning = url_warning_fn(row) is not None
        badges[row.candidate_id] = analysis_badge(confidence, has_warning=has_warning)
    return badges


def build_price_cells(
    rows: list,
    *,
    selling_estimate_by_id: dict[str, Decimal | None] | None = None,
    selling_meta_by_id: dict[str, dict] | None = None,
) -> dict[str, dict[str, str]]:
    """Build per-candidate purchase / expected-sale display values."""
    estimates = selling_estimate_by_id or {}
    meta = selling_meta_by_id or {}
    cells: dict[str, dict[str, str]] = {}
    for row in rows:
        selling_raw = estimates.get(row.candidate_id)
        info = meta.get(row.candidate_id) or {}
        quality = str(info.get("quality") or "")
        if quality in {"SUSPECT", "INSUFFICIENT"} or (
            selling_raw is not None and Decimal(str(selling_raw)) <= 0 and info.get("reason")
        ):
            selling_text = "算出不可"
            note = str(info.get("reason") or "信頼できる販売データ不足")
        else:
            selling_text = format_yen(selling_raw)
            note = str(info.get("summary") or info.get("selling_note") or "")
        cells[row.candidate_id] = {
            "purchase": resolve_purchase_text(row),
            "selling": selling_text,
            "selling_label": "販売予想",
            "selling_note": note,
            "selling_quality": quality or str(info.get("selling_confidence") or ""),
            "selling_confidence": str(info.get("selling_confidence") or quality or "-"),
            "freshness_label": str(info.get("freshness_label") or "-"),
            "new_market_risk": str(info.get("new_market_risk") or "NONE"),
            "overall_risk": str(info.get("overall_risk") or "-"),
            "risk_reason": str(info.get("risk_reason") or ""),
            "latest_sold_date": str(info.get("latest_sold_date") or "-"),
        }
    return cells


def build_title_cells(rows: list) -> dict[str, dict[str, str]]:
    """Build brand / product title parts for ranking display."""
    cells: dict[str, dict[str, str]] = {}
    for row in rows:
        brand, product = split_brand_title(
            getattr(row, "brand", ""),
            getattr(row, "title", ""),
        )
        cells[row.candidate_id] = {
            "brand": brand,
            "product": product,
        }
    return cells


def resolve_selling_estimates_from_batch_runs(
    rows: list,
    *,
    database_path: Path | str | None = None,
) -> dict[str, Decimal | None]:
    """Read already-computed selling estimates from saved batch runs."""
    estimates, _meta = resolve_selling_estimate_bundle_from_batch_runs(
        rows, database_path=database_path
    )
    return estimates


def resolve_selling_estimate_bundle_from_batch_runs(
    rows: list,
    *,
    database_path: Path | str | None = None,
) -> tuple[dict[str, Decimal | None], dict[str, dict]]:
    """Return selling estimates plus quality metadata from saved batch runs."""
    from app.storage.batch_profit_repository import BatchProfitRepository

    repository = BatchProfitRepository(database_path=database_path)
    estimates: dict[str, Decimal | None] = {row.candidate_id: None for row in rows}
    meta: dict[str, dict] = {row.candidate_id: {} for row in rows}
    batch_ids = {
        row.last_profit_batch_id
        for row in rows
        if getattr(row, "last_profit_batch_id", "")
    }
    for batch_id in batch_ids:
        try:
            run = repository.get_run(batch_id)
        except Exception:
            continue
        if run is None:
            continue
        for item in run.results:
            candidate_id = item.candidate.candidate_id
            if candidate_id not in estimates:
                continue
            quality_info = {}
            trace = getattr(item, "operational_trace", None) or {}
            profit = trace.get("profit") if isinstance(trace, dict) else {}
            if isinstance(profit, dict):
                quality_info = profit.get("comparable_quality") or {}
            quality = str(quality_info.get("quality") or "")
            publish = bool(quality_info.get("publish_price", True))
            reason = str(quality_info.get("reason") or "")
            sold_count = quality_info.get("sold_confirmed_count")
            same_model = quality_info.get("same_model_matches")
            latest = quality_info.get("latest_sold_date") or ""
            freshness = quality_info.get("freshness_label") or ""
            markets = quality_info.get("marketplaces") or ""
            warning = getattr(item.domestic, "comparable_warning", "") or ""
            recommended = item.domestic.recommended_selling_estimate_jpy
            from marketplace.acquisition_workspace.trust_display import (
                format_latest_sold_display,
                trust_summary_from_profit_trace,
            )

            trust = trust_summary_from_profit_trace(profit if isinstance(profit, dict) else {})
            latest_display = format_latest_sold_display(str(latest)) if latest else ""

            # Never fall back to median/trimmed when quality gate unpublished the price.
            if (
                (not publish)
                or quality in {"SUSPECT", "INSUFFICIENT"}
                or warning in {"COMPARABLE_DATA_SUSPECT", "COMPARABLE_DATA_INSUFFICIENT"}
                or recommended is None
                or recommended <= 0
            ):
                estimates[candidate_id] = Decimal("0")
                from marketplace.acquisition_workspace.unpublished_reason import concise_unpublished_reason

                qg = trace.get("query_generation") if isinstance(trace, dict) else {}
                yahoo = trace.get("yahoo") if isinstance(trace, dict) else {}
                mercari = trace.get("mercari") if isinstance(trace, dict) else {}
                reason_text = concise_unpublished_reason(
                    quality=quality,
                    quality_reason=reason or "同一モデル販売データ不足",
                    query_generation=qg if isinstance(qg, dict) else {},
                    yahoo_failure=str((yahoo or {}).get("failure_stage") or ""),
                    mercari_failure=str((mercari or {}).get("failure_stage") or ""),
                    same_model=int(same_model) if same_model is not None else None,
                    sold_confirmed=int(sold_count) if sold_count is not None else None,
                )
                meta[candidate_id] = {
                    "quality": quality or ("SUSPECT" if "SUSPECT" in warning else "INSUFFICIENT"),
                    "reason": reason_text,
                    "summary": reason_text,
                    "selling_note": reason_text,
                    "publish_price": False,
                    "freshness_label": trust.freshness_label or freshness or "-",
                    "marketplaces": markets,
                    "same_model_matches": same_model,
                    "sold_confirmed_count": sold_count,
                    "selling_confidence": trust.selling_confidence,
                    "new_market_risk": trust.new_market_risk,
                    "overall_risk": trust.overall_risk,
                    "risk_reason": trust.risk_reason,
                    "latest_sold_date": latest_display or trust.latest_sold_date,
                }
                continue

            estimates[candidate_id] = recommended
            summary = trust.selling_note
            if trust.new_market_risk == "CRITICAL":
                summary = f"{summary} / ⚠要確認:新品価格" if summary else "⚠要確認:新品価格"
            elif trust.new_market_risk == "WARNING":
                summary = f"{summary} / ⚠新品価格確認" if summary else "⚠新品価格確認"
            meta[candidate_id] = {
                "quality": quality or "MEDIUM",
                "reason": reason,
                "summary": summary,
                "selling_note": summary,
                "publish_price": True,
                "freshness_label": trust.freshness_label or freshness or "-",
                "marketplaces": markets,
                "same_model_matches": same_model,
                "sold_confirmed_count": sold_count,
                "selling_confidence": trust.selling_confidence,
                "new_market_risk": trust.new_market_risk,
                "overall_risk": trust.overall_risk,
                "risk_reason": trust.risk_reason,
                "latest_sold_date": latest_display or trust.latest_sold_date,
            }
    return estimates, meta
