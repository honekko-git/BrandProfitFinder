"""Concise Japanese unpublished selling-price reasons (display only)."""

from __future__ import annotations

from typing import Any


def concise_unpublished_reason(
    *,
    quality: str = "",
    quality_reason: str = "",
    query_generation: dict[str, Any] | None = None,
    yahoo_failure: str = "",
    mercari_failure: str = "",
    same_model: int | None = None,
    sold_confirmed: int | None = None,
) -> str:
    """Map operational evidence to one short ranking-cell reason."""
    qg = query_generation or {}
    status = str(qg.get("query_generation_status") or qg.get("status") or "")
    if status == "NO_SAFE_QUERY":
        return "型番・モデル検索語を生成できません"

    if quality == "SUSPECT" or "SUSPECT" in (quality_reason or "").upper():
        return "比較データ品質不足"

    if same_model is not None and same_model == 0 and (sold_confirmed or 0) > 0:
        return "同一モデル件数不足"
    if same_model is not None and same_model < 1:
        return "同一モデル件数不足"

    yahoo = (yahoo_failure or "").upper()
    mercari = (mercari_failure or "").upper()
    if "ZERO_RESULTS" in yahoo and "ZERO_RESULTS" in mercari:
        return "国内販売済みデータなし"
    if "ZERO_RESULTS" in yahoo or "ZERO_RESULTS" in mercari:
        return "国内販売済みデータなし"
    if "REQUEST_FAILED" in yahoo and "REQUEST_FAILED" in mercari:
        return "国内販売済みデータなし"
    if quality == "INSUFFICIENT" or "INSUFFICIENT" in (quality_reason or "").upper():
        return "国内販売済みデータなし"

    if quality_reason:
        # Prefer known Japanese labels already produced by quality gate.
        text = str(quality_reason).strip()
        if text:
            return text[:40]
    return "国内販売済みデータなし"
