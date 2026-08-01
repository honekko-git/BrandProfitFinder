"""CLI commands for acquisition workspace."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.exporters import export_candidates_csv, export_candidates_json
from marketplace.acquisition_workspace.models import confidence_sort_key
from marketplace.acquisition_workspace.ranking import (
    order_candidates_for_display,
    ranking_by_candidate_id,
    source_listing_url_warning,
)
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService


def _service() -> AcquisitionWorkspaceService:
    db_path = Path(os.getenv("BRAND_PROFIT_DB_PATH", "data/brand_profit.db"))
    return AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))


def build_acquisition_import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acquisition-import")
    parser.add_argument("--csv", help="CSV file path")
    parser.add_argument("--html", help="Saved HTML file or directory")
    return parser


def build_acquisition_list_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acquisition-list")
    parser.add_argument("--workspace-batch-id", required=True)
    parser.add_argument("--eligible-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--sort",
        choices=["profit", "confidence", "candidate-count", "updated", "overall-score"],
        default="updated",
    )
    parser.add_argument("--summary", action="store_true")
    return parser


def build_acquisition_export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acquisition-export")
    parser.add_argument("--workspace-batch-id", required=True)
    parser.add_argument("--selected-only", action="store_true")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json")
    return parser


def build_acquisition_run_profit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acquisition-run-profit")
    parser.add_argument("--workspace-batch-id", required=True)
    parser.add_argument("--selected-only", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--cost-profile", default="standard")
    parser.add_argument("--use-cache", action="store_true")
    return parser


def run_acquisition_cli(argv: list[str] | None = None, *, output: TextIO | None = None) -> int:
    stream = output or sys.stdout
    if not argv:
        stream.write("Usage: acquisition-import | acquisition-list | acquisition-export | acquisition-run-profit\n")
        return 1
    command = argv[0]
    args = argv[1:]
    service = _service()

    if command == "acquisition-import":
        parser = build_acquisition_import_parser()
        ns = parser.parse_args(args)
        if ns.csv:
            batch = service.import_csv(ns.csv)
            stream.write(f"Imported workspace batch {batch.workspace_batch_id} rows={batch.total_rows}\n")
            return 0
        if ns.html:
            path = Path(ns.html)
            files = []
            if path.is_dir():
                for item in path.glob("*.html"):
                    files.append((item.name, item.read_text(encoding="utf-8")))
            else:
                files.append((path.name, path.read_text(encoding="utf-8")))
            batch = service.import_saved_html_files(files)
            stream.write(f"Imported HTML batch {batch.workspace_batch_id} rows={batch.total_rows}\n")
            return 0
        stream.write("Provide --csv or --html\n")
        return 1

    if command == "acquisition-list":
        ns = build_acquisition_list_parser().parse_args(args)
        batch, candidates = service.get_batch(ns.workspace_batch_id)
        if ns.eligible_only:
            candidates = [
                item for item in candidates if item.eligible_for_profit_check and not item.duplicate_of
            ]
        ranks = ranking_by_candidate_id(candidates)
        candidates = _sort_candidates(candidates, ns.sort, ranks)[: ns.limit]
        if ns.summary:
            stream.write(_format_workspace_summary(batch, candidates))
            stream.write("\n\n")
        for item in candidates:
            rank = ranks.get(item.candidate_id)
            if ns.sort == "overall-score" and rank is not None:
                stream.write(_format_ranked_candidate_block(rank))
                stream.write("\n")
            else:
                stream.write(_format_candidate_line(item, rank))
                stream.write("\n")
                truth_block = _format_data_source_summary(item)
                if truth_block:
                    stream.write(truth_block)
                    stream.write("\n")
                warning = source_listing_url_warning(item)
                if warning and rank is None:
                    stream.write(f"順位注意: {warning}\n")
        return 0

    if command == "acquisition-export":
        ns = build_acquisition_export_parser().parse_args(args)
        candidates = service.list_candidates(ns.workspace_batch_id, selected_only=ns.selected_only)
        export_candidates_csv(ns.output_csv, candidates)
        if ns.output_json:
            export_candidates_json(ns.output_json, candidates)
        stream.write(f"{len(candidates)} 件をエクスポートしました\n")
        return 0

    if command == "acquisition-run-profit":
        ns = build_acquisition_run_profit_parser().parse_args(args)
        service.select_all_eligible(ns.workspace_batch_id)
        run = service.run_batch_profit(
            ns.workspace_batch_id,
            cost_profile_name=ns.cost_profile,
            use_cache=ns.use_cache,
        )
        stream.write(f"利益バッチ {run.summary.batch_id} 処理件数={run.summary.processed_count}\n")
        for item in run.results[: ns.limit]:
            stream.write(
                f"{item.candidate.title} | 判定={item.batch_decision} | 粗利={item.gross_estimated_profit} | 純利益={item.net_estimated_profit}\n"
            )
        return 0

    stream.write(f"不明なコマンド: {command}\n")
    return 1


def _sort_candidates(candidates, sort_key: str, ranks=None):
    ranks = ranks or ranking_by_candidate_id(candidates)
    if sort_key == "overall-score":
        return order_candidates_for_display(candidates)
    if sort_key == "profit":
        return sorted(
            candidates,
            key=lambda item: item.last_net_profit or item.last_gross_profit or Decimal("-999999999"),
            reverse=True,
        )
    if sort_key == "confidence":
        return sorted(
            candidates,
            key=lambda item: (
                confidence_sort_key(item.data_truth_summary.confidence_level),
                item.last_net_profit or item.last_gross_profit or Decimal("0"),
            ),
            reverse=True,
        )
    if sort_key == "candidate-count":
        return sorted(
            candidates,
            key=lambda item: (
                item.discovery_metadata.candidate_count,
                item.discovery_metadata.comparable_count,
            ),
            reverse=True,
        )
    return sorted(
        candidates,
        key=lambda item: item.last_profit_checked_at or item.imported_at or item.acquired_at,
        reverse=True,
    )


def _format_candidate_line(item, rank=None) -> str:
    profit = item.last_net_profit or item.last_gross_profit
    profit_display = str(int(profit)) if profit is not None else "-"
    rank_display = str(rank.rank) if rank is not None else "-"
    score_display = str(rank.overall_score) if rank is not None else "-"
    return (
        f"{item.candidate_id} | rank={rank_display} | score={score_display} | "
        f"{item.data_truth_summary.confidence_level} | {item.quality_grade} | "
        f"{item.title} | eligible={item.eligible_for_profit_check} | selected={item.selected_for_profit_check} | "
        f"profit={profit_display}"
    )


def _format_ranked_candidate_block(rank) -> str:
    profit = "N/A" if rank.net_profit is None else f"{int(rank.net_profit):,} JPY"
    roi = "N/A" if rank.roi is None else f"{rank.roi}%"
    return "\n".join(
        [
            f"{rank.rank}. {rank.title}",
            f"総合評価: {rank.overall_score}",
            f"純利益: {profit}",
            f"ROI: {roi}",
            f"販売実績: {rank.sales_count}",
            f"信頼度: {rank.confidence_level}",
            f"商品ページURL: {rank.source_listing_url}",
            f"AI分析: {rank.analysis_summary}",
        ]
    )


def _format_workspace_summary(batch, candidates) -> str:
    accepted = sum(1 for item in candidates if item.quality_grade != "REJECTED" and not item.duplicate_of)
    rejected = sum(1 for item in candidates if item.quality_grade == "REJECTED")
    pending = max(len(candidates) - accepted - rejected, 0)
    average_profit = _average_decimal(
        [item.last_net_profit or item.last_gross_profit for item in candidates if (item.last_net_profit or item.last_gross_profit) is not None]
    )
    average_confidence = _average_confidence(candidates)
    runtime = _workspace_runtime(candidates)
    last_updated = max(
        (item.last_profit_checked_at or item.imported_at or item.acquired_at for item in candidates),
        default=batch.updated_at,
    )
    lines = [
        "ワークスペース概要",
        "",
        f"バッチ: {batch.workspace_batch_id}",
        f"候補数: {len(candidates)}",
        f"採用: {accepted}",
        f"除外: {rejected}",
        f"保留: {pending}",
        f"平均信頼度: {average_confidence}",
        f"平均利益: {_format_decimal_jpy(average_profit)}",
        f"最終更新: {last_updated}",
        f"データ取得方法: {runtime}",
        f"取得モード: {batch.source_type}",
    ]
    return "\n".join(lines)


def _average_confidence(candidates) -> str:
    if not candidates:
        return "LOW"
    total = sum(confidence_sort_key(item.data_truth_summary.confidence_level) for item in candidates)
    average = total / len(candidates)
    if average >= 2.5:
        return "HIGH"
    if average >= 1.5:
        return "MEDIUM"
    return "LOW"


def _average_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _workspace_runtime(candidates) -> str:
    runtimes = {item.discovery_metadata.runtime_mode for item in candidates if item.discovery_metadata.runtime_mode}
    if not runtimes:
        return "IMPORT"
    if len(runtimes) == 1:
        return next(iter(runtimes))
    return "MIXED"


def _format_decimal_jpy(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} JPY"


def _format_data_source_summary(item) -> str:
    values = [
        ("商品情報", item.data_truth_summary.price_source),
        ("比較データ", item.data_truth_summary.comparable_source),
        ("送料", item.data_truth_summary.shipping_source),
        ("手数料", item.data_truth_summary.fee_source),
        ("信頼度", item.data_truth_summary.confidence_level),
        ("実行モード", item.discovery_metadata.runtime_mode),
        ("クエリ数", str(item.discovery_metadata.query_count)),
        ("候補数", str(item.discovery_metadata.candidate_count)),
        ("比較件数", str(item.discovery_metadata.comparable_count)),
        ("理由", ", ".join(item.data_truth_summary.reasons)),
    ]
    existing = [(label, value) for label, value in values if value]
    if not existing:
        return ""
    lines = ["========================", "", "データ取得情報", ""]
    for label, value in existing:
        lines.extend([f"{label}:", value, ""])
    if lines[-1] == "":
        lines.pop()
    lines.append("========================")
    return "\n".join(lines)
