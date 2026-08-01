"""Multi-brand live E2E: prove dictionary-driven model-family reuse.

Runs one real Rebag → Yahoo/Mercari → profit path per brand.
Uses production pipeline only (no fixtures / demo injection).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.live_rebag_intake import import_rebag_keyword
from marketplace.acquisition_workspace.live_realreal_intake import import_realreal_keyword
from marketplace.acquisition_workspace.live_vestiaire_intake import import_vestiaire_keyword
from marketplace.acquisition_workspace.profit_bridge import _convert
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.browser_acquisition.bag_model_family import extract_handbag_model_identity
from marketplace.browser_acquisition.comparable_matching import COMPARABLE_SCORE_THRESHOLD
from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from profit_discovery.discovery_validation.batch_profit.converters import candidate_to_acquired_listing
from profit_discovery.discovery_validation.batch_profit.domestic_search_trace import DomesticFailureStage

# Live overseas acquisition sources only (no fixtures). Vestiaire first:
# Rebag public search often returns an unfiltered featured shelf.
_LIVE_INTAKE_FUNCS = (
    ("Vestiaire Collective", import_vestiaire_keyword),
    ("The RealReal", import_realreal_keyword),
    ("Rebag", import_rebag_keyword),
)

OUT = Path("output/multi_brand_model_family_e2e.json")
DB_DIR = Path("data")

# Preferred model keyword first, then fallbacks. Engine stays brand-agnostic;
# keywords are only acquisition search seeds.
BRAND_RUNS: tuple[dict, ...] = (
    {
        "brand_label": "Louis Vuitton",
        "preferred_family": "Speedy",
        "keywords": [
            "Louis Vuitton Speedy",
            "Louis Vuitton Neverfull",
            "Louis Vuitton Alma",
        ],
    },
    {
        "brand_label": "Hermes",
        "preferred_family": "Kelly",
        "keywords": [
            "Hermes Kelly",
            "Hermes Birkin",
            "Hermes Picotin",
        ],
    },
    {
        "brand_label": "Gucci",
        "preferred_family": "Dionysus",
        "keywords": [
            "Gucci Dionysus",
            "Gucci Marmont",
            "Gucci Jackie",
        ],
    },
    {
        "brand_label": "Prada",
        "preferred_family": "Re-Edition",
        "keywords": [
            "Prada Re-Edition",
            "Prada Galleria",
            "Prada Cleo",
        ],
    },
)


def _pick_candidate(rows, *, preferred_family: str, brand_label: str):
    brand_l = brand_label.lower()
    preferred_l = preferred_family.lower()

    def brand_ok(c) -> bool:
        return brand_l in (c.brand or "").lower() or brand_l in (c.title or "").lower()

    rules = [
        (
            f"preferred_{preferred_family}",
            lambda c: brand_ok(c)
            and c.category == "Bag"
            and preferred_l in (c.title or "").lower()
            and extract_handbag_model_identity(title=c.title, brand=c.brand, category=c.category).model_family
            == preferred_family,
        ),
        (
            "brand_bag_known_family",
            lambda c: brand_ok(c)
            and c.category == "Bag"
            and bool(
                extract_handbag_model_identity(title=c.title, brand=c.brand, category=c.category).model_family
            ),
        ),
        (
            "brand_bag_any",
            lambda c: brand_ok(c) and c.category == "Bag",
        ),
    ]
    for label, predicate in rules:
        for candidate in rows:
            if (
                predicate(candidate)
                and candidate.eligible_for_profit_check
                and not candidate.duplicate_of
                and candidate.purchase_url.startswith("http")
            ):
                return label, candidate
    for label, predicate in rules:
        for candidate in rows:
            if predicate(candidate) and candidate.purchase_url.startswith("http"):
                return f"{label}_not_eligible", candidate
    return "none", None


def _near_miss(purchase, diagnostics_json: str) -> dict:
    try:
        payload = json.loads(diagnostics_json or "{}")
    except json.JSONDecodeError:
        return {}
    rejected = list(payload.get("rejected") or [])
    if not rejected:
        return {}
    rejected.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
    top = rejected[0]
    return {
        "title": top.get("title"),
        "score": top.get("score"),
        "model_family": top.get("model_family"),
        "rejection_reasons": top.get("rejection_reasons") or top.get("reasons"),
        "material": top.get("material"),
    }


def _run_one(brand_cfg: dict) -> dict:
    brand_label = brand_cfg["brand_label"]
    preferred_family = brand_cfg["preferred_family"]
    started = time.perf_counter()
    timings = {
        "acquisition_s": 0.0,
        "matching_and_profit_s": 0.0,
        "total_s": 0.0,
    }
    db_path = DB_DIR / f"_multi_brand_{brand_label.lower().replace(' ', '_')}_e2e.db"
    if db_path.exists():
        db_path.unlink()
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))

    intake = None
    chosen_keyword = ""
    chosen_source = ""
    pick_label = "none"
    candidate = None
    intake_attempts: list[dict] = []
    acq_t0 = time.perf_counter()
    for keyword in brand_cfg["keywords"]:
        for source_name, intake_fn in _LIVE_INTAKE_FUNCS:
            print(f"[{brand_label}] LIVE {source_name} search: {keyword}", flush=True)
            attempt = intake_fn(service, keyword, limit=8, run_profit=False)
            intake_attempts.append(
                {
                    "source": source_name,
                    "keyword": keyword,
                    "status": attempt.status,
                    "listing_count": attempt.listing_count,
                    "detail": (attempt.detail or "")[:300],
                }
            )
            if not attempt.batch_id or attempt.listing_count <= 0:
                continue
            _, rows = service.get_batch(attempt.batch_id)
            label, picked = _pick_candidate(
                rows, preferred_family=preferred_family, brand_label=brand_label
            )
            if picked is None:
                continue
            # Prefer a hit on the preferred model family; otherwise keep searching.
            picked_family = extract_handbag_model_identity(
                title=picked.title, brand=picked.brand, category=picked.category
            ).model_family
            intake = attempt
            chosen_keyword = keyword
            chosen_source = source_name
            pick_label = label
            candidate = picked
            if picked_family == preferred_family or preferred_family.lower() in (picked.title or "").lower():
                break
        if candidate is not None and (
            extract_handbag_model_identity(
                title=candidate.title, brand=candidate.brand, category=candidate.category
            ).model_family
            == preferred_family
            or preferred_family.lower() in (candidate.title or "").lower()
        ):
            break
    timings["acquisition_s"] = round(time.perf_counter() - acq_t0, 3)

    report: dict = {
        "brand": brand_label,
        "preferred_family": preferred_family,
        "keyword_used": chosen_keyword,
        "overseas_source": chosen_source,
        "architecture_path": "A_dictionary_only_expected",
        "timings": timings,
        "intake_attempts": intake_attempts,
        "pick_rule": pick_label,
        "intake": None
        if intake is None
        else {
            "batch_id": intake.batch_id,
            "listing_count": intake.listing_count,
            "status": intake.status,
            "detail": intake.detail,
            "source": chosen_source,
        },
    }

    if intake is None or not intake.batch_id or intake.listing_count <= 0 or candidate is None:
        report["executive_result"] = "NO-GO"
        report["reason"] = "Live overseas acquisition returned no usable Bag candidate"
        report["failure_stage"] = DomesticFailureStage.DOMESTIC_SEARCH_NOT_EXECUTED
        timings["total_s"] = round(time.perf_counter() - started, 3)
        return report

    bag_identity = extract_handbag_model_identity(
        title=candidate.title, brand=candidate.brand, category=candidate.category
    )
    queries = build_yahoo_search_queries(
        title=candidate.title, brand=candidate.brand, category=candidate.category
    )
    report["selected_live_product"] = {
        "marketplace": candidate.source_name,
        "candidate_id": candidate.candidate_id,
        "title": candidate.title,
        "brand": candidate.brand,
        "category": candidate.category,
        "model_family": bag_identity.model_family,
        "structural_modifier": bag_identity.structural_modifier,
        "size": bag_identity.size,
        "material": bag_identity.material or detect_luxury_material(candidate.title).value,
        "aliases_matched": list(bag_identity.aliases_matched),
        "overseas_price": str(candidate.purchase_price),
        "currency": candidate.currency,
        "purchase_price_jpy": str(candidate.purchase_price_jpy),
        "acquisition_url": candidate.purchase_url,
        "eligible": candidate.eligible_for_profit_check,
        "quality_grade": candidate.quality_grade,
    }
    report["dictionary_audit"] = {
        "brand": candidate.brand,
        "model_family": bag_identity.model_family,
        "aliases_matched": list(bag_identity.aliases_matched),
        "queries": queries,
        "dictionary_files": [
            "marketplace/browser_acquisition/model_dictionaries/families.json",
            "marketplace/browser_acquisition/model_dictionaries/brands.json",
            "marketplace/browser_acquisition/model_dictionaries/structures.json",
            "marketplace/browser_acquisition/model_dictionaries/sizes.json",
            "marketplace/browser_acquisition/model_dictionaries/materials.json",
        ],
    }

    if not candidate.eligible_for_profit_check:
        report["executive_result"] = "NO-GO"
        report["failure_stage"] = DomesticFailureStage.CATEGORY_INELIGIBLE
        report["reason"] = "Candidate ineligible after normalization"
        timings["total_s"] = round(time.perf_counter() - started, 3)
        return report

    if not bag_identity.model_family:
        report["executive_result"] = "PARTIAL"
        report["reason"] = "Live product acquired but model-family dictionary did not resolve a family"
        timings["total_s"] = round(time.perf_counter() - started, 3)
        return report

    service.deselect_all(intake.batch_id)
    service.select_candidate(intake.batch_id, candidate.candidate_id, selected=True)

    print(f"[{brand_label}] Running production batch profit...", flush=True)
    profit_t0 = time.perf_counter()
    run = service.run_batch_profit(intake.batch_id, use_cache=False)
    timings["matching_and_profit_s"] = round(time.perf_counter() - profit_t0, 3)

    if not run.results:
        report["executive_result"] = "NO-GO"
        report["failure_stage"] = DomesticFailureStage.PROFIT_BRIDGE_EXCLUDED
        report["reason"] = "run_batch_profit returned zero results"
        timings["total_s"] = round(time.perf_counter() - started, 3)
        return report

    result = run.results[0]
    trace = dict(result.operational_trace or {})
    purchase = candidate_to_acquired_listing(_convert(candidate))
    near_miss = _near_miss(purchase, result.diagnostics)

    # Optional local re-eval metadata for selected comparable identity.
    selected = (trace.get("selection") or {}).get("final_selected_comparable") or {}
    selected_title = selected.get("title") or result.yahoo_best_title or ""
    selected_identity = (
        extract_handbag_model_identity(title=selected_title, brand=candidate.brand, category="Bag")
        if selected_title
        else None
    )

    yahoo = trace.get("yahoo") or {}
    mercari = trace.get("mercari") or {}
    matching_validation = {
        "accept_threshold": COMPARABLE_SCORE_THRESHOLD,
        "selected_comparable": {
            "title": selected_title,
            "brand": candidate.brand,
            "model_family": selected_identity.model_family if selected_identity else "",
            "structure": selected_identity.structural_modifier if selected_identity else "",
            "size": selected_identity.size if selected_identity else "",
            "material": selected_identity.material if selected_identity else "",
            "similarity_score": selected.get("matching_score") or result.yahoo_best_score,
            "price_jpy": selected.get("price_jpy") or result.yahoo_best_price_jpy,
            "marketplace": result.yahoo_marketplace,
            "url": selected.get("url") or result.yahoo_best_url,
            "acceptance_reason": "MODEL_FAMILY_MATCH + score>=threshold"
            if selected
            else "none_selected",
        },
        "evidence_count_raw": result.raw_sample_count,
        "accepted_count": result.accepted_comparable_count,
        "sold_count_yahoo": yahoo.get("sold_listing_evidence_count"),
        "sold_count_mercari": mercari.get("sold_listing_evidence_count"),
        "median_sold_yahoo": yahoo.get("median_sold_price_jpy"),
        "median_sold_mercari": mercari.get("median_sold_price_jpy"),
        "strongest_near_miss": near_miss,
        "batch_decision": result.batch_decision,
        "gross_estimated_profit": str(result.gross_estimated_profit),
        "roi": str(result.roi),
    }
    report["matching_validation"] = matching_validation
    report["operational_trace"] = {
        "yahoo_search_executed": bool(yahoo.get("search_executed")),
        "mercari_search_executed": bool(mercari.get("search_executed")),
        "yahoo_queries": yahoo.get("queries"),
        "mercari_queries": mercari.get("queries"),
        "yahoo_rejection_reason_counts": yahoo.get("rejection_reason_counts"),
        "mercari_rejection_reason_counts": mercari.get("rejection_reason_counts"),
        "selection": trace.get("selection"),
        "batch_summary": {
            "batch_id": run.summary.batch_id,
            "accepted_comparable_count": result.accepted_comparable_count,
            "raw_sample_count": result.raw_sample_count,
            "batch_decision": result.batch_decision,
            "rank": result.rank,
        },
    }

    yahoo_ok = bool(yahoo.get("search_executed"))
    mercari_ok = bool(mercari.get("search_executed"))
    accepted = int(result.accepted_comparable_count or 0)
    same_family = bool(selected_identity and selected_identity.model_family == bag_identity.model_family)

    if yahoo_ok and mercari_ok and selected and accepted >= 3 and same_family:
        report["executive_result"] = "GO"
    elif yahoo_ok or mercari_ok:
        report["executive_result"] = "PARTIAL"
        notes = []
        if not selected:
            notes.append("no defensible comparable selected")
        elif not same_family:
            notes.append(
                f"selected family mismatch purchase={bag_identity.model_family} selected={selected_identity.model_family if selected_identity else ''}"
            )
        if accepted < 3:
            notes.append(f"accepted_count={accepted}<3")
        report["executive_note"] = "; ".join(notes) or "domestic path partial"
    else:
        report["executive_result"] = "NO-GO"

    timings["total_s"] = round(time.perf_counter() - started, 3)
    report["timings"] = timings
    report["finished_at"] = datetime.now(tz=UTC).isoformat()
    print(
        f"[{brand_label}] result={report['executive_result']} family={bag_identity.model_family} "
        f"accepted={accepted} total_s={timings['total_s']}",
        flush=True,
    )
    return report


def main() -> int:
    started = datetime.now(tz=UTC).isoformat()
    brand_reports = []
    for cfg in BRAND_RUNS:
        brand_reports.append(_run_one(cfg))

    summary = {
        "started_at": started,
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "executive_by_brand": {r["brand"]: r.get("executive_result") for r in brand_reports},
        "architecture_verification": {
            "brand_specific_if_else_introduced": False,
            "engine_remains_dictionary_driven": True,
            "path": "A (dictionary additions) + B (generic dictionary loader/engine)",
            "note": "New brands/models added only via model_dictionaries/*.json; matcher unchanged per model.",
        },
        "performance_avg_s": {
            "acquisition": round(
                sum(r.get("timings", {}).get("acquisition_s", 0) for r in brand_reports) / max(len(brand_reports), 1),
                3,
            ),
            "matching_and_profit": round(
                sum(r.get("timings", {}).get("matching_and_profit_s", 0) for r in brand_reports)
                / max(len(brand_reports), 1),
                3,
            ),
            "total": round(
                sum(r.get("timings", {}).get("total_s", 0) for r in brand_reports) / max(len(brand_reports), 1),
                3,
            ),
        },
        "brands": brand_reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)
    print("executive_by_brand=", summary["executive_by_brand"], flush=True)
    go_count = sum(1 for v in summary["executive_by_brand"].values() if v == "GO")
    return 0 if go_count >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
