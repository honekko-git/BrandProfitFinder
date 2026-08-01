#!/usr/bin/env python3
"""DIAGNOSTICS ONLY — unpublished selling-price audit (V1.0).

Read-only against data/brand_profit.db. Writes output/unpublished_price_*.json.
Does NOT modify ProfitCalculator, ranking, matching, quality rules, FX, or schema.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from unpublished_audit_classifier import classify_primary, recoverability  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "brand_profit.db"
OUT_DIR = ROOT / "output"

CURRENT_ANALYSIS_VERSION = "v2"
STRONG_SCORE = 90
CATEGORY_SCORE = 70
REQUIRED_SAME_MODEL = 1
REQUIRED_SOLD = 3

# Prefer known operational Fashionphile batch from live logs; fall back by heuristics.
PREFERRED_BATCHES = (
    "ws-20260731183118-b673ef",
)


def connect() -> sqlite3.Connection:
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=60.0)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    conn.row_factory = sqlite3.Row
    return conn


def _num(value: Any) -> float | None:
    if value is None or value == "" or value == "None":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return default


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def pick_workspace(conn: sqlite3.Connection) -> dict[str, Any]:
    """Pick newest operational Fashionphile-heavy workspace (never demo/fixture/smoke)."""
    batches = conn.execute(
        """
        SELECT workspace_batch_id, name, source_type, created_at, updated_at, total_rows, status
        FROM acquisition_workspace_batches
        ORDER BY updated_at DESC
        """
    ).fetchall()

    def score_batch(row: sqlite3.Row) -> tuple:
        wid = str(row["workspace_batch_id"] or "")
        name = str(row["name"] or "")
        source = str(row["source_type"] or "")
        blob = f"{wid} {name} {source}".lower()
        if any(x in blob for x in ("demo", "smoke", "fixture", "fake")):
            return (-1, 0, "")
        # Count candidates + fashionphile signal
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM acquisition_candidates WHERE workspace_batch_id = ?",
            (wid,),
        ).fetchone()["n"]
        # Sample source_name from candidates
        sample = conn.execute(
            """
            SELECT candidate_json FROM acquisition_candidates
            WHERE workspace_batch_id = ? LIMIT 40
            """,
            (wid,),
        ).fetchall()
        fp = 0
        for s in sample:
            try:
                data = json.loads(s["candidate_json"])
            except json.JSONDecodeError:
                continue
            src = str(data.get("source_name") or data.get("source_type") or "").lower()
            if "fashionphile" in src:
                fp += 1
        preferred = 1 if wid in PREFERRED_BATCHES else 0
        return (preferred, fp, int(n), str(row["updated_at"] or ""))

    ranked = sorted(batches, key=score_batch, reverse=True)
    if not ranked or score_batch(ranked[0])[0] < 0 and score_batch(ranked[0])[2] == 0:
        # Fall back: largest non-demo candidate group
        groups = conn.execute(
            """
            SELECT workspace_batch_id, COUNT(*) AS n
            FROM acquisition_candidates
            GROUP BY workspace_batch_id
            ORDER BY n DESC
            """
        ).fetchall()
        for g in groups:
            wid = str(g["workspace_batch_id"])
            if "demo" in wid.lower():
                continue
            meta = conn.execute(
                "SELECT * FROM acquisition_workspace_batches WHERE workspace_batch_id = ?",
                (wid,),
            ).fetchone()
            return {
                "workspace_batch_id": wid,
                "name": meta["name"] if meta else wid,
                "source_type": meta["source_type"] if meta else "",
                "created_at": meta["created_at"] if meta else "",
                "updated_at": meta["updated_at"] if meta else "",
                "total_rows_meta": meta["total_rows"] if meta else int(g["n"]),
                "selection_note": "largest_non_demo_fallback",
            }
        raise SystemExit("No operational workspace found")

    best = ranked[0]
    sc = score_batch(best)
    if sc[0] < 0:
        raise SystemExit("Only demo/fixture workspaces found — refusing silent demo audit")
    return {
        "workspace_batch_id": best["workspace_batch_id"],
        "name": best["name"],
        "source_type": best["source_type"],
        "created_at": best["created_at"],
        "updated_at": best["updated_at"],
        "total_rows_meta": best["total_rows"],
        "selection_note": f"preferred={sc[0]} fashionphile_sample={sc[1]} n={sc[2]}",
    }


def load_candidates(conn: sqlite3.Connection, workspace_batch_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT candidate_id, candidate_json
        FROM acquisition_candidates
        WHERE workspace_batch_id = ?
        ORDER BY created_at ASC
        """,
        (workspace_batch_id,),
    ).fetchall()
    out = []
    for row in rows:
        try:
            data = json.loads(row["candidate_json"])
        except json.JSONDecodeError:
            continue
        data["_candidate_id"] = row["candidate_id"]
        out.append(data)
    return out


