"""Batch real profit discovery pipeline."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from marketplace.browser_acquisition.comparable_matching import (
    COMPARABLE_SCORE_THRESHOLD,
    NEAR_MISS_SCORE_THRESHOLD,
    evaluate_comparables,
    format_comparable_diagnostics,
)
from marketplace.browser_acquisition.comparable_candidate import (
    candidate_from_best_comparable,
    select_best_comparable_candidate,
)
from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError
from marketplace.browser_acquisition.mercari_acquirer import MercariAcquirer
from marketplace.browser_acquisition.mercari_comparable import (
    MERCARI_MARKETPLACE,
    YAHOO_MARKETPLACE,
    select_best_mercari_comparable,
)
from marketplace.browser_acquisition.models import AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.comparable_quality import (
    apply_publish_gate,
    classify_comparable_quality,
    filter_estimation_samples,
)
from marketplace.browser_acquisition.rate_limit import RateLimiter
from marketplace.browser_acquisition.yahoo_comparable import select_best_yahoo_comparable
from marketplace.browser_acquisition.yahoo_open_acquirer import YahooOpenAcquirer
from marketplace.browser_acquisition.yahoo_search_cache import (
    build_cache_entry,
    cache_age_hours,
    normalize_query,
)
from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION
from marketplace.browser_acquisition.domestic_search_queries import build_domestic_search_queries
from marketplace.browser_acquisition.yahoo_search_queries import (
    MAX_SEARCH_QUERIES,
    build_yahoo_search_queries,
)
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_discovery.buy_decision_engine import BuyDecisionEngine
from profit_discovery.discovery_validation.batch_profit.condition import detect_condition, is_condition_excluded
from profit_discovery.discovery_validation.batch_profit.converters import (
    candidate_to_acquired_listing,
    candidate_to_market_listing,
)
from profit_discovery.discovery_validation.batch_profit.costs import CostProfile, compute_estimated_costs
from profit_discovery.discovery_validation.batch_profit.decisions import assign_batch_decision
from profit_discovery.discovery_validation.batch_profit.domestic_search_trace import (
    DomesticComparableTrace,
    DomesticFailureStage,
    build_marketplace_trace,
    build_selection_trace,
    resolve_overall_failure,
)
from profit_discovery.discovery_validation.batch_profit.models import (
    BatchDisplayDecision,
    BatchProfitCandidate,
    BatchProfitResult,
    BatchProfitRun,
    BatchRunStatus,
    BatchRunSummary,
    YahooDataSource,
)
from profit_discovery.discovery_validation.batch_profit.ranking import rank_batch_results
from profit_discovery.discovery_validation.batch_profit.robust_estimate import build_robust_domestic_estimate
from profit_discovery.discovery_validation.real_profit_models import DataStatus
from profit_discovery.discovery_validation.validator import ProfitValidationValidator
from profit_discovery.discovery_validation.yahoo_live_domestic import (
    format_accepted_comparables,
    format_rejected_samples,
)
from profit_intelligence.discovery_engine import DiscoveryEngine
from profit_intelligence.normalization import clamp_score
from supplier.models import to_product_candidate
from marketplace.importers.converters import market_listing_to_supplier_product

DEFAULT_CANDIDATE_LIMIT = 10
HARD_CANDIDATE_MAX = 20


class CachedYahooSearchService:
    """Yahoo search with cache, rate limiting, and query dedupe."""

    def __init__(
        self,
        *,
        cache_repository,
        yahoo_acquirer: YahooSoldAcquirer | None = None,
        use_cache: bool = True,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._cache = cache_repository
        self._acquirer = yahoo_acquirer or YahooSoldAcquirer()
        self._use_cache = use_cache
        self._rate_limiter = rate_limiter or RateLimiter()
        self.live_requests = 0
        self.cache_hits = 0
        self._query_cache: dict[str, tuple[list[YahooSoldSample], str, str, float | None]] = {}

    def fetch_for_candidate(
        self,
        *,
        title: str,
        brand: str,
        category: str,
        html_by_query: dict[str, str] | None = None,
        queries: tuple[str, ...] | None = None,
    ) -> tuple[list[YahooSoldSample], tuple[str, ...], str, str, float | None, list]:
        if queries is None:
            queries = tuple(
                build_yahoo_search_queries(title=title, brand=brand, category=category)[:MAX_SEARCH_QUERIES]
            )
        else:
            queries = tuple(queries[:MAX_SEARCH_QUERIES])
        if html_by_query:
            matched = [query for query in queries if query in html_by_query]
            queries = tuple(matched[:MAX_SEARCH_QUERIES] or list(html_by_query.keys())[:MAX_SEARCH_QUERIES])
        merged: list[YahooSoldSample] = []
        seen: set[str] = set()
        yahoo_source = YahooDataSource.UNAVAILABLE.value
        cache_retrieved_at = ""
        cache_age: float | None = None
        all_diagnostics = []

        for query in queries:
            normalized = normalize_query(query)
            if normalized in self._query_cache:
                samples, source, retrieved_at, age = self._query_cache[normalized]
                self.cache_hits += 1
                yahoo_source = source
                cache_retrieved_at = retrieved_at
                cache_age = age
            else:
                html = (html_by_query or {}).get(query)
                if html is not None:
                    result = self._acquirer.acquire(search_terms=query, html=html)
                    samples = list(result.samples)
                    source = YahooDataSource.LIVE.value
                    retrieved_at = datetime.now(tz=UTC).isoformat()
                    age = None
                    self.live_requests += 1
                elif self._use_cache:
                    cached = self._cache.get(query)
                    if cached is not None:
                        samples = list(cached.samples)
                        source = YahooDataSource.LIVE_CACHE.value
                        retrieved_at = cached.retrieved_at
                        age = cache_age_hours(cached.retrieved_at)
                        self.cache_hits += 1
                    else:
                        samples, source, retrieved_at, age = self._fetch_live(query)
                else:
                    samples, source, retrieved_at, age = self._fetch_live(query)
                self._query_cache[normalized] = (samples, source, retrieved_at, age)

            all_diagnostics.extend(self._acquirer.last_diagnostics)
            for sample in samples:
                key = f"{sample.title}|{sample.sold_price_jpy}"
                if key in seen:
                    continue
                if is_condition_excluded(sample.title):
                    continue
                seen.add(key)
                merged.append(sample)
                if len(merged) >= 20:
                    break
            if len(merged) >= 20:
                break
            if yahoo_source == YahooDataSource.UNAVAILABLE.value and samples:
                yahoo_source = source
                cache_retrieved_at = retrieved_at
                cache_age = age

        if merged and yahoo_source == YahooDataSource.UNAVAILABLE.value:
            yahoo_source = YahooDataSource.LIVE.value
        return merged[:20], queries, yahoo_source, cache_retrieved_at, cache_age, all_diagnostics

    def _fetch_live(self, query: str) -> tuple[list[YahooSoldSample], str, str, float | None]:
        self._rate_limiter.wait()
        try:
            result = self._acquirer.acquire(search_terms=query)
        except AcquisitionBlockedError:
            return [], YahooDataSource.UNAVAILABLE.value, "", None
        except Exception:
            # Launch/network failures: keep query list at caller; mark unavailable.
            return [], YahooDataSource.UNAVAILABLE.value, "", None
        samples = list(result.samples)
        retrieved_at = datetime.now(tz=UTC).isoformat()
        if result.status == AcquisitionStatus.LIVE and samples:
            entry = build_cache_entry(
                query=query,
                samples=samples,
                diagnostics=self._acquirer.last_diagnostics,
            )
            self._cache.save(entry)
        self.live_requests += 1
        source = YahooDataSource.LIVE.value if samples else YahooDataSource.UNAVAILABLE.value
        return samples, source, retrieved_at, None


def run_batch_profit(
    candidates: list[BatchProfitCandidate],
    *,
    cost_profile: CostProfile,
    use_cache: bool = True,
    cache_repository=None,
    yahoo_acquirer: YahooSoldAcquirer | None = None,
    mercari_acquirer: MercariAcquirer | None = None,
    html_by_query: dict[str, str] | None = None,
    open_html_by_query: dict[str, str] | None = None,
    mercari_html_by_query: dict[str, str] | None = None,
    import_errors: tuple[str, ...] = (),
) -> BatchProfitRun:
    """Run batch profit discovery for multiple candidates."""
    started_at = datetime.now(tz=UTC)
    batch_id = f"batch-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    if cache_repository is None:
        from app.storage.yahoo_cache_repository import YahooSearchCacheRepository

        cache_repository = YahooSearchCacheRepository()

    search_service = CachedYahooSearchService(
        cache_repository=cache_repository,
        yahoo_acquirer=yahoo_acquirer,
        use_cache=use_cache,
    )
    open_acquirer = YahooOpenAcquirer()
    mercari = mercari_acquirer or MercariAcquirer()
    calculator = ProfitCalculator()
    discovery_engine = DiscoveryEngine()
    buy_engine = BuyDecisionEngine()
    validator = ProfitValidationValidator()

    results: list[BatchProfitResult] = []
    counters = {
        BatchDisplayDecision.STRONG_CANDIDATE.value: 0,
        BatchDisplayDecision.REVIEW.value: 0,
        BatchDisplayDecision.HOLD.value: 0,
        BatchDisplayDecision.REJECT.value: 0,
        BatchDisplayDecision.DATA_INSUFFICIENT.value: 0,
        BatchDisplayDecision.BLOCKED.value: 0,
    }
    failed_count = 0

    for candidate in candidates:
        try:
            result = _process_candidate(
                candidate=candidate,
                search_service=search_service,
                open_acquirer=open_acquirer,
                mercari_acquirer=mercari,
                calculator=calculator,
                discovery_engine=discovery_engine,
                buy_engine=buy_engine,
                validator=validator,
                cost_profile=cost_profile,
                html_by_query=html_by_query,
                open_html_by_query=open_html_by_query,
                mercari_html_by_query=mercari_html_by_query,
            )
        except Exception as exc:
            failed_count += 1
            result = _failed_result(candidate, reason=f"{type(exc).__name__}: {exc}")
        counters[result.batch_decision] = counters.get(result.batch_decision, 0) + 1
        results.append(result)

    ranked = rank_batch_results(results)
    completed_at = datetime.now(tz=UTC)
    summary = BatchRunSummary(
        batch_id=batch_id,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        total_candidates=len(candidates),
        processed_count=len(ranked),
        strong_candidate_count=counters.get(BatchDisplayDecision.STRONG_CANDIDATE.value, 0),
        review_count=counters.get(BatchDisplayDecision.REVIEW.value, 0),
        hold_count=counters.get(BatchDisplayDecision.HOLD.value, 0),
        reject_count=counters.get(BatchDisplayDecision.REJECT.value, 0),
        failed_count=failed_count,
        blocked_count=counters.get(BatchDisplayDecision.BLOCKED.value, 0),
        total_yahoo_requests=search_service.live_requests,
        cache_hits=search_service.cache_hits,
        exchange_rate=f"{cost_profile.active_exchange_rate():g} JPY/USD",
        cost_profile=cost_profile.profile_name,
        status=BatchRunStatus.COMPLETED.value if ranked else BatchRunStatus.FAILED.value,
        import_errors=import_errors,
    )
    return BatchProfitRun(summary=summary, results=tuple(ranked))


def _process_candidate(
    *,
    candidate: BatchProfitCandidate,
    search_service: CachedYahooSearchService,
    open_acquirer: YahooOpenAcquirer,
    mercari_acquirer: MercariAcquirer,
    calculator: ProfitCalculator,
    discovery_engine: DiscoveryEngine,
    buy_engine: BuyDecisionEngine,
    validator: ProfitValidationValidator,
    cost_profile: CostProfile,
    html_by_query: dict[str, str] | None,
    open_html_by_query: dict[str, str] | None,
    mercari_html_by_query: dict[str, str] | None,
) -> BatchProfitResult:
    listing = candidate_to_market_listing(candidate)
    purchase = candidate_to_acquired_listing(candidate)
    yahoo_error = ""
    mercari_error = ""
    mercari_queries: list[str] = []
    yahoo_request_status = "NOT_EXECUTED"
    mercari_request_status = "NOT_EXECUTED"
    yahoo_search_executed = False
    mercari_search_executed = False

    # Generate queries BEFORE acquisition so failures never wipe the query list.
    query_generation = build_domestic_search_queries(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
    )
    planned_queries = tuple(query_generation.query_strings[:MAX_SEARCH_QUERIES])
    queries: tuple[str, ...] = planned_queries

    try:
        samples, queries, yahoo_source, cache_retrieved_at, cache_age, _diagnostics = search_service.fetch_for_candidate(
            title=candidate.title,
            brand=candidate.brand,
            category=candidate.category,
            html_by_query=html_by_query,
            queries=planned_queries,
        )
        if not queries and planned_queries:
            queries = planned_queries
        yahoo_search_executed = True
        yahoo_request_status = yahoo_source
    except Exception as exc:  # noqa: BLE001 - continue tracing on marketplace failure
        samples, yahoo_source, cache_retrieved_at, cache_age = [], YahooDataSource.UNAVAILABLE.value, "", None
        queries = planned_queries  # preserve generated queries for auditability
        yahoo_error = f"{type(exc).__name__}: {exc}"
        yahoo_request_status = "REQUEST_FAILED"

    open_samples: list[YahooSoldSample] = []
    open_queries: list[str] = []
    try:
        if open_html_by_query:
            open_samples, open_queries = open_acquirer.acquire_multi(
                title=candidate.title,
                brand=candidate.brand,
                category=candidate.category,
                queries=list(queries),
                html_by_query=open_html_by_query,
            )
        elif html_by_query is None:
            open_samples, open_queries = open_acquirer.acquire_multi(
                title=candidate.title,
                brand=candidate.brand,
                category=candidate.category,
                queries=list(queries),
            )
        if open_queries and not queries:
            queries = tuple(open_queries)
    except Exception as exc:  # noqa: BLE001
        open_samples = []
        if not yahoo_error:
            yahoo_error = f"open_acquire: {type(exc).__name__}: {exc}"

    mercari_samples: list[YahooSoldSample] = []
    try:
        if mercari_html_by_query:
            mercari_samples, mercari_queries = mercari_acquirer.acquire_multi(
                title=candidate.title,
                brand=candidate.brand,
                category=candidate.category,
                queries=list(queries) if queries else None,
                html_by_query=mercari_html_by_query,
            )
            mercari_search_executed = True
            mercari_request_status = "LIVE_HTML" if mercari_samples else "LIVE_HTML_EMPTY"
        elif html_by_query is None:
            mercari_samples, mercari_queries = mercari_acquirer.acquire_multi(
                title=candidate.title,
                brand=candidate.brand,
                category=candidate.category,
                queries=list(planned_queries) if planned_queries else (list(queries) if queries else None),
            )
            if not mercari_queries and planned_queries:
                mercari_queries = list(planned_queries)
            mercari_search_executed = True
            mercari_request_status = "LIVE" if mercari_samples else "LIVE_EMPTY"
        else:
            mercari_request_status = "SKIPPED_FIXTURE_MODE_WITHOUT_MERCARI_HTML"
    except Exception as exc:  # noqa: BLE001
        mercari_samples = []
        mercari_queries = list(planned_queries) if planned_queries else list(queries)
        mercari_error = f"{type(exc).__name__}: {exc}"
        mercari_request_status = "REQUEST_FAILED"

    failure_reason = ""
    yahoo_fallback = ""
    # Phase 2: sold-price only — never use open/active asking prices for estimates.
    sold_yahoo, yahoo_filter_counts = filter_estimation_samples(
        samples,
        purchase_price_jpy=candidate.purchase_price_jpy,
    )
    sold_mercari, mercari_filter_counts = filter_estimation_samples(
        mercari_samples,
        purchase_price_jpy=candidate.purchase_price_jpy,
    )
    filter_counts = {
        "junk_excluded": yahoo_filter_counts.get("junk_excluded", 0)
        + mercari_filter_counts.get("junk_excluded", 0),
        "active_excluded": yahoo_filter_counts.get("active_excluded", 0)
        + mercari_filter_counts.get("active_excluded", 0)
        + len(open_samples),
        "unknown_excluded": yahoo_filter_counts.get("unknown_excluded", 0)
        + mercari_filter_counts.get("unknown_excluded", 0),
        "suspicious_low_excluded": yahoo_filter_counts.get("suspicious_low_excluded", 0)
        + mercari_filter_counts.get("suspicious_low_excluded", 0),
        "sold_kept": yahoo_filter_counts.get("sold_kept", 0)
        + mercari_filter_counts.get("sold_kept", 0),
    }
    profit_samples = sold_yahoo
    if not profit_samples and not sold_mercari:
        failure_reason = "Yahoo sold data unavailable"

    comparable = evaluate_comparables(
        purchase,
        profit_samples,
        purchase_price_jpy=candidate.purchase_price_jpy,
    )
    yahoo_sold_comparable = comparable
    diagnostics_json = format_comparable_diagnostics(comparable)
    domestic = build_robust_domestic_estimate(
        raw_sample_count=comparable.raw_sample_count,
        accepted_samples=comparable.matched_samples,
        rejected_count=comparable.rejected_count,
        comparable_warning=comparable.data_warning,
        outlier_notes=comparable.outlier_exclusions,
    )

    # Prefer open-auction best match for detail display only (not for price estimate).
    display_comparable = comparable
    display_samples: list[YahooSoldSample] = list(profit_samples)
    if open_samples:
        open_comparable = evaluate_comparables(
            purchase,
            open_samples,
            purchase_price_jpy=candidate.purchase_price_jpy,
        )
        display_comparable = open_comparable
        display_samples = list(open_samples)
    yahoo_best = select_best_yahoo_comparable(
        purchase,
        display_comparable,
        min_score=COMPARABLE_SCORE_THRESHOLD,
        candidate_samples=display_samples,
    )
    # Near-miss open comps remain display-only; do not rebuild domestic from them.
    if yahoo_best is None and open_samples:
        yahoo_best = select_best_yahoo_comparable(
            purchase,
            display_comparable,
            min_score=NEAR_MISS_SCORE_THRESHOLD,
            candidate_samples=open_samples,
        )
        if yahoo_best is not None:
            yahoo_fallback = yahoo_fallback or "yahoo_near_miss_display_only"

    mercari_comparable = evaluate_comparables(
        purchase,
        sold_mercari,
        purchase_price_jpy=candidate.purchase_price_jpy,
    )
    mercari_best = select_best_mercari_comparable(
        purchase,
        mercari_comparable,
        min_score=COMPARABLE_SCORE_THRESHOLD,
        candidate_samples=sold_mercari,
    )
    if mercari_best is None and sold_mercari:
        mercari_best = select_best_mercari_comparable(
            purchase,
            mercari_comparable,
            min_score=NEAR_MISS_SCORE_THRESHOLD,
            candidate_samples=sold_mercari,
        )
        if mercari_best is not None and not yahoo_fallback:
            yahoo_fallback = "mercari_near_miss_display_only"

    selected = select_best_comparable_candidate(
        [
            candidate_from_best_comparable(yahoo_best, marketplace=YAHOO_MARKETPLACE),
            candidate_from_best_comparable(mercari_best, marketplace=MERCARI_MARKETPLACE),
        ]
    )
    best = selected.source if selected is not None else None
    marketplace = selected.marketplace if selected is not None else ""
    if marketplace == MERCARI_MARKETPLACE and mercari_best is not None:
        if mercari_comparable.matched_samples:
            comparable = mercari_comparable
            diagnostics_json = format_comparable_diagnostics(comparable)
            domestic = build_robust_domestic_estimate(
                raw_sample_count=comparable.raw_sample_count,
                accepted_samples=comparable.matched_samples,
                rejected_count=comparable.rejected_count,
                comparable_warning=comparable.data_warning,
                outlier_notes=comparable.outlier_exclusions,
            )
            yahoo_source = YahooDataSource.LIVE.value
            failure_reason = ""
        # Do not rebuild domestic from a single near-miss Mercari asking/sold sample.
    elif marketplace == YAHOO_MARKETPLACE:
        marketplace = YAHOO_MARKETPLACE if best is not None else ""
    elif best is not None and not marketplace:
        marketplace = YAHOO_MARKETPLACE

    quality_report = classify_comparable_quality(
        purchase_price_jpy=candidate.purchase_price_jpy,
        accepted_samples=comparable.matched_samples,
        accepted_diagnostics=comparable.accepted_diagnostics,
        comparable_warning=comparable.data_warning,
        filter_counts=filter_counts,
    )
    raw_recommended = domestic.recommended_selling_estimate_jpy
    selling_price = apply_publish_gate(raw_recommended, quality_report)
    if not quality_report.publish_price:
        domestic = replace(
            domestic,
            recommended_selling_estimate_jpy=Decimal("0"),
            comparable_warning=comparable.data_warning
            or (
                "COMPARABLE_DATA_SUSPECT"
                if quality_report.quality == "SUSPECT"
                else "COMPARABLE_DATA_INSUFFICIENT"
            ),
        )
        if quality_report.quality == "SUSPECT" and not comparable.data_warning:
            # ComparableEstimateResult may not be a dataclass.replace target on all paths;
            # keep warning on domestic which drives decisions.
            pass

    profit_failure_stage = None
    profit_failure_detail = ""
    try:
        if selling_price <= 0:
            raise ValueError("selling estimate unpublished due to comparable quality gate")
        supplier_product = market_listing_to_supplier_product(listing)
        product_candidate = to_product_candidate(supplier_product)
        derived_rate = (
            float(candidate.purchase_price_jpy / candidate.purchase_price)
            if candidate.purchase_price > 0 and candidate.purchase_price_jpy > 0
            else cost_profile.active_exchange_rate()
        )
        product = Product(
            name=str(product_candidate["name"]),
            brand=str(product_candidate["brand"]),
            price=float(product_candidate["purchase_price"]),
            currency=str(product_candidate["currency"]),
            store_name=str(product_candidate["source"]),
            url=str(product_candidate.get("url") or ""),
            model=str(product_candidate.get("model_number") or ""),
            exchange_rate=derived_rate,
        )
        gross_result = calculator.calculate(product, selling_price, domestic_market="yahoo_auction")
        net_profit, estimated_costs = compute_estimated_costs(
            profile=cost_profile,
            purchase_price_jpy=candidate.purchase_price_jpy,
            selling_price_jpy=selling_price,
            gross_profit_result=gross_result,
        )
        # Keep displayed FX aligned with the rate actually used for purchase JPY.
        from dataclasses import replace as _replace_ec

        estimated_costs = _replace_ec(
            estimated_costs,
            exchange_rate=f"{derived_rate:g} JPY/{str(product_candidate['currency']).upper()}",
        )
        discovery_score = discovery_engine.score(gross_result)
        buy_decision = buy_engine.decide(gross_result, discovery_score)
        engine_decision = buy_decision.decision.value
        if not estimated_costs.net_profit_complete and not engine_decision.startswith("PROVISIONAL"):
            engine_decision = f"PROVISIONAL {engine_decision}"
    except Exception as exc:  # noqa: BLE001
        if selling_price <= 0:
            profit_failure_stage = DomesticFailureStage.INSUFFICIENT_PRICE_EVIDENCE
            profit_failure_detail = quality_report.reason or str(exc)
        else:
            profit_failure_stage = DomesticFailureStage.PROFIT_CALCULATION_FAILED
            profit_failure_detail = f"{type(exc).__name__}: {exc}"
        from profit_discovery.discovery_validation.batch_profit.models import EstimatedCosts as _EC

        gross_result = type("Gross", (), {"profit_jpy": Decimal("0"), "profit_margin": Decimal("0"), "roi": Decimal("0")})()
        net_profit = None
        estimated_costs = _EC(
            exchange_rate=f"{cost_profile.active_exchange_rate():g} JPY/USD",
            international_shipping_jpy=Decimal("0"),
            forwarding_fee_jpy=Decimal("0"),
            import_duty_jpy=Decimal("0"),
            import_tax_jpy=Decimal("0"),
            payment_fee_jpy=Decimal("0"),
            domestic_platform_fee_jpy=Decimal("0"),
            domestic_shipping_jpy=Decimal("0"),
            inspection_or_repair_reserve_jpy=Decimal("0"),
            miscellaneous_cost_jpy=Decimal("0"),
            total_additional_costs_jpy=Decimal("0"),
            net_profit_complete=False,
            unconfigured_fields=("profit_calculation_failed",),
        )
        engine_decision = "PASS"

    net_margin = None
    net_roi = None
    if net_profit is not None and candidate.purchase_price_jpy > 0:
        net_margin = net_profit / candidate.purchase_price_jpy
        net_roi = net_profit / candidate.purchase_price_jpy

    purchase_condition = detect_condition(f"{candidate.title} {candidate.condition}")
    warnings: list[str] = []
    if domestic.comparable_warning:
        warnings.append(domestic.comparable_warning)
    elif comparable.data_warning:
        warnings.append(comparable.data_warning)
    if quality_report.user_message:
        warnings.append(quality_report.user_message)
    if purchase_condition.value == "UNKNOWN":
        warnings.append("PURCHASE_CONDITION_UNKNOWN")
    if not estimated_costs.net_profit_complete:
        warnings.append("NET_COST_INCOMPLETE")

    batch_decision = assign_batch_decision(
        accepted_count=domestic.accepted_count,
        reliability=domestic.reliability,
        comparable_warning=domestic.comparable_warning or comparable.data_warning,
        net_profit_complete=estimated_costs.net_profit_complete,
        net_profit=net_profit,
        net_margin=net_margin,
        net_roi=net_roi,
        yahoo_data_source=yahoo_source,
        failure_reason=failure_reason,
        engine_decision=engine_decision,
        purchase_subtype=candidate.detected_subtype,
        purchase_category=candidate.category,
    )

    if not quality_report.publish_price:
        # Unreliable estimates must not surface as profitable ranking candidates.
        if quality_report.quality == "SUSPECT":
            batch_decision = BatchDisplayDecision.HOLD.value
        elif domestic.accepted_count < 3:
            batch_decision = BatchDisplayDecision.DATA_INSUFFICIENT.value
        else:
            batch_decision = BatchDisplayDecision.HOLD.value
        net_profit = None
        net_margin = None
        net_roi = None

    data_status = _resolve_data_status(yahoo_source)
    verification_complete = (
        domestic.accepted_count >= 3
        and domestic.reliability != "LOW"
        and estimated_costs.net_profit_complete
        and not comparable.data_warning
        and yahoo_source in {YahooDataSource.LIVE.value, YahooDataSource.LIVE_CACHE.value}
    )

    yahoo_trace_samples = list(samples) if samples else list(open_samples)
    yahoo_trace_comparable = yahoo_sold_comparable if samples else (display_comparable if open_samples else yahoo_sold_comparable)
    yahoo_trace = build_marketplace_trace(
        marketplace="Yahoo Auctions",
        search_executed=yahoo_search_executed,
        queries=list(queries),
        request_status=yahoo_request_status,
        samples=yahoo_trace_samples,
        comparable=yahoo_trace_comparable,
        best=yahoo_best,
        error=yahoo_error,
        evidence_note=(
            "Yahoo sold acquirer targets completed auctions; open-auction samples used only as fallback. "
            f"fallback={yahoo_fallback or 'none'}"
        ),
    )
    mercari_trace = build_marketplace_trace(
        marketplace="Mercari",
        search_executed=mercari_search_executed,
        queries=list(mercari_queries) if mercari_queries else list(queries),
        request_status=mercari_request_status,
        samples=list(mercari_samples),
        comparable=mercari_comparable,
        best=mercari_best,
        error=mercari_error,
        evidence_note=(
            "Mercari sold_out/trading only for price estimation; active listings are excluded."
        ),
    )
    selection_trace = build_selection_trace(
        yahoo_best=yahoo_best,
        mercari_best=mercari_best,
        selected=selected,
        predicted_sale_price_jpy=selling_price,
        evidence_count=domestic.accepted_count,
        fallback_used=yahoo_fallback,
    )
    if selling_price <= 0 and not profit_failure_stage:
        profit_failure_stage = DomesticFailureStage.INSUFFICIENT_PRICE_EVIDENCE
        profit_failure_detail = quality_report.reason or "No publishable sold-price estimate"
    profit_trace = {
        "overseas_acquisition_cost": str(candidate.purchase_price),
        "overseas_currency": candidate.currency,
        "overseas_price_jpy": str(candidate.purchase_price_jpy),
        "exchange_rate": estimated_costs.exchange_rate,
        "domestic_predicted_sale_price_jpy": str(selling_price),
        "raw_recommended_before_quality_gate_jpy": str(raw_recommended),
        "comparable_quality": quality_report.to_dict(),
        "marketplace_fees_jpy": str(estimated_costs.domestic_platform_fee_jpy),
        "payment_fees_jpy": str(estimated_costs.payment_fee_jpy),
        "shipping_logistics_jpy": str(
            estimated_costs.international_shipping_jpy
            + estimated_costs.forwarding_fee_jpy
            + estimated_costs.domestic_shipping_jpy
        ),
        "other_included_costs_jpy": str(
            estimated_costs.import_duty_jpy
            + estimated_costs.import_tax_jpy
            + estimated_costs.inspection_or_repair_reserve_jpy
            + estimated_costs.miscellaneous_cost_jpy
        ),
        "total_additional_costs_jpy": str(estimated_costs.total_additional_costs_jpy),
        "gross_estimated_profit_jpy": str(gross_result.profit_jpy),
        "net_estimated_profit_jpy": str(net_profit) if net_profit is not None else None,
        "roi": str(gross_result.roi),
        "net_roi": str(net_roi) if net_roi is not None else None,
        "batch_decision": batch_decision,
        "engine_decision": engine_decision,
        "ranking_eligibility": False,  # set after new-market validation
        "verification_complete": verification_complete and quality_report.publish_price,
        "failure_stage": profit_failure_stage,
        "failure_detail": profit_failure_detail,
        "cost_breakdown": {
            "source": "ProfitCalculator/ImportCostEngine",
            "domestic_market": str(getattr(gross_result, "domestic_market", "") or "yahoo_auction"),
            "purchase_price_jpy": _trace_money(
                getattr(gross_result, "purchase_price_jpy", None),
                fallback=candidate.purchase_price_jpy,
            ),
            "international_shipping_jpy": _trace_money(getattr(gross_result, "international_shipping_jpy", None)),
            "customs_duty_jpy": _trace_money(getattr(gross_result, "customs_duty_jpy", None)),
            "import_tax_jpy": _trace_money(getattr(gross_result, "import_tax_jpy", None)),
            "domestic_shipping_jpy": _trace_money(getattr(gross_result, "domestic_shipping_jpy", None)),
            "marketplace_fee_jpy": _trace_money(getattr(gross_result, "marketplace_fee_jpy", None)),
            "other_costs_jpy": _trace_money(getattr(gross_result, "other_costs_jpy", None)),
            "payment_fee_jpy": "0",
            "insurance_jpy": "0",
            "packaging_jpy": "0",
            "total_cost_jpy": _trace_money(getattr(gross_result, "total_cost_jpy", None)),
            "profit_jpy": _trace_money(getattr(gross_result, "profit_jpy", None)),
            "formula": "sale - total_cost_jpy - marketplace_fee_jpy",
            "config_source": "ProfitConfig defaults via MarketplaceConfiguration.from_profit_config",
        },
        "cost_profile_breakdown": {
            "source": "CostProfile",
            "profile_name": getattr(cost_profile, "profile_name", "standard"),
            "international_shipping_jpy": str(estimated_costs.international_shipping_jpy),
            "forwarding_fee_jpy": str(estimated_costs.forwarding_fee_jpy),
            "import_duty_jpy": str(estimated_costs.import_duty_jpy),
            "import_tax_jpy": str(estimated_costs.import_tax_jpy),
            "payment_fee_jpy": str(estimated_costs.payment_fee_jpy),
            "domestic_platform_fee_jpy": str(estimated_costs.domestic_platform_fee_jpy),
            "domestic_shipping_jpy": str(estimated_costs.domestic_shipping_jpy),
            "inspection_or_repair_reserve_jpy": str(estimated_costs.inspection_or_repair_reserve_jpy),
            "miscellaneous_cost_jpy": str(estimated_costs.miscellaneous_cost_jpy),
            "import_duty_rate": (
                str(cost_profile.import_duty_rate) if cost_profile.import_duty_rate is not None else None
            ),
            "import_tax_rate": (
                str(cost_profile.import_tax_rate) if cost_profile.import_tax_rate is not None else None
            ),
            "domestic_platform_fee_rate": (
                str(cost_profile.domestic_platform_fee_rate)
                if cost_profile.domestic_platform_fee_rate is not None
                else None
            ),
            "payment_fee_rate": (
                str(cost_profile.payment_fee_rate) if cost_profile.payment_fee_rate is not None else None
            ),
            "net_profit_complete": estimated_costs.net_profit_complete,
            "unconfigured_fields": list(estimated_costs.unconfigured_fields),
            "calculation_source": "標準CostProfile" if getattr(cost_profile, "profile_name", "") == "standard" else f"CostProfile:{getattr(cost_profile, 'profile_name', '')}",
        },
        "new_market_price": None,
        "new_market_warning": None,
        "new_market_validation": None,
        "profit_analysis_version": PROFIT_ANALYSIS_VERSION,
    }
    new_market_validation = _run_new_market_validation(
        candidate=candidate,
        selling_price=selling_price,
    )
    profit_trace["new_market_validation"] = new_market_validation.to_dict()
    profit_trace["ranking_eligibility"] = (
        batch_decision not in {BatchDisplayDecision.BLOCKED.value}
        and quality_report.publish_price
        and selling_price > 0
        and new_market_validation.ranking_safe
    )
    if new_market_validation.new_market_price_jpy is not None:
        profit_trace["new_market_price"] = str(new_market_validation.new_market_price_jpy)
    if new_market_validation.risk in {"WARNING", "CRITICAL"}:
        profit_trace["new_market_warning"] = {
            "used_estimate_jpy": new_market_validation.used_predicted_price_jpy,
            "new_market_price_jpy": new_market_validation.new_market_price_jpy,
            "warning": new_market_validation.reason,
            "new_market_warning": True,
            "risk": new_market_validation.risk,
            "code": new_market_validation.code,
            "marketplace": new_market_validation.marketplace,
            "match_score": new_market_validation.match_score,
            "display_label": new_market_validation.display_label,
            "user_message": new_market_validation.user_message,
        }
    overall_stage, overall_detail = resolve_overall_failure(
        yahoo=yahoo_trace,
        mercari=mercari_trace,
        selection=selection_trace,
        profit=profit_trace,
    )
    operational_trace = DomesticComparableTrace(
        overseas={
            "marketplace": candidate.purchase_source,
            "product_id": candidate.candidate_id,
            "product_title": candidate.title,
            "brand": candidate.brand,
            "normalized_category": candidate.category,
            "detected_subtype": candidate.detected_subtype,
            "condition": candidate.condition,
            "material": candidate.detected_material,
            "overseas_price": str(candidate.purchase_price),
            "currency": candidate.currency,
            "purchase_price_jpy": str(candidate.purchase_price_jpy),
            "acquisition_url": candidate.purchase_url,
            "product_identity": _product_identity_trace(candidate),
        },
        yahoo=yahoo_trace,
        mercari=mercari_trace,
        selection=selection_trace,
        profit=profit_trace,
        query_generation={
            **query_generation.to_dict(),
            "query_generation_status": query_generation.status,
            "query_generation_reason": query_generation.reason,
        },
        overall_failure_stage=overall_stage,
        overall_failure_detail=overall_detail,
    ).to_dict()

    return BatchProfitResult(
        candidate=candidate,
        yahoo_queries=queries,
        yahoo_data_source=yahoo_source,
        yahoo_cache_retrieved_at=cache_retrieved_at,
        yahoo_cache_age_hours=cache_age,
        raw_sample_count=comparable.raw_sample_count,
        accepted_comparable_count=domestic.accepted_count,
        rejected_sample_count=comparable.rejected_count,
        domestic=domestic,
        estimated_costs=estimated_costs,
        gross_estimated_profit=gross_result.profit_jpy,
        net_estimated_profit=net_profit,
        profit_margin=gross_result.profit_margin,
        net_profit_margin=net_margin,
        roi=gross_result.roi,
        net_roi=net_roi,
        engine_decision=engine_decision,
        batch_decision=batch_decision,
        data_status=data_status,
        verification_complete=verification_complete,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        failure_reason=failure_reason,
        comparable_warning=comparable.data_warning,
        warnings=tuple(warnings),
        diagnostics=diagnostics_json,
        accepted_comparables_display=format_accepted_comparables(diagnostics_json),
        rejected_samples_display=format_rejected_samples(diagnostics_json),
        yahoo_best_title=best.title if best else "",
        yahoo_best_price_jpy=best.price_jpy if best else 0,
        yahoo_best_url=best.url if best else "",
        yahoo_best_score=best.matching_score if best else 0,
        yahoo_best_attributes=best.matched_attributes if best else "",
        yahoo_best_condition=best.condition if best else "",
        yahoo_marketplace=marketplace if best else "",
        operational_trace=operational_trace,
    )


def _run_new_market_validation(*, candidate: BatchProfitCandidate, selling_price):
    from marketplace.browser_acquisition.new_market_price import NewMarketEvidence
    from marketplace.browser_acquisition.new_market_provider import (
        NullNewMarketPriceProvider,
        resolve_new_market_validation,
    )
    from marketplace.browser_acquisition.product_identity import extract_product_identity

    identity = extract_product_identity(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
    )
    injected: list[NewMarketEvidence] | None = None
    raw_injected = getattr(candidate, "new_market_candidates", None)
    if raw_injected:
        injected = list(raw_injected)
    elif getattr(candidate, "new_market_price_jpy", None) is not None:
        # Legacy single-price injection — only usable when identity already has a reference.
        injected = [
            NewMarketEvidence(
                marketplace="EXTERNAL",
                title=candidate.title,
                price=int(candidate.new_market_price_jpy),
                currency="JPY",
                condition="NEW",
            )
        ]
    provider = getattr(candidate, "new_market_provider", None) or NullNewMarketPriceProvider()
    return resolve_new_market_validation(
        product_identity=identity,
        used_predicted_price_jpy=selling_price,
        provider=provider,
        injected_candidates=injected,
    )


def _product_identity_trace(candidate: BatchProfitCandidate) -> dict:
    from marketplace.browser_acquisition.product_identity import extract_product_identity

    identity = extract_product_identity(
        title=candidate.title,
        brand=candidate.brand,
        category=candidate.category,
    )
    return identity.to_dict()


def _trace_money(value, *, fallback: Decimal | None = None) -> str | None:
    """Serialize money for operational_trace.

    Returns a numeric string when an amount exists.
    Returns None (JSON null) when missing — never the literal string \"None\".

    Note: getattr(result, \"purchase_price_jpy\", fallback) is unsafe when the
    attribute exists and is None (PriceResult error path); callers must pass
    value/fallback separately as done above.
    """
    amount = value if value is not None else fallback
    if amount is None:
        return None
    return str(amount)


def _failed_result(candidate: BatchProfitCandidate, *, reason: str) -> BatchProfitResult:
    from profit_discovery.discovery_validation.batch_profit.models import EstimatedCosts, RobustDomesticEstimate

    empty_domestic = RobustDomesticEstimate(
        raw_sample_count=0,
        accepted_count=0,
        rejected_count=0,
        minimum_jpy=0,
        maximum_jpy=0,
        average_jpy=Decimal("0"),
        median_jpy=Decimal("0"),
        q1_jpy=0,
        q3_jpy=0,
        iqr_jpy=0,
        outlier_count=0,
        trimmed_average_jpy=None,
        recommended_selling_estimate_jpy=Decimal("0"),
        reliability="LOW",
    )
    costs = EstimatedCosts(
        exchange_rate="",
        international_shipping_jpy=Decimal("0"),
        forwarding_fee_jpy=Decimal("0"),
        import_duty_jpy=Decimal("0"),
        import_tax_jpy=Decimal("0"),
        payment_fee_jpy=Decimal("0"),
        domestic_platform_fee_jpy=Decimal("0"),
        domestic_shipping_jpy=Decimal("0"),
        inspection_or_repair_reserve_jpy=Decimal("0"),
        miscellaneous_cost_jpy=Decimal("0"),
        total_additional_costs_jpy=Decimal("0"),
        net_profit_complete=False,
    )
    return BatchProfitResult(
        candidate=candidate,
        yahoo_queries=(),
        yahoo_data_source=YahooDataSource.UNAVAILABLE.value,
        yahoo_cache_retrieved_at="",
        yahoo_cache_age_hours=None,
        raw_sample_count=0,
        accepted_comparable_count=0,
        rejected_sample_count=0,
        domestic=empty_domestic,
        estimated_costs=costs,
        gross_estimated_profit=Decimal("0"),
        net_estimated_profit=None,
        profit_margin=Decimal("0"),
        net_profit_margin=None,
        roi=Decimal("0"),
        net_roi=None,
        engine_decision="PASS",
        batch_decision=BatchDisplayDecision.BLOCKED.value,
        data_status=DataStatus.UNAVAILABLE.value,
        verification_complete=False,
        retrieved_at=datetime.now(tz=UTC).isoformat(),
        failure_reason=reason,
        comparable_warning="",
        warnings=(reason,),
        diagnostics="{}",
        accepted_comparables_display="",
        rejected_samples_display="",
    )


def _resolve_data_status(yahoo_source: str) -> str:
    if yahoo_source in {YahooDataSource.LIVE.value, YahooDataSource.LIVE_CACHE.value}:
        return DataStatus.MIXED.value
    return DataStatus.UNAVAILABLE.value
