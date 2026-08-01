"""SQLite repository for batch profit runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.storage.database import connect
from profit_discovery.discovery_validation.batch_profit.models import (
    BatchProfitResult,
    BatchProfitRun,
    BatchRunSummary,
)


class BatchProfitRepository:
    """Persist and retrieve batch profit runs."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = database_path

    def save_run(self, run: BatchProfitRun) -> None:
        now = datetime.now(tz=UTC).isoformat()
        summary = run.summary
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO batch_runs (
                    batch_id, started_at, completed_at, cost_profile, exchange_rate,
                    total_candidates, processed_count, strong_candidate_count, review_count,
                    hold_count, reject_count, failed_count, blocked_count,
                    total_yahoo_requests, cache_hits, status, summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.batch_id,
                    summary.started_at,
                    summary.completed_at,
                    summary.cost_profile,
                    summary.exchange_rate,
                    summary.total_candidates,
                    summary.processed_count,
                    summary.strong_candidate_count,
                    summary.review_count,
                    summary.hold_count,
                    summary.reject_count,
                    summary.failed_count,
                    summary.blocked_count,
                    summary.total_yahoo_requests,
                    summary.cache_hits,
                    summary.status,
                    json.dumps(_summary_to_dict(summary), ensure_ascii=False),
                    now,
                ),
            )
            for result in run.results:
                connection.execute(
                    """
                    INSERT INTO batch_profit_results (batch_id, candidate_id, rank, result_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        summary.batch_id,
                        result.candidate.candidate_id,
                        result.rank,
                        json.dumps(_result_to_dict(result), ensure_ascii=False),
                        now,
                    ),
                )
                self._save_evidence(connection, summary.batch_id, result)
            connection.commit()

    def list_runs(self, *, limit: int = 20) -> list[BatchRunSummary]:
        with connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT summary_json FROM batch_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_summary_from_dict(json.loads(row["summary_json"])) for row in rows]

    def get_run(self, batch_id: str) -> BatchProfitRun | None:
        with connect(self._database_path) as connection:
            summary_row = connection.execute(
                "SELECT summary_json FROM batch_runs WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
            if summary_row is None:
                return None
            result_rows = connection.execute(
                """
                SELECT result_json FROM batch_profit_results
                WHERE batch_id = ?
                ORDER BY rank ASC
                """,
                (batch_id,),
            ).fetchall()
        summary = _summary_from_dict(json.loads(summary_row["summary_json"]))
        results = tuple(_result_from_dict(json.loads(row["result_json"])) for row in result_rows)
        return BatchProfitRun(summary=summary, results=results)

    def delete_run(self, batch_id: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute("DELETE FROM comparable_evidence WHERE batch_id = ?", (batch_id,))
            connection.execute("DELETE FROM batch_profit_results WHERE batch_id = ?", (batch_id,))
            connection.execute("DELETE FROM batch_runs WHERE batch_id = ?", (batch_id,))
            connection.commit()

    def _save_evidence(self, connection, batch_id: str, result: BatchProfitResult) -> None:
        now = datetime.now(tz=UTC).isoformat()
        diagnostics = json.loads(result.diagnostics or "{}")
        rows = []
        for item in diagnostics.get("accepted", []):
            rows.append((item, True))
        for item in diagnostics.get("rejected", []):
            rows.append((item, False))
        for item, accepted in rows:
            connection.execute(
                """
                INSERT INTO comparable_evidence (
                    batch_id, candidate_id, yahoo_title, price_jpy, url, matching_score,
                    accepted, rejection_reasons, subtype, material, condition_label,
                    retrieved_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    result.candidate.candidate_id,
                    item.get("title", ""),
                    int(item.get("price_jpy", 0)),
                    item.get("url", ""),
                    int(item.get("score", 0)),
                    1 if accepted else 0,
                    ",".join(item.get("reasons", [])),
                    item.get("subtype", ""),
                    item.get("material", ""),
                    item.get("condition", "UNKNOWN"),
                    result.retrieved_at,
                    now,
                ),
            )


