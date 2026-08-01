"""Structured domestic comparable search tracing and failure taxonomy.

Used by the batch profit pipeline for operational evidence. Failure codes reuse
existing reason vocabulary where possible and add stage-level codes required
for one-product live verification.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from marketplace.browser_acquisition.comparable_candidate import ComparableCandidate
from marketplace.browser_acquisition.comparable_matching import ComparableEstimateResult
from marketplace.browser_acquisition.models import YahooSoldSample
from marketplace.browser_acquisition.yahoo_comparable import YahooBestComparable


class DomesticFailureStage:
    """Stage-level failure codes for domestic comparable / profit tracing."""

    CATEGORY_INELIGIBLE = "CATEGORY_INELIGIBLE"
    CANDIDATE_NOT_SELECTED = "CANDIDATE_NOT_SELECTED"
    PROFIT_BRIDGE_EXCLUDED = "PROFIT_BRIDGE_EXCLUDED"
    DOMESTIC_SEARCH_NOT_EXECUTED = "DOMESTIC_SEARCH_NOT_EXECUTED"
    YAHOO_REQUEST_FAILED = "YAHOO_REQUEST_FAILED"
    YAHOO_ZERO_RESULTS = "YAHOO_ZERO_RESULTS"
    YAHOO_ALL_FILTERED = "YAHOO_ALL_FILTERED"
    YAHOO_ALL_MATCHES_REJECTED = "YAHOO_ALL_MATCHES_REJECTED"
    MERCARI_REQUEST_FAILED = "MERCARI_REQUEST_FAILED"
    MERCARI_ZERO_RESULTS = "MERCARI_ZERO_RESULTS"
    MERCARI_ALL_FILTERED = "MERCARI_ALL_FILTERED"
    MERCARI_ALL_MATCHES_REJECTED = "MERCARI_ALL_MATCHES_REJECTED"
    NO_DOMESTIC_COMPARABLE = "NO_DOMESTIC_COMPARABLE"
    NO_DEFENSIBLE_MODEL_FAMILY_COMPARABLE = "NO_DEFENSIBLE_MODEL_FAMILY_COMPARABLE"
    COMPARABLE_SELECTOR_REJECTED = "COMPARABLE_SELECTOR_REJECTED"
    INSUFFICIENT_PRICE_EVIDENCE = "INSUFFICIENT_PRICE_EVIDENCE"
    PROFIT_CALCULATION_FAILED = "PROFIT_CALCULATION_FAILED"
    RANKING_REJECTED = "RANKING_REJECTED"


@dataclass
class MarketplaceSearchTrace:
    """One marketplace domestic search stage report."""

    marketplace: str
    search_executed: bool = False
    queries: list[str] = field(default_factory=list)
    request_status: str = ""
    raw_candidates: int = 0
    after_marketplace_filtering: int = 0
    after_normalization: int = 0
    after_deterministic_matching: int = 0
    rejection_reason_counts: dict[str, int] = field(default_factory=dict)
    sold_listing_evidence_count: int = 0
    active_listing_evidence_count: int = 0
    price_values_for_median: list[int] = field(default_factory=list)
    median_sold_price_jpy: int | None = None
    final_selected: dict[str, Any] | None = None
    failure_stage: str | None = None
    failure_detail: str = ""
    evidence_note: str = ""


@dataclass
class DomesticComparableTrace:
    """Full operational trace for one candidate through domestic comps + profit."""

    overseas: dict[str, Any] = field(default_factory=dict)
    yahoo: MarketplaceSearchTrace = field(default_factory=lambda: MarketplaceSearchTrace(marketplace="Yahoo Auctions"))
    mercari: MarketplaceSearchTrace = field(default_factory=lambda: MarketplaceSearchTrace(marketplace="Mercari"))
    selection: dict[str, Any] = field(default_factory=dict)
    profit: dict[str, Any] = field(default_factory=dict)
    query_generation: dict[str, Any] = field(default_factory=dict)
    overall_failure_stage: str | None = None
    overall_failure_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def count_rejection_reasons(result: ComparableEstimateResult | None) -> dict[str, int]:
    if result is None:
        return {}
    counter: Counter[str] = Counter()
    for diagnostic in result.rejected_diagnostics:
        key = diagnostic.rejection_reasons[0] if diagnostic.rejection_reasons else "UNKNOWN"
        counter[key] += 1
    return dict(counter)


def sold_active_counts(samples: list[YahooSoldSample]) -> tuple[int, int]:
    sold = 0
    active = 0
    for sample in samples:
        status = (sample.auction_status or "").lower()
        if "sold" in status or status in {"ended", "closed", "sold_out"}:
            sold += 1
        elif "active" in status or "on_sale" in status or status == "open":
            active += 1
        else:
            # Yahoo sold acquirer returns completed auctions; treat blank as sold evidence.
            sold += 1
    return sold, active


def build_marketplace_trace(
    *,
    marketplace: str,
    search_executed: bool,
    queries: list[str],
    request_status: str,
    samples: list[YahooSoldSample],
    comparable: ComparableEstimateResult | None,
    best: YahooBestComparable | None,
    error: str = "",
    evidence_note: str = "",
) -> MarketplaceSearchTrace:
    raw = len(samples)
    after_filter = raw  # marketplace hard exclusions already applied in acquirers
    after_norm = raw
    after_match = len(comparable.matched_samples) if comparable is not None else 0
    rejection = count_rejection_reasons(comparable)
    sold_count, active_count = sold_active_counts(samples)
    prices = [int(sample.sold_price_jpy) for sample in (comparable.matched_samples if comparable else ()) if sample.sold_price_jpy > 0]
    median = int(comparable.median_jpy) if comparable is not None and comparable.median_jpy and after_match else None
    selected = None
    if best is not None:
        selected = {
            "title": best.title,
            "price_jpy": best.price_jpy,
            "url": best.url,
            "matching_score": best.matching_score,
            "condition": best.condition,
            "matched_attributes": best.matched_attributes,
            "identity_material": best.identity_material,
            "identity_category": best.identity_category,
        }

    failure_stage = None
    failure_detail = ""
    prefix = "YAHOO" if "yahoo" in marketplace.lower() else "MERCARI"
    if error:
        failure_stage = f"{prefix}_REQUEST_FAILED"
        failure_detail = error
    elif not search_executed:
        failure_stage = DomesticFailureStage.DOMESTIC_SEARCH_NOT_EXECUTED
        failure_detail = "Search was not invoked"
    elif raw == 0:
        failure_stage = f"{prefix}_ZERO_RESULTS"
        failure_detail = "Search executed but returned zero listing candidates"
    elif after_filter == 0:
        failure_stage = f"{prefix}_ALL_FILTERED"
        failure_detail = "All candidates removed by marketplace filtering"
    elif after_match == 0 and selected is None:
        failure_stage = f"{prefix}_ALL_MATCHES_REJECTED"
        failure_detail = "Candidates survived acquisition but none met matching threshold"
    elif selected is None:
        failure_stage = DomesticFailureStage.COMPARABLE_SELECTOR_REJECTED
        failure_detail = "Matched samples existed but no final comparable was selected"
    else:
        failure_stage = None
        failure_detail = ""

    return MarketplaceSearchTrace(
        marketplace=marketplace,
        search_executed=search_executed and not bool(error),
        queries=list(queries),
        request_status=request_status,
        raw_candidates=raw,
        after_marketplace_filtering=after_filter,
        after_normalization=after_norm,
        after_deterministic_matching=after_match,
        rejection_reason_counts=rejection,
        sold_listing_evidence_count=sold_count,
        active_listing_evidence_count=active_count,
        price_values_for_median=prices,
        median_sold_price_jpy=median,
        final_selected=selected,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        evidence_note=evidence_note,
    )


def build_selection_trace(
    *,
    yahoo_best: YahooBestComparable | None,
    mercari_best: YahooBestComparable | None,
    selected: ComparableCandidate | None,
    predicted_sale_price_jpy: Decimal,
    evidence_count: int,
    fallback_used: str,
) -> dict[str, Any]:
    considered = []
    if yahoo_best is not None:
        considered.append({"marketplace": "Yahoo Auctions", "score": yahoo_best.matching_score, "price_jpy": yahoo_best.price_jpy})
    if mercari_best is not None:
        considered.append({"marketplace": "Mercari", "score": mercari_best.matching_score, "price_jpy": mercari_best.price_jpy})
    if selected is None:
        return {
            "yahoo_comparable_available": yahoo_best is not None,
            "mercari_comparable_available": mercari_best is not None,
            "candidates_considered": considered,
            "selection_rule": "higher matching_score, then material identity, then category identity",
            "final_selected_marketplace": "",
            "final_selected_comparable": None,
            "final_predicted_domestic_sale_price_jpy": int(predicted_sale_price_jpy) if predicted_sale_price_jpy else 0,
            "evidence_count": evidence_count,
            "fallback_used": fallback_used,
            "failure_stage": (
                DomesticFailureStage.NO_DOMESTIC_COMPARABLE
                if not considered
                else DomesticFailureStage.COMPARABLE_SELECTOR_REJECTED
            ),
            "failure_detail": "No marketplace-neutral comparable selected",
        }
    return {
        "yahoo_comparable_available": yahoo_best is not None,
        "mercari_comparable_available": mercari_best is not None,
        "candidates_considered": considered,
        "selection_rule": "higher matching_score, then material identity, then category identity",
        "final_selected_marketplace": selected.marketplace,
        "final_selected_comparable": {
            "title": selected.title,
            "price_jpy": selected.price_jpy,
            "url": selected.listing_url,
            "matching_score": selected.matching_score,
            "match_status": selected.match_status,
            "condition": selected.condition,
        },
        "final_predicted_domestic_sale_price_jpy": int(predicted_sale_price_jpy) if predicted_sale_price_jpy else selected.price_jpy,
        "evidence_count": evidence_count,
        "fallback_used": fallback_used,
        "failure_stage": None,
        "failure_detail": "",
    }


def resolve_overall_failure(*, yahoo: MarketplaceSearchTrace, mercari: MarketplaceSearchTrace, selection: dict[str, Any], profit: dict[str, Any]) -> tuple[str | None, str]:
    if selection.get("final_selected_comparable") and not profit.get("failure_stage"):
        return None, ""
    if profit.get("failure_stage"):
        return str(profit["failure_stage"]), str(profit.get("failure_detail") or "")
    if selection.get("failure_stage"):
        return str(selection["failure_stage"]), str(selection.get("failure_detail") or "")
    for stage in (yahoo.failure_stage, mercari.failure_stage):
        if stage:
            return stage, yahoo.failure_detail if stage == yahoo.failure_stage else mercari.failure_detail
    return DomesticFailureStage.NO_DOMESTIC_COMPARABLE, "No domestic comparable produced"
