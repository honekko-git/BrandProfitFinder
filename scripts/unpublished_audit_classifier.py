"""Deterministic unpublished-reason classifier (diagnostics only).

Not used by ProfitCalculator / ranking / acquisition pipelines.
"""

from __future__ import annotations

from typing import Any

STRONG_SCORE = 90
REQUIRED_SAME_MODEL = 1
REQUIRED_SOLD = 3


def classify_primary(
    *,
    result: dict | None,
    quality_info: dict,
    warning: str,
    nmv: dict,
    identity: dict,
    yahoo: dict,
    mercari: dict,
    same_model: int,
    sold: int,
    category_matches: int,
    best_score: int,
    junk: int,
    raw_before: float | None = None,
) -> tuple[str, list[str]]:
    secondary: list[str] = []
    if result is None:
        return "MISSING_REQUIRED_TRACE_DATA", ["NO_PROFIT_RESULT"]

    risk = str(nmv.get("risk") or "").upper()
    if risk == "CRITICAL" or (
        nmv.get("ranking_safe") is False and str(nmv.get("code") or "").startswith("NEW_PRICE")
    ):
        return "NEW_PRICE_CRITICAL", secondary

    quality = str(quality_info.get("quality") or "")
    reason_text = str(quality_info.get("reason") or "")

    if warning == "COMPARABLE_DATA_SUSPECT" or quality == "SUSPECT":
        if junk >= 3:
            secondary.append("LOW_QUALITY_COMPARABLES_REMOVED")
        if same_model == 0 and category_matches > 0:
            secondary.append("CATEGORY_ONLY_MATCHES")
        if sold >= 3 and same_model == 0:
            return "CATEGORY_ONLY_MATCHES", ["COMPARABLE_DATA_SUSPECT"] + secondary
        return "COMPARABLE_DATA_SUSPECT", secondary

    if sold == 0:
        if junk > 0:
            secondary.append("LOW_QUALITY_COMPARABLES_REMOVED")
        yahoo_raw = int(yahoo.get("raw_count") or 0)
        mercari_raw = int(mercari.get("raw_count") or 0)
        yahoo_sold = int(yahoo.get("sold_confirmed") or 0)
        mercari_sold = int(mercari.get("sold_confirmed") or 0)
        market_sold = yahoo_sold + mercari_sold
        rejects = dict(yahoo.get("rejection_reason_counts") or {})
        rejects.update(dict(mercari.get("rejection_reason_counts") or {}))
        if yahoo_raw == 0 and mercari_raw == 0:
            if identity.get("reference_numbers") and (yahoo.get("queries") or mercari.get("queries")):
                return "QUERY_TOO_NARROW", ["NO_SOLD_DATA"] + secondary
            if (
                not identity.get("reference_numbers")
                and not identity.get("family")
                and not identity.get("collection")
            ):
                return "IDENTITY_EXTRACTION_INCOMPLETE", ["NO_SOLD_DATA"] + secondary
            # Empty queries on analyzed rows often means search did not persist usable query text.
            if not (yahoo.get("queries") or mercari.get("queries")) and (
                yahoo.get("search_executed") or mercari.get("search_executed")
            ):
                return "QUERY_TOO_NARROW", ["NO_SOLD_DATA", "EMPTY_STORED_QUERIES"] + secondary
            return "NO_SOLD_DATA", secondary
        # Marketplace returned listings but quality gate accepted none.
        if rejects.get("SCORE_BELOW_THRESHOLD") or rejects.get("MODEL_SIMILARITY_LOW"):
            return "LOW_MATCH_SCORE", ["NO_ACCEPTED_COMPARABLES"] + secondary
        unknown = int(quality_info.get("unknown_excluded_count") or 0)
        if unknown > 0:
            return "SOLD_STATUS_UNKNOWN", ["NO_SOLD_DATA"] + secondary
        if junk > 0:
            return "LOW_QUALITY_COMPARABLES_REMOVED", ["NO_SOLD_DATA"] + secondary
        if market_sold > 0:
            return "NO_ACCEPTED_COMPARABLES", ["MARKET_SOLD_PRESENT_BUT_UNACCEPTED"] + secondary
        return "NO_ACCEPTED_COMPARABLES", ["NO_SOLD_DATA"] + secondary

    if same_model == 0 and sold > 0:
        if identity.get("reference_numbers"):
            secondary.append("REFERENCE_PRESENT_BUT_UNMATCHED")
            if yahoo.get("raw_count", 0) + mercari.get("raw_count", 0) > 0:
                return "REFERENCE_NOT_FOUND", ["INSUFFICIENT_SAME_MODEL_COUNT"] + secondary
            return "MODEL_FAMILY_NOT_FOUND", secondary
        if not identity.get("family") and not identity.get("collection"):
            return "IDENTITY_EXTRACTION_INCOMPLETE", ["INSUFFICIENT_SAME_MODEL_COUNT"] + secondary
        if category_matches >= sold and sold >= 3:
            return "CATEGORY_ONLY_MATCHES", ["INSUFFICIENT_SAME_MODEL_COUNT"] + secondary
        if best_score and best_score < STRONG_SCORE:
            return "LOW_MATCH_SCORE", ["INSUFFICIENT_SAME_MODEL_COUNT"] + secondary
        return "INSUFFICIENT_SAME_MODEL_COUNT", secondary

    if sold < REQUIRED_SOLD:
        return "INSUFFICIENT_ACCEPTED_COUNT", secondary

    if best_score and 0 < best_score < STRONG_SCORE and same_model == 0:
        return "LOW_MATCH_SCORE", secondary

    if quality == "INSUFFICIENT":
        return "INSUFFICIENT_ACCEPTED_COUNT", secondary

    if "同一モデル" in reason_text:
        return "INSUFFICIENT_SAME_MODEL_COUNT", secondary
    if "品質" in reason_text:
        return "COMPARABLE_DATA_SUSPECT", secondary

    if same_model >= REQUIRED_SAME_MODEL and sold >= REQUIRED_SOLD and quality in {"HIGH", "MEDIUM"}:
        return "PIPELINE_INTEGRATION_ERROR", ["UNEXPECTED_UNPUBLISH"]

    return "OTHER", secondary


