"""CLI entry point for batch profit discovery."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import TextIO

from app.storage.batch_profit_repository import BatchProfitRepository
from profit_discovery.discovery_validation.batch_profit.candidate_import import load_batch_candidates_from_csv
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.pipeline import HARD_CANDIDATE_MAX, run_batch_profit


def build_batch_profit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="batch-profit-check",
        description="Run batch real profit discovery for multiple purchase candidates.",
    )
    parser.add_argument("--csv", required=True, help="CSV file with batch candidates")
    parser.add_argument("--limit", type=int, default=10, help="Maximum candidates to process")
    parser.add_argument("--cost-profile", default="standard", help="Cost profile name")
    parser.add_argument("--use-cache", action="store_true", help="Use Yahoo search cache")
    parser.add_argument("--output-json", help="Optional JSON output path")
    parser.add_argument("--output-csv", help="Optional CSV output path")
    return parser


def run_batch_profit_command(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    stream = output or sys.stdout
    args = build_batch_profit_parser().parse_args(argv)
    limit = max(1, min(args.limit, HARD_CANDIDATE_MAX))
    imported = load_batch_candidates_from_csv(args.csv, limit=limit)
    if not imported.candidates:
        stream.write("Status: NO_CANDIDATES\n")
        for error in imported.errors:
            stream.write(f"Import error: {error}\n")
        return 1

    profile_store = CostProfileStore(
        profiles=default_cost_profiles(),
        storage_path=Path("data/cost_profiles.json"),
    )
    profile = profile_store.get(args.cost_profile)
    run = run_batch_profit(
        imported.candidates,
        cost_profile=profile,
        use_cache=args.use_cache,
        import_errors=tuple(imported.errors),
    )
    BatchProfitRepository().save_run(run)

    summary = run.summary
    stream.write(f"Batch ID: {summary.batch_id}\n")
    stream.write(f"Processed: {summary.processed_count}/{summary.total_candidates}\n")
    stream.write(f"Yahoo LIVE requests: {summary.total_yahoo_requests}\n")
    stream.write(f"Cache hits: {summary.cache_hits}\n")
    stream.write(f"Strong candidates: {summary.strong_candidate_count}\n")
    for error in imported.errors:
        stream.write(f"Candidate error: {error}\n")

    for item in run.results[:10]:
        stream.write("\n---\n")
        stream.write(f"Product: {item.candidate.title}\n")
        stream.write(f"Purchase URL: {item.candidate.purchase_url}\n")
        stream.write(f"Accepted comparables: {item.accepted_comparable_count}\n")
        stream.write(f"Recommended estimate: {item.domestic.recommended_selling_estimate_jpy} JPY\n")
        stream.write(f"Gross profit: {item.gross_estimated_profit} JPY\n")
        stream.write(
            f"Net profit: {item.net_estimated_profit if item.net_estimated_profit is not None else 'Not configured'} JPY\n"
        )
        stream.write(f"Margin: {item.profit_margin}\n")
        stream.write(f"ROI: {item.roi}\n")
        stream.write(f"Decision: {item.batch_decision}\n")
        stream.write(f"Warning: {', '.join(item.warnings) if item.warnings else item.comparable_warning}\n")
        stream.write(f"Data status: {item.data_status}\n")

    if args.output_json:
        _write_json(Path(args.output_json), run)
    if args.output_csv:
        _write_csv(Path(args.output_csv), run)
    return 0


def run_batch_profit_cli(argv: list[str] | None = None) -> int:
    return run_batch_profit_command(argv)


def _write_json(path: Path, run) -> None:
    from dataclasses import asdict

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": asdict(run.summary),
        "results": [
            {
                "candidate": asdict(item.candidate),
                "batch_decision": item.batch_decision,
                "gross_estimated_profit": str(item.gross_estimated_profit),
                "net_estimated_profit": str(item.net_estimated_profit) if item.net_estimated_profit is not None else None,
                "recommended_estimate": str(item.domestic.recommended_selling_estimate_jpy),
                "accepted_comparable_count": item.accepted_comparable_count,
                "data_status": item.data_status,
                "warnings": list(item.warnings),
            }
            for item in run.results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, run) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "product",
                "purchase_price",
                "purchase_price_jpy",
                "accepted_comparables",
                "recommended_estimate",
                "gross_profit",
                "net_profit",
                "margin",
                "roi",
                "decision",
                "warning",
                "data_status",
            ]
        )
        for item in run.results:
            writer.writerow(
                [
                    item.rank,
                    item.candidate.title,
                    f"{item.candidate.purchase_price} {item.candidate.currency}",
                    item.candidate.purchase_price_jpy,
                    item.accepted_comparable_count,
                    item.domestic.recommended_selling_estimate_jpy,
                    item.gross_estimated_profit,
                    item.net_estimated_profit if item.net_estimated_profit is not None else "Not configured",
                    item.profit_margin,
                    item.roi,
                    item.batch_decision,
                    ", ".join(item.warnings) if item.warnings else item.comparable_warning,
                    item.data_status,
                ]
            )