def _summary_to_dict(summary: BatchRunSummary) -> dict:
    return asdict(summary)


def _summary_from_dict(data: dict) -> BatchRunSummary:
    return BatchRunSummary(**data)


def _result_to_dict(result: BatchProfitResult) -> dict:
    payload = asdict(result)
    payload["candidate"] = asdict(result.candidate)
    payload["domestic"] = asdict(result.domestic)
    payload["estimated_costs"] = asdict(result.estimated_costs)
    return _encode_decimals(payload)


def _result_from_dict(data: dict) -> BatchProfitResult:
    from profit_discovery.discovery_validation.batch_profit.models import (
        BatchProfitCandidate,
        EstimatedCosts,
        RobustDomesticEstimate,
    )

    candidate = BatchProfitCandidate(**_decode_decimals(data["candidate"]))
    domestic = RobustDomesticEstimate(**_decode_decimals(data["domestic"]))
    costs = EstimatedCosts(**_decode_decimals(data["estimated_costs"]))
    payload = _decode_decimals(data)
    payload["candidate"] = candidate
    payload["domestic"] = domestic
    payload["estimated_costs"] = costs
    return BatchProfitResult(**payload)


def _encode_decimals(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _encode_decimals(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_decimals(item) for item in value]
    if isinstance(value, tuple):
        return [_encode_decimals(item) for item in value]
    return value


_DECIMAL_FIELD_NAMES = frozenset(
    {
        "purchase_price",
        "purchase_price_jpy",
        "average_jpy",
        "median_jpy",
        "trimmed_average_jpy",
        "recommended_selling_estimate_jpy",
        "gross_estimated_profit",
        "net_estimated_profit",
        "profit_margin",
        "net_profit_margin",
        "roi",
        "net_roi",
        "international_shipping_jpy",
        "forwarding_fee_jpy",
        "import_duty_jpy",
        "import_tax_jpy",
        "payment_fee_jpy",
        "domestic_platform_fee_jpy",
        "domestic_shipping_jpy",
        "inspection_or_repair_reserve_jpy",
        "miscellaneous_cost_jpy",
        "total_additional_costs_jpy",
    }
)

# Tokens that appear in nested JSON near money keys but are not numeric.
_NON_NUMERIC_TOKENS = frozenset(
    {
        "none",
        "null",
        "nan",
        "high",
        "low",
        "medium",
        "review",
        "hold",
        "reject",
        "pass",
        "buy",
        "blocked",
        "true",
        "false",
    }
)


def _decode_decimal(field_name: str, value):
    """Safely convert one stored money field to Decimal.

    Never raises. Non-numeric values (literal \"None\", decision labels, dicts,
    lists, bools) return None instead of calling Decimal() on invalid text.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    # bool is a subclass of int — reject before int/float handling.
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple)):
        print(
            "field name=",
            field_name,
            "field value=",
            repr(value),
            "field type=",
            type(value).__name__,
            "before Decimal() - skipped non-numeric",
        )
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in _NON_NUMERIC_TOKENS:
            print(
                "field name=",
                field_name,
                "field value=",
                repr(value),
                "field type=",
                type(value).__name__,
                "before Decimal() - skipped non-numeric token",
            )
            return None
        try:
            return Decimal(text)
        except Exception:
            print(
                "field name=",
                field_name,
                "field value=",
                repr(value),
                "field type=",
                type(value).__name__,
                "before Decimal() - ConversionSyntax avoided",
            )
            return None
    print(
        "field name=",
        field_name,
        "field value=",
        repr(value),
        "field type=",
        type(value).__name__,
        "before Decimal() - skipped unsupported type",
    )
    return None


def _decode_decimals(value):
    if isinstance(value, dict):
        decoded = {key: _decode_decimals(item) for key, item in value.items()}
        for key in _DECIMAL_FIELD_NAMES:
            if key in decoded and decoded[key] not in (None, "") and not isinstance(decoded[key], Decimal):
                decoded[key] = _decode_decimal(key, decoded[key])
        return decoded
    if isinstance(value, list):
        return [_decode_decimals(item) for item in value]
    return value
