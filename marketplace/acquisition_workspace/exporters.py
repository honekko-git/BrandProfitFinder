"""Export acquisition workspace candidates."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from dataclasses import asdict

from marketplace.acquisition_workspace.models import AcquisitionCandidate
from marketplace.acquisition_workspace.ranking import (
    UsedListingRankResult,
    ranking_by_candidate_id,
    source_listing_url_warning,
)


def export_candidates_csv(path: Path | str, candidates: list[AcquisitionCandidate]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranks = ranking_by_candidate_id(candidates)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "candidate_id",
                "title",
                "brand",
                "category",
                "subtype",
                "material",
                "condition",
                "purchase_price",
                "currency",
                "purchase_url",
                "source_name",
                "quality_grade",
                "quality_score",
                "eligible",
                "selected",
                "duplicate_of",
                "data_status",
                "confidence",
                "runtime_mode",
                "discovery_timestamp",
                "query_count",
                "candidate_count",
                "comparable_count",
                "acquisition_mode",
                "comparable_source",
                "shipping_source",
                "fee_source",
                "truth_reasons",
                "rank",
                "overall_score",
                "profit_score",
                "roi_score",
                "demand_score",
                "confidence_score",
                "net_profit",
                "roi",
                "sales_count",
                "source_listing_url",
                "analysis_summary",
                "ranking_warnings",
            ]
        )
        for item in candidates:
            rank = ranks.get(item.candidate_id)
            writer.writerow(
                [
                    item.candidate_id,
                    item.title,
                    item.brand,
                    item.category,
                    item.detected_subtype,
                    item.detected_material,
                    item.detected_condition,
                    item.purchase_price,
                    item.currency,
                    item.purchase_url,
                    item.source_name,
                    item.quality_grade,
                    item.quality_score,
                    item.eligible_for_profit_check,
                    item.selected_for_profit_check,
                    item.duplicate_of,
                    item.data_status,
                    item.data_truth_summary.confidence_level,
                    item.discovery_metadata.runtime_mode,
                    item.discovery_metadata.discovery_timestamp,
                    item.discovery_metadata.query_count,
                    item.discovery_metadata.candidate_count,
                    item.discovery_metadata.comparable_count,
                    item.data_truth_summary.acquisition_mode,
                    item.data_truth_summary.comparable_source,
                    item.data_truth_summary.shipping_source,
                    item.data_truth_summary.fee_source,
                    " | ".join(item.data_truth_summary.reasons),
                    rank.rank if rank else "",
                    rank.overall_score if rank else "",
                    rank.profit_score if rank else "",
                    rank.roi_score if rank else "",
                    rank.demand_score if rank else "",
                    rank.confidence_score if rank else "",
                    rank.net_profit if rank else "",
                    rank.roi if rank else "",
                    rank.sales_count if rank else "",
                    rank.source_listing_url if rank else item.purchase_url,
                    rank.analysis_summary if rank else "",
                    " | ".join(rank.ranking_warnings) if rank else (source_listing_url_warning(item) or ""),
                ]
            )


def export_candidates_json(path: Path | str, candidates: list[AcquisitionCandidate]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranks = ranking_by_candidate_id(candidates)
    payload = [_candidate_to_dict(item, ranks.get(item.candidate_id)) for item in candidates]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _candidate_to_dict(item: AcquisitionCandidate, rank: UsedListingRankResult | None = None) -> dict:
    data = asdict(item)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = str(value)
        elif isinstance(value, tuple):
            data[key] = list(value)
    if rank is not None:
        data["ranking"] = rank.to_dict()
    else:
        data["ranking"] = None
        warning = source_listing_url_warning(item)
        if warning:
            data["ranking_exclusion_warning"] = warning
    return data
