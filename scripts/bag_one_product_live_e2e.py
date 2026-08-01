"""One-product live E2E: Rebag handbag through normal production domestic pipeline.

Uses live acquisition and live Yahoo/Mercari only. Writes a full operational
trace to output/bag_one_product_e2e.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.live_rebag_intake import import_rebag_keyword
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.browser_acquisition.bag_model_family import extract_handbag_model_identity
from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    detect_model_tokens,
)
from marketplace.browser_acquisition.listing_identity import extract_listing_identity
from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.product_subtype import detect_wallet_subtype
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from marketplace.acquisition_workspace.profit_bridge import _convert
from profit_discovery.discovery_validation.batch_profit.converters import candidate_to_acquired_listing
from profit_discovery.discovery_validation.batch_profit.domestic_search_trace import DomesticFailureStage

OUT = Path("output/bag_one_product_e2e.json")
DB = Path("data/_bag_one_product_e2e.db")


def _pick_candidate(rows):
    preferred = [
        ("rebag_chanel_flap", lambda c: "chanel" in c.title.lower() and "flap" in c.title.lower() and c.category == "Bag"),
        ("rebag_chanel_handbag", lambda c: "chanel" in c.title.lower() and c.category == "Bag"),
        ("rebag_lv_speedy", lambda c: "louis vuitton" in c.title.lower() and "speedy" in c.title.lower() and c.category == "Bag"),
        ("rebag_any_bag_ab", lambda c: c.category == "Bag" and c.quality_grade in {"A", "B"} and c.brand and c.purchase_url.startswith("http")),
    ]
    for label, predicate in preferred:
        for candidate in rows:
            if predicate(candidate) and candidate.eligible_for_profit_check and not candidate.duplicate_of:
                return label, candidate
    for label, predicate in preferred:
        for candidate in rows:
            if predicate(candidate) and candidate.purchase_url.startswith("http"):
                return f"{label}_not_eligible", candidate
    return "none", None


def main() -> int:
    started = datetime.now(tz=UTC).isoformat()
    if DB.exists():
        DB.unlink()
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=DB))

    # Prefer Classic Flap; fall back to Chanel handbag keyword if needed.
    keywords = ["Chanel Classic Flap", "Chanel handbag", "Louis Vuitton Speedy"]
    intake = None
    chosen_keyword = ""
    for keyword in keywords:
        print(f"LIVE Rebag search: {keyword}", flush=True)
        intake = import_rebag_keyword(
            service,
            keyword,
            limit=8,
            run_profit=False,  # select exactly one product first
        )
        if intake.listing_count > 0 and intake.batch_id:
            chosen_keyword = keyword
            break

    report: dict = {
        "started_at": started,
        "keyword_used": chosen_keyword,
        "intake": None if intake is None else {
            "batch_id": intake.batch_id,
            "listing_count": intake.listing_count,
            "status": intake.status,
            "detail": intake.detail,
        },
    }

    if intake is None or not intake.batch_id or intake.listing_count <= 0:
        report["executive_result"] = "NO-GO"
        report["reason"] = "Rebag live acquisition returned no listings"
        report["failure_stage"] = DomesticFailureStage.DOMESTIC_SEARCH_NOT_EXECUTED
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    _, rows = service.get_batch(intake.batch_id)
    pick_label, candidate = _pick_candidate(rows)
    report["pick_rule"] = pick_label
    if candidate is None:
        report["executive_result"] = "NO-GO"
        report["reason"] = "No Bag candidate with acquisition URL found after import"
        report["imported_titles"] = [item.title for item in rows]
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    report["selected_live_product"] = {
        "marketplace": candidate.source_name,
        "candidate_id": candidate.candidate_id,
        "title": candidate.title,
        "brand": candidate.brand,
        "category": candidate.category,
        "subtype": candidate.detected_subtype,
        "material": candidate.detected_material,
        "condition": candidate.detected_condition,
        "overseas_price": str(candidate.purchase_price),
        "currency": candidate.currency,
        "purchase_price_jpy": str(candidate.purchase_price_jpy),
        "acquisition_url": candidate.purchase_url,
        "quality_score": candidate.quality_score,
        "quality_grade": candidate.quality_grade,
        "eligible": candidate.eligible_for_profit_check,
        "warnings": list(candidate.validation_warnings),
        "errors": list(candidate.validation_errors),
        "model_family": extract_handbag_model_identity(
            title=candidate.title, brand=candidate.brand, category=candidate.category
        ).model_family,
        "structural_modifier": extract_handbag_model_identity(
            title=candidate.title, brand=candidate.brand, category=candidate.category
        ).structural_modifier,
        "size": extract_handbag_model_identity(
            title=candidate.title, brand=candidate.brand, category=candidate.category
        ).size,
    }

    queries = build_yahoo_search_queries(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
    )
    identity = extract_listing_identity(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
        model_family_tokens=detect_model_tokens(candidate.title),
    )
    bag_identity = extract_handbag_model_identity(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
    )
    report["query_audit"] = {
        "original_title": candidate.title,
        "identity_category": identity.category,
        "identity_material": identity.material,
        "identity_color": identity.color,
        "model_tokens": list(detect_model_tokens(candidate.title)),
        "bag_model_family": bag_identity.model_family,
        "bag_structural_modifier": bag_identity.structural_modifier,
        "bag_size": bag_identity.size,
        "bag_material": bag_identity.material,
        "bag_aliases_matched": list(bag_identity.aliases_matched),
        "wallet_subtype": detect_wallet_subtype(candidate.title).value,
        "material_enum": detect_luxury_material(candidate.title).value,
        "queries": queries,
        "previous_generic_queries_example": [
            "シャネル バッグ パテント",
            "シャネル パテント バッグ",
            "Chanel bag patent",
        ],
        "tokens_note": "Model-first deterministic bag queries when model family is known.",
    }

    if not candidate.eligible_for_profit_check:
        report["executive_result"] = "NO-GO"
        report["failure_stage"] = DomesticFailureStage.CATEGORY_INELIGIBLE
        report["reason"] = "Imported Bag candidate remained ineligible after normalization"
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3

    # Select exactly this one candidate through the normal workspace API.
    service.deselect_all(intake.batch_id)
    service.select_candidate(intake.batch_id, candidate.candidate_id, selected=True)
    _, after_select = service.get_batch(intake.batch_id)
    selected_rows = [item for item in after_select if item.selected_for_profit_check]
    report["selection"] = {
        "selected_count": len(selected_rows),
        "selected_ids": [item.candidate_id for item in selected_rows],
    }
    if len(selected_rows) != 1:
        report["executive_result"] = "NO-GO"
        report["failure_stage"] = DomesticFailureStage.CANDIDATE_NOT_SELECTED
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 4

    print("Running production batch profit (live Yahoo + Mercari)...", flush=True)
    run = service.run_batch_profit(intake.batch_id, use_cache=False)
    if not run.results:
        report["executive_result"] = "NO-GO"
        report["failure_stage"] = DomesticFailureStage.PROFIT_BRIDGE_EXCLUDED
        report["reason"] = "run_batch_profit returned zero results"
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 5

    result = run.results[0]
    trace = dict(result.operational_trace or {})
    # Enrich overseas block with quality fields from workspace candidate.
    overseas = dict(trace.get("overseas") or {})
    overseas.update(
        {
            "raw_category_note": "Parser/acquirer category normalized before eligibility",
            "quality_score": candidate.quality_score,
            "quality_grade": candidate.quality_grade,
            "eligibility_decision": candidate.eligible_for_profit_check,
            "eligibility_warnings": list(candidate.validation_warnings),
        }
    )
    trace["overseas"] = overseas
    trace["batch_summary"] = {
        "batch_id": run.summary.batch_id,
        "total_candidates": run.summary.total_candidates,
        "processed_count": run.summary.processed_count,
        "total_yahoo_requests": run.summary.total_yahoo_requests,
        "status": run.summary.status,
        "rank": result.rank,
        "batch_decision": result.batch_decision,
        "yahoo_data_source": result.yahoo_data_source,
        "accepted_comparable_count": result.accepted_comparable_count,
        "raw_sample_count": result.raw_sample_count,
        "gross_estimated_profit": str(result.gross_estimated_profit),
        "net_estimated_profit": str(result.net_estimated_profit) if result.net_estimated_profit is not None else None,
        "roi": str(result.roi),
        "best_title": result.yahoo_best_title,
        "best_price_jpy": result.yahoo_best_price_jpy,
        "best_url": result.yahoo_best_url,
        "best_score": result.yahoo_best_score,
        "best_marketplace": result.yahoo_marketplace,
    }

    # Matching sample-level audit for selected product against accepted/rejected diagnostics JSON.
    purchase = candidate_to_acquired_listing(_convert(candidate))
    matching_audit = {
        "accept_threshold": COMPARABLE_SCORE_THRESHOLD,
        "purchase_subtype": detect_wallet_subtype(candidate.title).value,
        "purchase_material": detect_luxury_material(candidate.title).value,
        "purchase_model_tokens": list(detect_model_tokens(candidate.title)),
        "purchase_listing_for_matcher": purchase.title,
        "diagnostics_json": result.diagnostics,
        "accepted_display": result.accepted_comparables_display,
        "rejected_display": result.rejected_samples_display,
    }
    trace["matching_audit"] = matching_audit

    yahoo_ok = bool((trace.get("yahoo") or {}).get("search_executed"))
    mercari_ok = bool((trace.get("mercari") or {}).get("search_executed"))
    selected_comp = (trace.get("selection") or {}).get("final_selected_comparable")
    ranked = result.rank > 0 or run.summary.processed_count > 0
    accepted = int(result.accepted_comparable_count or 0)

    if yahoo_ok and mercari_ok and selected_comp and accepted >= 3:
        report["executive_result"] = "GO"
    elif yahoo_ok or mercari_ok:
        report["executive_result"] = "PARTIAL"
        if not selected_comp:
            report["executive_note"] = (
                "Domestic searches executed; no defensible Classic Flap comparable selected "
                "(prefer no comparable over a misleading same-brand bag)."
            )
            if not (trace.get("selection") or {}).get("failure_stage"):
                sel = dict(trace.get("selection") or {})
                sel["failure_stage"] = DomesticFailureStage.NO_DEFENSIBLE_MODEL_FAMILY_COMPARABLE
                trace["selection"] = sel
        elif accepted < 3:
            report["executive_note"] = (
                f"Defensible comparable path ran but sold evidence count remains insufficient ({accepted}<3)."
            )
    else:
        report["executive_result"] = "NO-GO"

    report["operational_trace"] = trace
    report["finished_at"] = datetime.now(tz=UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)
    print("executive_result=", report["executive_result"], flush=True)
    print("yahoo_executed=", yahoo_ok, "mercari_executed=", mercari_ok, flush=True)
    print("selected_comparable=", bool(selected_comp), "decision=", result.batch_decision, flush=True)
    return 0 if report["executive_result"] != "NO-GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
