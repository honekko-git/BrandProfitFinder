"""Ranking helpers for batch profit results."""

from __future__ import annotations

from profit_discovery.discovery_validation.batch_profit.decisions import decision_sort_key
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitResult


def rank_batch_results(results: list[BatchProfitResult]) -> list[BatchProfitResult]:
    """Rank batch results by decision priority and net profit."""
    ordered = sorted(results, key=decision_sort_key)
    ranked: list[BatchProfitResult] = []
    for index, item in enumerate(ordered, start=1):
        ranked.append(
            BatchProfitResult(
                candidate=item.candidate,
                yahoo_queries=item.yahoo_queries,
                yahoo_data_source=item.yahoo_data_source,
                yahoo_cache_retrieved_at=item.yahoo_cache_retrieved_at,
                yahoo_cache_age_hours=item.yahoo_cache_age_hours,
                raw_sample_count=item.raw_sample_count,
                accepted_comparable_count=item.accepted_comparable_count,
                rejected_sample_count=item.rejected_sample_count,
                domestic=item.domestic,
                estimated_costs=item.estimated_costs,
                gross_estimated_profit=item.gross_estimated_profit,
                net_estimated_profit=item.net_estimated_profit,
                profit_margin=item.profit_margin,
                net_profit_margin=item.net_profit_margin,
                roi=item.roi,
                net_roi=item.net_roi,
                engine_decision=item.engine_decision,
                batch_decision=item.batch_decision,
                data_status=item.data_status,
                verification_complete=item.verification_complete,
                retrieved_at=item.retrieved_at,
                failure_reason=item.failure_reason,
                comparable_warning=item.comparable_warning,
                warnings=item.warnings,
                diagnostics=item.diagnostics,
                accepted_comparables_display=item.accepted_comparables_display,
                rejected_samples_display=item.rejected_samples_display,
                rank=index,
                yahoo_best_title=item.yahoo_best_title,
                yahoo_best_price_jpy=item.yahoo_best_price_jpy,
                yahoo_best_url=item.yahoo_best_url,
                yahoo_best_score=item.yahoo_best_score,
                yahoo_best_attributes=item.yahoo_best_attributes,
                yahoo_best_condition=item.yahoo_best_condition,
                yahoo_marketplace=item.yahoo_marketplace,
                operational_trace=_with_rank(item.operational_trace, index),
            )
        )
    return ranked


def _with_rank(trace: dict, rank: int) -> dict:
    if not trace:
        return {"profit": {"ranking_position": rank}}
    payload = dict(trace)
    profit = dict(payload.get("profit") or {})
    profit["ranking_position"] = rank
    if rank <= 0:
        profit["failure_stage"] = profit.get("failure_stage") or "RANKING_REJECTED"
        profit["failure_detail"] = profit.get("failure_detail") or "Result was not assigned a ranking position"
    payload["profit"] = profit
    return payload