def recoverability(
    primary: str,
    identity: dict[str, Any],
    yahoo: dict[str, Any],
    mercari: dict[str, Any],
    same_model: int,
    sold: int,
    best_score: int,
) -> str:
    if primary in {"NEW_PRICE_CRITICAL", "COMPARABLE_DATA_SUSPECT", "CATEGORY_ONLY_MATCHES"}:
        return "A_CORRECT_REJECTION"
    if primary == "PIPELINE_INTEGRATION_ERROR":
        return "G_PIPELINE_DEFECT"
    if primary in {"IDENTITY_EXTRACTION_INCOMPLETE", "MODEL_FAMILY_NOT_FOUND", "REFERENCE_NOT_FOUND"}:
        return "B_RECOVERABLE_BY_IDENTITY"
    if primary in {"QUERY_TOO_NARROW", "QUERY_TOO_BROAD"}:
        return "C_RECOVERABLE_BY_QUERY"
    if primary in {"SOLD_STATUS_UNKNOWN", "MISSING_SOLD_DATE"}:
        return "E_RECOVERABLE_BY_DATA_STATUS"
    if primary in {"NO_SOLD_DATA", "NO_ACCEPTED_COMPARABLES"} and (
        int(yahoo.get("raw_count") or 0) + int(mercari.get("raw_count") or 0) == 0
    ):
        if identity.get("reference_numbers") or identity.get("family"):
            return "C_RECOVERABLE_BY_QUERY"
        return "D_RECOVERABLE_BY_MARKET_LIQUIDITY"
    if primary in {"INSUFFICIENT_SAME_MODEL_COUNT", "INSUFFICIENT_ACCEPTED_COUNT", "LOW_MATCH_SCORE"}:
        if same_model >= 1 and sold >= 2:
            return "F_POSSIBLE_THRESHOLD_TUNING"
        if best_score >= 70 and sold >= 1:
            return "F_POSSIBLE_THRESHOLD_TUNING"
        if int(yahoo.get("raw_count") or 0) + int(mercari.get("raw_count") or 0) > 0:
            return "D_RECOVERABLE_BY_MARKET_LIQUIDITY"
        return "C_RECOVERABLE_BY_QUERY"
    if primary == "LOW_QUALITY_COMPARABLES_REMOVED":
        return "E_RECOVERABLE_BY_DATA_STATUS"
    return "A_CORRECT_REJECTION"
