"""Trace Yahoo + Mercari domestic comparable search per imported overseas product.

Bypasses workspace eligibility so ineligible Bag rows still exercise the domestic pipeline.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.profit_bridge import _convert
from marketplace.browser_acquisition.comparable_matching import (
    RejectionReason,
    evaluate_comparables,
)
from marketplace.browser_acquisition.mercari_acquirer import MercariAcquirer
from marketplace.browser_acquisition.mercari_comparable import select_best_mercari_comparable
from marketplace.browser_acquisition.mercari_search_queries import build_mercari_search_queries
from marketplace.browser_acquisition.models import YahooSoldSample
from marketplace.browser_acquisition.yahoo_comparable import select_best_yahoo_comparable
from marketplace.browser_acquisition.yahoo_open_acquirer import YahooOpenAcquirer
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer
from profit_discovery.discovery_validation.batch_profit.converters import candidate_to_acquired_listing

FILTER_REASONS = {
    RejectionReason.HARD_EXCLUSION.value,
    RejectionReason.ACCESSORY_ONLY.value,
    RejectionReason.BRAND_MISMATCH.value,
    RejectionReason.CATEGORY_MISMATCH.value,
    RejectionReason.SUBTYPE_MISMATCH.value,
    RejectionReason.MATERIAL_MISMATCH.value,
    RejectionReason.MODEL_NUMBER_MISMATCH.value,
}

AUDIT_DBS = (
    ("Fashionphile", Path("data/_ops_audit_pipeline/Fashionphile.db")),
    ("Rebag", Path("data/_ops_audit_pipeline/Rebag_bag.db")),
    ("Rebag_seed", Path("data/_ops_audit_pipeline/Rebag.db")),
    ("The RealReal", Path("data/_ops_audit_pipeline/RealReal_bag.db")),
    ("The RealReal seed", Path("data/_ops_audit_pipeline/The_RealReal.db")),
    ("Vestiaire Collective", Path("data/_ops_audit_pipeline/Vestiaire_bag.db")),
    ("Vestiaire Collective seed", Path("data/_ops_audit_pipeline/Vestiaire_Collective.db")),
)

OUT_JSON = Path("output/domestic_comparable_trace.json")
OUT_MD = Path("output/domestic_comparable_trace.md")


@dataclass
class MarketplaceTrace:
    search_executed: bool
    queries: list[str] = field(default_factory=list)
    candidates: int = 0
    after_filtering: int = 0
    after_matching: int = 0
    median_sold_price_jpy: int | None = None
    final_selected: dict | None = None
    failure_stage: str | None = None
    failure_detail: str = ""
    top_rejection_reasons: list[tuple[str, int]] = field(default_factory=list)
    error: str = ""


@dataclass
class ProductTrace:
    marketplace: str
    database: str
    batch_id: str
    candidate_id: str
    title: str
    brand: str
    category: str
    detected_subtype: str
    purchase_url: str
    eligible_for_profit_check: bool
    quality_warnings: list[str]
    profit_path_note: str
    yahoo: MarketplaceTrace
    mercari: MarketplaceTrace
    overall_failure_stage: str
    overall_failure_detail: str


def _stage_counts(purchase, samples: list[YahooSoldSample], purchase_price_jpy) -> tuple[int, int, int, int | None, object, list[tuple[str, int]]]:
    if not samples:
        return 0, 0, 0, None, None, []
    result = evaluate_comparables(purchase, samples, purchase_price_jpy=purchase_price_jpy)
    candidates = result.raw_sample_count
    after_filtering = 0
    reason_counts: dict[str, int] = {}
    for diag in result.rejected_diagnostics:
        reasons = set(diag.rejection_reasons)
        reason_counts[diag.rejection_reasons[0] if diag.rejection_reasons else "UNKNOWN"] = (
            reason_counts.get(diag.rejection_reasons[0] if diag.rejection_reasons else "UNKNOWN", 0) + 1
        )
        if reasons & FILTER_REASONS:
            continue
        after_filtering += 1
    after_filtering += len(result.accepted_diagnostics)
    after_matching = len(result.matched_samples)
    median_price = int(result.median_jpy) if result.median_jpy and after_matching else None
    if median_price is None and after_matching:
        prices = [s.sold_price_jpy for s in result.matched_samples if s.sold_price_jpy > 0]
        median_price = int(median(prices)) if prices else None
    top_reasons = sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    return candidates, after_filtering, after_matching, median_price, result, top_reasons


def _failure_stage(
    *,
    search_executed: bool,
    queries: list[str],
    candidates: int,
    after_filtering: int,
    after_matching: int,
    final_selected,
    error: str = "",
) -> tuple[str | None, str]:
    if final_selected is not None:
        return None, ""
    if error:
        return "search_execution_error", error
    if not search_executed:
        return "search_not_executed", "Domestic search was not invoked"
    if not queries:
        return "query_generation", "No search queries were generated"
    if candidates == 0:
        return "candidates", "Search ran but returned 0 listing candidates"
    if after_filtering == 0:
        return "filtering", "Candidates existed but all were removed by hard filters"
    if after_matching == 0:
        return "matching", "Candidates survived filters but none met matching score/threshold"
    return "selection", "Matched samples existed but no final comparable was selected"


def _selected_payload(best) -> dict | None:
    if best is None:
        return None
    return {
        "title": best.title,
        "price_jpy": best.price_jpy,
        "url": best.url,
        "matching_score": best.matching_score,
        "condition": best.condition,
        "matched_attributes": best.matched_attributes,
    }


def trace_yahoo(
    *,
    purchase,
    batch_candidate,
    sold_acquirer: YahooSoldAcquirer,
    open_acquirer: YahooOpenAcquirer,
) -> MarketplaceTrace:
    queries = build_yahoo_search_queries(
        title=batch_candidate.title,
        brand=batch_candidate.brand,
        category=batch_candidate.category,
    )[:3]
    samples: list[YahooSoldSample] = []
    error = ""
    search_executed = False
    try:
        search_executed = True
        sold_samples, used_queries, _ = sold_acquirer.acquire_multi(
            title=batch_candidate.title,
            brand=batch_candidate.brand,
            category=batch_candidate.category,
            queries=list(queries),
        )
        if used_queries:
            queries = list(used_queries)
        samples = list(sold_samples)
        if not samples:
            open_samples, open_queries = open_acquirer.acquire_multi(
                title=batch_candidate.title,
                brand=batch_candidate.brand,
                category=batch_candidate.category,
                queries=list(queries),
            )
            if open_queries and not queries:
                queries = list(open_queries)
            samples = list(open_samples)
    except Exception as exc:  # noqa: BLE001 - trace must continue
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    candidates, after_filtering, after_matching, median_price, comparable, top_reasons = _stage_counts(
        purchase, samples, batch_candidate.purchase_price_jpy
    )
    best = None
    if comparable is not None:
        best = select_best_yahoo_comparable(
            purchase,
            comparable,
            candidate_samples=samples,
        )
    selected = _selected_payload(best)
    stage, detail = _failure_stage(
        search_executed=search_executed,
        queries=queries,
        candidates=candidates,
        after_filtering=after_filtering,
        after_matching=after_matching,
        final_selected=selected,
        error=error,
    )
    return MarketplaceTrace(
        search_executed=search_executed and not bool(error),
        queries=list(queries),
        candidates=candidates,
        after_filtering=after_filtering,
        after_matching=after_matching,
        median_sold_price_jpy=median_price,
        final_selected=selected,
        failure_stage=stage,
        failure_detail=detail,
        top_rejection_reasons=top_reasons,
        error=error,
    )


def trace_mercari(*, purchase, batch_candidate, mercari_acquirer: MercariAcquirer) -> MarketplaceTrace:
    queries = build_mercari_search_queries(
        title=batch_candidate.title,
        brand=batch_candidate.brand,
        category=batch_candidate.category,
    )[:3]
    samples: list[YahooSoldSample] = []
    error = ""
    search_executed = False
    try:
        search_executed = True
        samples, used_queries = mercari_acquirer.acquire_multi(
            title=batch_candidate.title,
            brand=batch_candidate.brand,
            category=batch_candidate.category,
            queries=list(queries),
        )
        if used_queries:
            queries = list(used_queries)
        samples = list(samples)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    candidates, after_filtering, after_matching, median_price, comparable, top_reasons = _stage_counts(
        purchase, samples, batch_candidate.purchase_price_jpy
    )
    best = None
    if comparable is not None:
        best = select_best_mercari_comparable(
            purchase,
            comparable,
            candidate_samples=samples,
        )
    selected = _selected_payload(best)
    stage, detail = _failure_stage(
        search_executed=search_executed,
        queries=queries,
        candidates=candidates,
        after_filtering=after_filtering,
        after_matching=after_matching,
        final_selected=selected,
        error=error,
    )
    return MarketplaceTrace(
        search_executed=search_executed and not bool(error),
        queries=list(queries),
        candidates=candidates,
        after_filtering=after_filtering,
        after_matching=after_matching,
        median_sold_price_jpy=median_price,
        final_selected=selected,
        failure_stage=stage,
        failure_detail=detail,
        top_rejection_reasons=top_reasons,
        error=error,
    )


def _overall_failure(yahoo: MarketplaceTrace, mercari: MarketplaceTrace) -> tuple[str, str]:
    if yahoo.final_selected or mercari.final_selected:
        return "", ""
    # Prefer earliest shared failure; otherwise report both.
    order = (
        "search_not_executed",
        "search_execution_error",
        "query_generation",
        "candidates",
        "filtering",
        "matching",
        "selection",
    )
    stages = [s for s in (yahoo.failure_stage, mercari.failure_stage) if s]
    if not stages:
        return "unknown", "No comparable produced for unknown reason"
    earliest = min(stages, key=lambda s: order.index(s) if s in order else 99)
    detail = (
        f"Yahoo failed at {yahoo.failure_stage or 'n/a'} ({yahoo.failure_detail or yahoo.error or 'n/a'}); "
        f"Mercari failed at {mercari.failure_stage or 'n/a'} ({mercari.failure_detail or mercari.error or 'n/a'})"
    )
    return earliest, detail


def load_products() -> list[tuple[str, str, object]]:
    products: list[tuple[str, str, object]] = []
    seen: set[str] = set()
    for marketplace, path in AUDIT_DBS:
        if not path.exists():
            continue
        repo = AcquisitionWorkspaceRepository(database_path=path)
        for batch in repo.list_batches():
            _, candidates = repo.get_batch(batch.workspace_batch_id)
            for candidate in candidates:
                key = f"{candidate.purchase_url}|{candidate.title}|{marketplace.split()[0]}"
                if key in seen:
                    continue
                seen.add(key)
                products.append((marketplace, str(path), candidate))
    return products


def render_md(traces: list[ProductTrace], *, started_at: str, finished_at: str) -> str:
    lines = [
        "# Domestic comparable search trace",
        "",
        f"- Started: {started_at}",
        f"- Finished: {finished_at}",
        f"- Products traced: {len(traces)}",
        "",
        "Eligibility note: workspace profit selection requires `category in {Wallet}` "
        "(`SUPPORTED_LIVE_CATEGORIES`). Bag imports were ineligible, so the operational "
        "profit path never invoked domestic search. This report force-runs Yahoo/Mercari "
        "for each imported product anyway.",
        "",
    ]
    for idx, item in enumerate(traces, start=1):
        lines.extend(
            [
                f"## {idx}. [{item.marketplace}] {item.title}",
                "",
                f"- Candidate ID: `{item.candidate_id}`",
                f"- Brand / category / subtype: {item.brand} / {item.category} / {item.detected_subtype}",
                f"- Eligible for profit check: {item.eligible_for_profit_check}",
                f"- Quality warnings: {', '.join(item.quality_warnings) or '(none)'}",
                f"- Profit-path note: {item.profit_path_note}",
                f"- Overall no-comparable stage: {item.overall_failure_stage or 'comparable produced'}",
                f"- Overall detail: {item.overall_failure_detail or 'n/a'}",
                "",
                "### Yahoo! Auctions",
                "",
                f"- Search executed?: {item.yahoo.search_executed}",
                f"- Query used: {item.yahoo.queries or '(none)'}",
                f"- Number of candidates: {item.yahoo.candidates}",
                f"- Number after filtering: {item.yahoo.after_filtering}",
                f"- Number after matching: {item.yahoo.after_matching}",
                f"- Median sold price: {item.yahoo.median_sold_price_jpy if item.yahoo.median_sold_price_jpy is not None else 'n/a'}",
                f"- Final selected comparable: {json.dumps(item.yahoo.final_selected, ensure_ascii=False) if item.yahoo.final_selected else 'none'}",
                f"- Failure stage: {item.yahoo.failure_stage or 'none'}",
                f"- Failure detail: {item.yahoo.failure_detail or item.yahoo.error or 'n/a'}",
                f"- Top rejection reasons: {item.yahoo.top_rejection_reasons}",
                "",
                "### Mercari",
                "",
                f"- Search executed?: {item.mercari.search_executed}",
                f"- Query used: {item.mercari.queries or '(none)'}",
                f"- Number of candidates: {item.mercari.candidates}",
                f"- Number after filtering: {item.mercari.after_filtering}",
                f"- Number after matching: {item.mercari.after_matching}",
                f"- Median sold price: {item.mercari.median_sold_price_jpy if item.mercari.median_sold_price_jpy is not None else 'n/a'}",
                f"- Final selected comparable: {json.dumps(item.mercari.final_selected, ensure_ascii=False) if item.mercari.final_selected else 'none'}",
                f"- Failure stage: {item.mercari.failure_stage or 'none'}",
                f"- Failure detail: {item.mercari.failure_detail or item.mercari.error or 'n/a'}",
                f"- Top rejection reasons: {item.mercari.top_rejection_reasons}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    started_at = datetime.now(tz=UTC).isoformat()
    products = load_products()
    print(f"Loaded {len(products)} imported products", flush=True)

    sold = YahooSoldAcquirer()
    open_acq = YahooOpenAcquirer()
    mercari = MercariAcquirer()
    traces: list[ProductTrace] = []

    for index, (marketplace, database, candidate) in enumerate(products, start=1):
        print(f"[{index}/{len(products)}] {marketplace}: {candidate.title[:70]}", flush=True)
        batch_candidate = _convert(candidate)
        purchase = candidate_to_acquired_listing(batch_candidate)
        profit_path_note = (
            "Ops profit path skipped domestic search because candidate was not eligible/selected "
            "(CATEGORY_NOT_SUPPORTED_FOR_LIVE_PROFIT / non-Wallet)."
            if not candidate.eligible_for_profit_check
            else "Eligible; domestic search would run when selected."
        )
        yahoo = trace_yahoo(
            purchase=purchase,
            batch_candidate=batch_candidate,
            sold_acquirer=sold,
            open_acquirer=open_acq,
        )
        mercari_trace = trace_mercari(
            purchase=purchase,
            batch_candidate=batch_candidate,
            mercari_acquirer=mercari,
        )
        # Also compute combined final selection like batch pipeline
        yahoo_best = yahoo.final_selected
        mercari_best = mercari_trace.final_selected
        if yahoo_best or mercari_best:
            # keep per-market traces; overall only fails if both empty
            pass
        overall_stage, overall_detail = _overall_failure(yahoo, mercari_trace)
        traces.append(
            ProductTrace(
                marketplace=marketplace,
                database=database,
                batch_id=candidate.workspace_batch_id,
                candidate_id=candidate.candidate_id,
                title=candidate.title,
                brand=candidate.brand,
                category=candidate.category,
                detected_subtype=candidate.detected_subtype,
                purchase_url=candidate.purchase_url,
                eligible_for_profit_check=candidate.eligible_for_profit_check,
                quality_warnings=list(candidate.validation_warnings),
                profit_path_note=profit_path_note,
                yahoo=yahoo,
                mercari=mercari_trace,
                overall_failure_stage=overall_stage,
                overall_failure_detail=overall_detail,
            )
        )
        # Incremental save so partial progress survives long runs
        payload = {
            "started_at": started_at,
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "products": [asdict(item) for item in traces],
        }
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    finished_at = datetime.now(tz=UTC).isoformat()
    OUT_MD.write_text(render_md(traces, started_at=started_at, finished_at=finished_at), encoding="utf-8")
    payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "product_count": len(traces),
        "products": [asdict(item) for item in traces],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON} and {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