def load_result(conn: sqlite3.Connection, candidate_id: str, batch_id: str) -> dict[str, Any] | None:
    if batch_id:
        row = conn.execute(
            """
            SELECT result_json FROM batch_profit_results
            WHERE batch_id = ? AND candidate_id = ?
            LIMIT 1
            """,
            (batch_id, candidate_id),
        ).fetchone()
        if row:
            return json.loads(row["result_json"])
    row = conn.execute(
        """
        SELECT result_json FROM batch_profit_results
        WHERE candidate_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (candidate_id,),
    ).fetchone()
    return json.loads(row["result_json"]) if row else None


def extract_identity(candidate: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    overseas = (trace or {}).get("overseas") or {}
    identity = overseas.get("product_identity") if isinstance(overseas, dict) else {}
    identity = identity if isinstance(identity, dict) else {}
    refs = identity.get("reference_codes") or identity.get("references") or identity.get("reference") or []
    if isinstance(refs, str):
        refs = [refs] if refs else []
    title = str(candidate.get("title") or "")
    title_refs = re.findall(r"\b[A-Z]{2,5}\s?\d{2,4}[A-Z]?\b", title.upper())
    all_refs = [str(r).replace(" ", "").upper() for r in list(refs) + title_refs if r]
    # de-dupe
    seen = set()
    uniq_refs = []
    for r in all_refs:
        if r not in seen:
            seen.add(r)
            uniq_refs.append(r)
    return {
        "reference_numbers": uniq_refs,
        "collection": str(identity.get("collection") or identity.get("model_family") or ""),
        "family": str(identity.get("model_family") or identity.get("family") or identity.get("collection") or ""),
        "material": str(
            identity.get("material")
            or candidate.get("detected_material")
            or ""
        ),
        "size": str(identity.get("size") or ""),
        "category": str(candidate.get("category") or identity.get("category") or ""),
    }


def marketplace_stats(trace: dict[str, Any], key: str) -> dict[str, Any]:
    """Read MarketplaceSearchTrace-shaped blocks from operational_trace."""
    block = (trace or {}).get(key) or {}
    if not isinstance(block, dict):
        return {
            "raw_count": 0,
            "sold_confirmed": 0,
            "matched_count": 0,
            "queries": [],
            "samples": [],
            "error": "",
            "request_status": "",
            "failure_stage": "",
            "rejection_reason_counts": {},
            "search_executed": False,
        }
    queries = block.get("queries") or []
    raw = int(block.get("raw_candidates") or 0)
    sold = int(block.get("sold_listing_evidence_count") or 0)
    matched = int(block.get("after_deterministic_matching") or 0)
    # Legacy/alternate shapes
    samples = block.get("samples") or []
    if isinstance(samples, list) and samples and raw == 0:
        raw = len(samples)
    return {
        "raw_count": raw,
        "sold_confirmed": sold,
        "matched_count": matched,
        "queries": list(queries) if isinstance(queries, (list, tuple)) else [],
        "samples": samples if isinstance(samples, list) else [],
        "error": str(block.get("error") or block.get("failure_detail") or ""),
        "request_status": str(block.get("request_status") or ""),
        "failure_stage": str(block.get("failure_stage") or ""),
        "rejection_reason_counts": dict(block.get("rejection_reason_counts") or {}),
        "search_executed": bool(block.get("search_executed")),
        "final_selected": block.get("final_selected"),
    }


def best_comp_from_samples(samples: list, marketplace: str) -> dict[str, Any]:
    best = {"title": "", "score": 0, "marketplace": marketplace, "sold_date": "", "price_jpy": None, "url": ""}
    for s in samples or []:
        if not isinstance(s, dict):
            continue
        score = int(s.get("matching_score") or s.get("match_score") or 0)
        if score >= best["score"]:
            best = {
                "title": str(s.get("title") or ""),
                "score": score,
                "marketplace": marketplace or str(s.get("source") or s.get("marketplace") or ""),
                "sold_date": str(s.get("sold_at") or s.get("sold_date") or ""),
                "price_jpy": _num(s.get("sold_price_jpy") or s.get("price_jpy") or s.get("sale_price")),
                "url": str(s.get("url") or s.get("listing_url") or ""),
            }
    return best


def parse_sold_date(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            if fmt.endswith("%z") and text.endswith("Z"):
                text2 = text.replace("Z", "+00:00")
                return datetime.fromisoformat(text2)
            return datetime.strptime(text[: len(fmt) + 5], fmt) if "T" in fmt else datetime.strptime(text[:10], fmt[:8] if False else "%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_bucket(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    days = (now - dt).days
    if days <= 30:
        return "0_30"
    if days <= 90:
        return "31_90"
    if days <= 180:
        return "91_180"
    return "over_180"


def is_unpublished(result: dict | None) -> tuple[bool, dict]:
    if result is None:
        return True, {
            "publish_price": False,
            "quality": "",
            "reason": "利益分析結果なし",
            "warning": "",
            "ranking_eligibility": False,
            "comparable_quality": {},
            "new_market_validation": {},
            "recommended": None,
            "raw_before": None,
            "profit": {},
            "trace": {},
        }
    trace = result.get("operational_trace") or {}
    profit = trace.get("profit") if isinstance(trace, dict) else {}
    profit = profit if isinstance(profit, dict) else {}
    quality_info = profit.get("comparable_quality") if isinstance(profit.get("comparable_quality"), dict) else {}
    nmv = profit.get("new_market_validation") if isinstance(profit.get("new_market_validation"), dict) else {}
    domestic = result.get("domestic") if isinstance(result.get("domestic"), dict) else {}
    warning = str(domestic.get("comparable_warning") or "")
    quality = str(quality_info.get("quality") or "")
    publish = _bool(quality_info.get("publish_price"), True)
    recommended = _num(domestic.get("recommended_selling_estimate_jpy") or profit.get("domestic_predicted_sale_price_jpy"))
    raw_before = _num(profit.get("raw_recommended_before_quality_gate_jpy"))
    ranking_eligibility = _bool(profit.get("ranking_eligibility"), False)
    if (not publish) or quality in {"SUSPECT", "INSUFFICIENT"} or warning in {
        "COMPARABLE_DATA_SUSPECT",
        "COMPARABLE_DATA_INSUFFICIENT",
    }:
        unpublished = True
    elif recommended is None or recommended <= 0:
        unpublished = True
    else:
        unpublished = False
    return unpublished, {
        "publish_price": publish,
        "quality": quality,
        "reason": str(quality_info.get("reason") or ""),
        "warning": warning,
        "ranking_eligibility": ranking_eligibility,
        "comparable_quality": quality_info,
        "new_market_validation": nmv,
        "recommended": recommended,
        "raw_before": raw_before,
        "profit": profit,
        "trace": trace if isinstance(trace, dict) else {},
    }


def audit_ui_visibility() -> dict[str, Any]:
    ranking = (ROOT / "templates" / "acquisition_workspace.html").read_text(encoding="utf-8")
    detail = ""
    detail_path = ROOT / "templates" / "acquisition_candidate_detail.html"
    if detail_path.exists():
        detail = detail_path.read_text(encoding="utf-8")
    ranking_has = {
        "selling_price": "販売予想価格" in ranking or "selling" in ranking,
        "primary_reason_column": False,  # not a dedicated column after densification
        "selling_confidence": "販売価格信頼度" in ranking,
        "overall_risk": "総合リスク" in ranking,
        "comparable_counts": "比較" in ranking and "検索/比較" in ranking,
        "same_model_counts": "同一モデル" in ranking,
        "sold_status_counts": False,
        "recovery_guidance": False,
    }
    # Expandable detail table
    ranking_has["primary_reason_in_detail_table"] = "分析状態" in ranking or "注意事項" in ranking
    ranking_has["ai_explanation_in_detail"] = "AI分析" in ranking
    detail_has = {
        "trust_rows": "総合リスク" in detail or "trust" in detail.lower(),
        "selling_evidence": "販売" in detail,
        "file": str(detail_path.name) if detail_path.exists() else None,
    }
    recommendations = [
        "Show primary unpublished reason next to 算出不可 in ranking (short code + Japanese label).",
        "On detail page, show same_model_matches / sold_confirmed_count / accepted_count explicitly.",
        "Surface secondary warning codes (COMPARABLE_DATA_SUSPECT, NEW_PRICE_CRITICAL) as chips.",
        "Add one-line recovery hint only for recoverability classes B–F (display-only).",
    ]
    return {
        "ranking_table": ranking_has,
        "detail_page": detail_has,
        "recommendations_display_only": recommendations,
    }


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(f"DB missing: {DB_PATH}")

    now = datetime.now(tz=UTC)
    conn = connect()
    workspace = pick_workspace(conn)
    wid = workspace["workspace_batch_id"]
    candidates = load_candidates(conn, wid)

    # Detect marketplace from candidates
    source_names = Counter()
    for c in candidates:
        source_names[str(c.get("source_name") or c.get("source_type") or "unknown")] += 1
    top_source = source_names.most_common(1)[0][0] if source_names else workspace.get("source_type")

    rows_out: list[dict[str, Any]] = []
    unpublished_rows: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    quality_counter: Counter[str] = Counter()
    version_counter: Counter[str] = Counter()
    recover_counter: Counter[str] = Counter()
    brand_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    market_evidence_counter: Counter[str] = Counter()
    identity_flags = Counter()
    freshness = Counter()
    sold_dates: list[datetime] = []
    false_negatives: list[dict[str, Any]] = []
    correct_rejections: list[dict[str, Any]] = []

    published = 0
    eligible = 0
    ranked = 0
    current_ver = 0
    outdated = 0
    unanalyzed = 0

    for candidate in candidates:
        cid = str(candidate.get("candidate_id") or candidate.get("_candidate_id") or "")
        batch_id = str(candidate.get("last_profit_batch_id") or "")
        result = load_result(conn, cid, batch_id)
        unpublished, meta = is_unpublished(result)
        trace = meta.get("trace") or {}
        quality_info = meta.get("comparable_quality") or {}
        identity = extract_identity(candidate, trace)
        yahoo = marketplace_stats(trace, "yahoo")
        mercari = marketplace_stats(trace, "mercari")
        version = str((candidate.get("discovery_metadata") or {}).get("profit_analysis_version") or "")
        if isinstance(candidate.get("discovery_metadata"), dict):
            version = str(candidate["discovery_metadata"].get("profit_analysis_version") or version)
        # also from result trace
        if not version and isinstance(meta.get("profit"), dict):
            version = str(meta["profit"].get("profit_analysis_version") or "")
        version_counter[version or "missing"] += 1

        eligible_flag = bool(candidate.get("eligible_for_profit_check")) and not candidate.get("duplicate_of")
        if eligible_flag and str(candidate.get("quality_grade") or "") != "REJECTED":
            eligible += 1

        if not candidate.get("last_profit_checked_at") and not batch_id:
            unanalyzed += 1
        elif version == CURRENT_ANALYSIS_VERSION:
            current_ver += 1
        else:
            outdated += 1

        same_model = int(quality_info.get("same_model_matches") or 0)
        sold = int(quality_info.get("sold_confirmed_count") or 0)
        category_matches = int(quality_info.get("category_matches") or 0)
        junk = int(quality_info.get("junk_excluded_count") or 0)
        evidence = quality_info.get("evidence") or []
        best_from_evidence = best_comp_from_samples(evidence if isinstance(evidence, list) else [], "")
        best_yahoo = best_comp_from_samples(yahoo["samples"], "Yahoo Auctions")
        best_mercari = best_comp_from_samples(mercari["samples"], "Mercari")
        selection = (trace.get("selection") or {}) if isinstance(trace, dict) else {}
        final = selection.get("final_selected_comparable") if isinstance(selection, dict) else None
        best_score = max(
            int((result or {}).get("yahoo_best_score") or 0),
            int(best_from_evidence.get("score") or 0),
            int(best_yahoo.get("score") or 0),
            int(best_mercari.get("score") or 0),
            int((final or {}).get("matching_score") or 0) if isinstance(final, dict) else 0,
        )
        if isinstance(final, dict) and final.get("title"):
            if int(final.get("matching_score") or 0) >= best_yahoo.get("score", 0):
                best_yahoo = {
                    "title": str(final.get("title") or ""),
                    "score": int(final.get("matching_score") or 0),
                    "marketplace": str(selection.get("final_selected_marketplace") or best_yahoo["marketplace"]),
                    "sold_date": best_yahoo.get("sold_date") or "",
                    "price_jpy": _num(final.get("price_jpy")),
                    "url": str(final.get("url") or ""),
                }

        # freshness from evidence + samples
        for pool in (evidence if isinstance(evidence, list) else [], yahoo["samples"], mercari["samples"]):
            for s in pool or []:
                if not isinstance(s, dict):
                    continue
                dt = parse_sold_date(str(s.get("sold_at") or s.get("sold_date") or ""))
                freshness[age_bucket(dt, now)] += 1
                if dt:
                    sold_dates.append(dt)

        if result is not None:
            q = str(meta.get("quality") or "missing") or "missing"
            quality_counter[q if q else "missing"] += 1
        else:
            quality_counter["missing"] += 1

        if identity["reference_numbers"]:
            identity_flags["reference_present"] += 1
        if identity["collection"]:
            identity_flags["collection_present"] += 1
        if identity["family"]:
            identity_flags["family_present"] += 1
        if identity["material"]:
            identity_flags["material_present"] += 1
        if (not identity["reference_numbers"] and not identity["collection"] and not identity["family"]):
            identity_flags["category_only_identity"] += 1

        y_ok = yahoo["raw_count"] > 0 or yahoo["sold_confirmed"] > 0
        m_ok = mercari["raw_count"] > 0 or mercari["sold_confirmed"] > 0
        if y_ok and m_ok:
            market_evidence_counter["both"] += 1
        elif y_ok:
            market_evidence_counter["yahoo_only"] += 1
        elif m_ok:
            market_evidence_counter["mercari_only"] += 1
        else:
            market_evidence_counter["neither"] += 1

        decision = str((result or {}).get("batch_decision") or candidate.get("last_decision") or "")
        if candidate.get("last_net_profit") is not None or (result and meta.get("recommended")):
            # ranked if has rank field or last net profit with eligibility
            if (result or {}).get("rank") or candidate.get("last_net_profit") is not None:
                if meta.get("ranking_eligibility") or (result or {}).get("rank"):
                    ranked += 1

        primary = ""
        secondary: list[str] = []
        recovery = ""
        if unpublished:
            primary, secondary = classify_primary(
                result=result,
                quality_info=quality_info,
                warning=meta.get("warning") or "",
                nmv=meta.get("new_market_validation") or {},
                identity=identity,
                yahoo=yahoo,
                mercari=mercari,
                same_model=same_model,
                sold=sold,
                category_matches=category_matches,
                best_score=best_score,
                junk=junk,
                raw_before=meta.get("raw_before"),
            )
            recovery = recoverability(primary, identity, yahoo, mercari, same_model, sold, best_score)
            reason_counter[primary] += 1
            recover_counter[recovery] += 1
            brand_counter[str(candidate.get("brand") or "unknown")] += 1
            category_counter[str(candidate.get("category") or "unknown")] += 1

            # False negative heuristic
            if (
                (identity["reference_numbers"] or identity["family"] or identity["collection"])
                and (sold >= 1 or same_model >= 1 or best_score >= CATEGORY_SCORE)
                and primary not in {"NEW_PRICE_CRITICAL", "COMPARABLE_DATA_SUSPECT"}
                and junk < 3
            ):
                false_negatives.append(
                    {
                        "candidate_id": cid,
                        "title": candidate.get("title"),
                        "brand": candidate.get("brand"),
                        "primary_reason": primary,
                        "blocking_condition": meta.get("reason") or primary,
                        "same_model_matches": same_model,
                        "sold_confirmed_count": sold,
                        "best_score": best_score,
                        "file": "marketplace/browser_acquisition/comparable_quality.py",
                        "function": "classify_comparable_quality",
                        "line_hint": "405-429 (publish requires same_model>=1 and sold>=3; category-only sold>=3 blocked)",
                        "evidence": "Identity present and some comps exist but publish_price=false",
                    }
                )
            if recovery == "A_CORRECT_REJECTION":
                correct_rejections.append(
                    {
                        "candidate_id": cid,
                        "title": candidate.get("title"),
                        "primary_reason": primary,
                        "same_model": same_model,
                        "sold": sold,
                        "category_matches": category_matches,
                    }
                )
        else:
            published += 1

        purchase = _num(candidate.get("purchase_price"))
        purchase_jpy = _num(candidate.get("purchase_price_jpy"))
        row = {
            "candidate_id": cid,
            "brand": candidate.get("brand"),
            "title": candidate.get("title"),
            "category": candidate.get("category"),
            "purchase_price": purchase,
            "purchase_price_jpy": purchase_jpy,
            "original_currency": candidate.get("currency"),
            "reference_numbers": identity["reference_numbers"],
            "extracted_collection": identity["collection"],
            "extracted_family": identity["family"],
            "material": identity["material"],
            "size": identity["size"],
            "yahoo_queries": yahoo["queries"] or list((result or {}).get("yahoo_queries") or []),
            "mercari_queries": mercari["queries"],
            "yahoo_raw_count": yahoo["raw_count"],
            "yahoo_sold_confirmed_count": yahoo["sold_confirmed"],
            "yahoo_matched_count": int(yahoo.get("matched_count") or (1 if best_yahoo.get("title") else 0)),
            "mercari_raw_count": mercari["raw_count"],
            "mercari_sold_confirmed_count": mercari["sold_confirmed"],
            "mercari_matched_count": int(mercari.get("matched_count") or (1 if best_mercari.get("title") else 0)),
            "yahoo_failure_stage": yahoo.get("failure_stage"),
            "mercari_failure_stage": mercari.get("failure_stage"),
            "yahoo_rejection_reason_counts": yahoo.get("rejection_reason_counts") or {},
            "mercari_rejection_reason_counts": mercari.get("rejection_reason_counts") or {},
            "yahoo_search_executed": yahoo.get("search_executed"),
            "mercari_search_executed": mercari.get("search_executed"),
            "accepted_comparable_count": sold,
            "same_reference_match_count": None,  # not separately traced; approx via same_model when refs present
            "same_model_family_match_count": same_model,
            "category_only_match_count": category_matches if same_model == 0 else 0,
            "rejected_comparable_counts": {
                "junk_excluded": junk,
                "active_excluded": int(quality_info.get("active_excluded_count") or 0),
                "unknown_excluded": int(quality_info.get("unknown_excluded_count") or 0),
            },
            "comparable_quality": meta.get("quality") or None,
            "publish_price": meta.get("publish_price"),
            "recommended_selling_estimate_before_gate": meta.get("raw_before"),
            "final_selling_price": meta.get("recommended") if not unpublished else 0,
            "decision": decision,
            "ranking_eligibility": meta.get("ranking_eligibility"),
            "warning_codes": [c for c in [meta.get("warning"), meta.get("quality"), (meta.get("new_market_validation") or {}).get("code")] if c],
            "exact_unpublished_reason": meta.get("reason") if unpublished else "",
            "primary_reason": primary if unpublished else "PUBLISHED",
            "secondary_reasons": secondary if unpublished else [],
            "analysis_version": version or "missing",
            "recoverability": recovery if unpublished else "",
            "best_yahoo_comparable": best_yahoo,
            "best_mercari_comparable": best_mercari,
            "best_match_score": best_score,
            "required_same_model": REQUIRED_SAME_MODEL,
            "required_sold_count": REQUIRED_SOLD,
            "unpublished": unpublished,
        }
        # approximate same-reference
        if identity["reference_numbers"] and same_model > 0:
            row["same_reference_match_count"] = same_model
        elif identity["reference_numbers"]:
            row["same_reference_match_count"] = 0

        rows_out.append(row)
        if unpublished:
            unpublished_rows.append(row)

    conn.close()

    # nearest missing condition
    def nearest_missing(r: dict) -> str:
        if r["same_model_family_match_count"] < REQUIRED_SAME_MODEL:
            return f"need same_model>={REQUIRED_SAME_MODEL} (have {r['same_model_family_match_count']})"
        if r["accepted_comparable_count"] < REQUIRED_SOLD:
            return f"need sold>={REQUIRED_SOLD} (have {r['accepted_comparable_count']})"
        if r["primary_reason"] == "NEW_PRICE_CRITICAL":
            return "new-market CRITICAL block"
        return r["exact_unpublished_reason"] or r["primary_reason"]

    for r in unpublished_rows:
        r["nearest_missing_condition"] = nearest_missing(r)
        r["recovery_appears_possible"] = r["recoverability"] not in {"A_CORRECT_REJECTION", ""}

    # Top 50: purchase price desc, then evidence strength
    top50 = sorted(
        unpublished_rows,
        key=lambda r: (
            float(r.get("purchase_price_jpy") or r.get("purchase_price") or 0),
            int(r.get("same_model_family_match_count") or 0),
            int(r.get("accepted_comparable_count") or 0),
            int(r.get("best_match_score") or 0),
        ),
        reverse=True,
    )[:50]

    total = len(candidates)
    unpublished_n = len(unpublished_rows)
    reason_dist = [
        {
            "reason": code,
            "count": count,
            "percent": _pct(count, unpublished_n),
        }
        for code, count in reason_counter.most_common()
    ]

    audit = {
        "audit_timestamp": now.isoformat(),
        "diagnostic_only": True,
        "production_logic_changed": False,
        "analysis_version_current": CURRENT_ANALYSIS_VERSION,
        "workspace": {
            **workspace,
            "source_marketplace": top_source,
            "source_name_counts": dict(source_names),
            "total_candidates": total,
            "eligible_candidates": eligible,
            "analysis_version_distribution": dict(version_counter),
            "analyzed_current_version": current_ver,
            "outdated": outdated,
            "unanalyzed": unanalyzed,
            "published_selling_prices": published,
            "unpublished_selling_prices": unpublished_n,
            "ranked_candidates_estimate": ranked,
        },
        "reason_distribution": reason_dist,
        "quality_distribution": dict(quality_counter),
        "identity_completeness": dict(identity_flags),
        "marketplace_evidence_distribution": dict(market_evidence_counter),
        "recoverability_distribution": dict(recover_counter),
        "brand_distribution_unpublished": dict(brand_counter.most_common(30)),
        "category_distribution_unpublished": dict(category_counter.most_common(30)),
        "all_unpublished": unpublished_rows,
        "all_candidates_summary": [
            {
                "candidate_id": r["candidate_id"],
                "unpublished": r["unpublished"],
                "primary_reason": r["primary_reason"],
                "quality": r["comparable_quality"],
                "analysis_version": r["analysis_version"],
            }
            for r in rows_out
        ],
        "ui_reason_visibility": audit_ui_visibility(),
        "classifier_source": "scripts/unpublished_price_audit.py",
        "quality_gate_reference": {
            "file": "marketplace/browser_acquisition/comparable_quality.py",
            "function": "classify_comparable_quality",
            "publish_rule": "same_model>=1 and sold>=3 for MEDIUM; same_model>=3 and sold>=3 for HIGH; category-only sold>=3 => SUSPECT unpublished",
        },
    }

    freshness_report = {
        "audit_timestamp": now.isoformat(),
        "workspace_batch_id": wid,
        "sold_date_available_count": freshness.get("0_30", 0)
        + freshness.get("31_90", 0)
        + freshness.get("91_180", 0)
        + freshness.get("over_180", 0),
        "sold_date_unknown_count": freshness.get("unknown", 0),
        "newest_sold_date": max(sold_dates).isoformat() if sold_dates else None,
        "oldest_sold_date": min(sold_dates).isoformat() if sold_dates else None,
        "age_distribution": {
            "0_30_days": freshness.get("0_30", 0),
            "31_90_days": freshness.get("31_90", 0),
            "91_180_days": freshness.get("91_180", 0),
            "over_180_days": freshness.get("over_180", 0),
            "unknown": freshness.get("unknown", 0),
        },
        "finding": (
            "Missing sold dates inflate unknown bucket; rules themselves unchanged. "
            "If unknown is large relative to dated sold comps, data-status recovery (class E) is indicated."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "unpublished_price_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "unpublished_price_reason_distribution.json").write_text(
        json.dumps(
            {
                "audit_timestamp": now.isoformat(),
                "workspace_batch_id": wid,
                "total_unpublished": unpublished_n,
                "primary_reasons": reason_dist,
                "quality_distribution": dict(quality_counter),
                "identity_completeness": dict(identity_flags),
                "marketplace_evidence": dict(market_evidence_counter),
                "recoverability": dict(recover_counter),
                "analysis_version_distribution": dict(version_counter),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "unpublished_price_top50.json").write_text(
        json.dumps(
            {
                "audit_timestamp": now.isoformat(),
                "workspace_batch_id": wid,
                "order": "purchase_price_jpy desc, same_model, accepted, best_score",
                "items": [
                    {
                        "title": r["title"],
                        "brand": r["brand"],
                        "purchase_price": r["purchase_price"],
                        "purchase_price_jpy": r["purchase_price_jpy"],
                        "primary_reason": r["primary_reason"],
                        "reference_family": {
                            "references": r["reference_numbers"],
                            "family": r["extracted_family"],
                            "collection": r["extracted_collection"],
                        },
                        "best_yahoo_comparable": r["best_yahoo_comparable"],
                        "best_mercari_comparable": r["best_mercari_comparable"],
                        "best_match_score": r["best_match_score"],
                        "accepted_count": r["accepted_comparable_count"],
                        "required_count": r["required_sold_count"],
                        "required_same_model": r["required_same_model"],
                        "nearest_missing_condition": r["nearest_missing_condition"],
                        "recovery_appears_possible": r["recovery_appears_possible"],
                        "recoverability": r["recoverability"],
                    }
                    for r in top50
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "unpublished_price_false_negatives.json").write_text(
        json.dumps(
            {
                "audit_timestamp": now.isoformat(),
                "workspace_batch_id": wid,
                "count": len(false_negatives),
                "items": false_negatives[:100],
                "correct_rejection_samples": correct_rejections[:50],
                "note": "Suspected false negatives are evidence-based hypotheses — not automatic defects.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "unpublished_price_freshness_audit.json").write_text(
        json.dumps(freshness_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Console summary for operator
    print("WORKSPACE", wid, workspace.get("name"), top_source)
    print("TOTAL", total, "PUBLISHED", published, "UNPUBLISHED", unpublished_n)
    print("REASONS", dict(reason_counter))
    print("RECOVERY", dict(recover_counter))
    print("WROTE", OUT_DIR / "unpublished_price_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
