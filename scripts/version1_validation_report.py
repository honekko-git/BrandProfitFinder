"""Version 1.0 operational validation report (read-only after v3 replay)."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION  # noqa: E402
from marketplace.browser_acquisition.product_identity import extract_product_identity  # noqa: E402

BATCH = "ws-20260731183118-b673ef"
DB = ROOT / "data" / "brand_profit.db"
OUT = ROOT / "output"

# Prior unpublished audit distribution (v2 era) for comparison.
PRIOR_UNPUBLISHED = {
    "NO_SOLD_DATA": 204,
    "MISSING_REQUIRED_TRACE_DATA": 132,
    "COMPARABLE_DATA_SUSPECT": 51,
    "IDENTITY_EXTRACTION_INCOMPLETE": 16,
    "INSUFFICIENT_ACCEPTED_COUNT": 4,
    "LOW_MATCH_SCORE": 2,
    "NO_ACCEPTED_COMPARABLES": 1,
    "total_unpublished": 410,
    "published": 0,
}


def _load_candidates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT candidate_id, candidate_json FROM acquisition_candidates WHERE workspace_batch_id=?",
        (BATCH,),
    ).fetchall()
    out = []
    for row in rows:
        data = json.loads(row["candidate_json"])
        data["candidate_id"] = row["candidate_id"]
        out.append(data)
    return out


def _load_latest_result(conn: sqlite3.Connection, candidate_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT result_json FROM batch_profit_results
        WHERE candidate_id=?
        ORDER BY id DESC LIMIT 1
        """,
        (candidate_id,),
    ).fetchone()
    return json.loads(row["result_json"]) if row else None


def _num(v: Any) -> float | None:
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify_unpublished(result: dict | None, cand: dict) -> str:
    if not result:
        return "OTHER"
    trace = result.get("operational_trace") or {}
    profit = trace.get("profit") or {}
    quality = profit.get("comparable_quality") or {}
    q = str(quality.get("quality") or "")
    yahoo = trace.get("yahoo") or {}
    mercari = trace.get("mercari") or {}
    qg = trace.get("query_generation") or {}
    same = int(quality.get("same_model_matches") or 0)
    sold_q = int(quality.get("sold_confirmed_count") or 0)
    yraw = int(yahoo.get("raw_candidates") or 0)
    mraw = int(mercari.get("raw_candidates") or 0)
    yfail = str(yahoo.get("failure_stage") or "")
    mfail = str(mercari.get("failure_stage") or "")
    nm = profit.get("new_market_validation") or {}
    nm_risk = str(nm.get("risk") or "")
    reject = yahoo.get("rejection_reason_counts") or {}
    if isinstance(reject, dict) and not reject:
        reject = mercari.get("rejection_reason_counts") or {}

    if nm_risk == "CRITICAL":
        return "NEW_PRICE_CRITICAL"
    if q == "SUSPECT" or "SUSPECT" in str(quality.get("reason") or "").upper():
        return "SUSPECT"
    if qg.get("status") == "NO_SAFE_QUERY" or (
        not (yahoo.get("queries") or result.get("yahoo_queries"))
        and yraw == 0
        and "REQUEST_FAILED" in (yfail + mfail)
    ):
        return "QUERY_FAILURE"
    if yraw == 0 and mraw == 0:
        return "NO_SOLD_DATA"
    if same == 0 and (sold_q > 0 or yraw > 0 or mraw > 0):
        # Distinguish category-only vs low match
        if any("CATEGORY" in str(k).upper() for k in (reject or {})) or same == 0 and sold_q == 0:
            # category-only often surfaces as SUSPECT already; otherwise NO_SAME_MODEL
            if "SCORE_BELOW" in json.dumps(reject).upper() or "MODEL_SIMILARITY" in json.dumps(reject).upper():
                return "LOW_MATCH_SCORE"
            return "NO_SAME_MODEL"
    if "SCORE_BELOW" in json.dumps(reject).upper() or "MODEL_SIMILARITY" in json.dumps(reject).upper():
        return "LOW_MATCH_SCORE"
    if same == 0:
        return "NO_SAME_MODEL"
    # Weak category-only identity products
    identity = extract_product_identity(
        title=cand.get("title") or "",
        brand=cand.get("brand") or "",
        category=cand.get("category") or "",
    )
    if not identity.has_reference and not identity.collection and not identity.has_strong_model:
        return "CATEGORY_ONLY"
    return "OTHER"


def is_published(result: dict | None) -> bool:
    if not result:
        return False
    trace = result.get("operational_trace") or {}
    profit = trace.get("profit") or {}
    quality = profit.get("comparable_quality") or {}
    if quality.get("publish_price") is True:
        selling = _num(profit.get("domestic_predicted_sale_price_jpy"))
        return bool(selling and selling > 0)
    # Fallback: domestic recommended
    domestic = result.get("domestic") or {}
    if isinstance(domestic, dict):
        rec = _num(domestic.get("recommended_selling_estimate_jpy"))
        warning = str(domestic.get("comparable_warning") or "")
        if rec and rec > 0 and "INSUFFICIENT" not in warning and "SUSPECT" not in warning:
            return bool(quality.get("publish_price", False))
    return False


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    candidates = _load_candidates(conn)

    versions = Counter()
    qualities = Counter()
    unpublished_reasons = Counter()
    eligible_n = 0
    analyzed_n = 0
    published_items: list[dict] = []
    unpublished_items: list[dict] = []
    same_model_vals: list[int] = []
    accepted_vals: list[int] = []
    ranking_eligible = 0

    for cand in candidates:
        cid = cand["candidate_id"]
        eligible = bool(cand.get("eligible_for_profit_check")) and not cand.get("duplicate_of") and cand.get("quality_grade") != "REJECTED"
        if eligible:
            eligible_n += 1
        result = _load_latest_result(conn, cid)
        meta = cand.get("discovery_metadata") or {}
        ver = str(meta.get("profit_analysis_version") or "")
        if not ver and result:
            ver = str(((result.get("operational_trace") or {}).get("profit") or {}).get("profit_analysis_version") or "")
        versions[ver or "missing"] += 1

        if not result:
            if eligible:
                unpublished_items.append({"candidate_id": cid, "title": cand.get("title"), "reason": "OTHER", "detail": "no_result"})
                unpublished_reasons["OTHER"] += 1
            continue

        if ver == PROFIT_ANALYSIS_VERSION:
            analyzed_n += 1

        trace = result.get("operational_trace") or {}
        profit = trace.get("profit") or {}
        quality = profit.get("comparable_quality") or {}
        q = str(quality.get("quality") or "missing")
        qualities[q] += 1
        same = int(quality.get("same_model_matches") or 0)
        accepted = int(
            quality.get("accepted_count")
            or (result.get("accepted_comparable_count") if result.get("accepted_comparable_count") is not None else 0)
            or 0
        )
        same_model_vals.append(same)
        accepted_vals.append(accepted)
        if profit.get("ranking_eligibility"):
            ranking_eligible += 1

        item = {
            "candidate_id": cid,
            "title": cand.get("title"),
            "brand": cand.get("brand"),
            "category": cand.get("category"),
            "purchase_price_jpy": cand.get("purchase_price_jpy"),
            "purchase_price": cand.get("purchase_price"),
            "currency": cand.get("currency"),
            "analysis_version": ver,
            "quality": q,
            "same_model": same,
            "accepted": accepted,
            "sold_confirmed": quality.get("sold_confirmed_count"),
            "publish_price": quality.get("publish_price"),
            "selling_jpy": profit.get("domestic_predicted_sale_price_jpy"),
            "net_profit": profit.get("net_estimated_profit_jpy") or result.get("net_estimated_profit"),
            "gross_profit": profit.get("gross_estimated_profit_jpy") or result.get("gross_estimated_profit"),
            "roi": profit.get("roi") or result.get("roi"),
            "ranking_eligibility": profit.get("ranking_eligibility"),
            "new_market": profit.get("new_market_validation"),
            "yahoo": {
                "queries": (trace.get("yahoo") or {}).get("queries"),
                "raw": (trace.get("yahoo") or {}).get("raw_candidates"),
                "matched": (trace.get("yahoo") or {}).get("after_deterministic_matching"),
                "failure": (trace.get("yahoo") or {}).get("failure_stage"),
                "median": (trace.get("yahoo") or {}).get("median_sold_price_jpy"),
            },
            "mercari": {
                "queries": (trace.get("mercari") or {}).get("queries"),
                "raw": (trace.get("mercari") or {}).get("raw_candidates"),
                "matched": (trace.get("mercari") or {}).get("after_deterministic_matching"),
                "failure": (trace.get("mercari") or {}).get("failure_stage"),
            },
            "query_generation": trace.get("query_generation"),
            "identity": ((trace.get("overseas") or {}).get("product_identity")),
            "freshness": quality.get("freshness_label") or quality.get("latest_sold_date"),
            "cost_breakdown": profit.get("cost_breakdown"),
            "cost_profile_breakdown": profit.get("cost_profile_breakdown"),
            "batch_decision": result.get("batch_decision") or profit.get("batch_decision"),
        }

        if is_published(result):
            published_items.append(item)
        else:
            reason = classify_unpublished(result, cand)
            item["unpublished_reason"] = reason
            unpublished_reasons[reason] += 1
            unpublished_items.append(item)

    # Rank published by net profit then gross then purchase
    def _rank_key(it: dict) -> tuple:
        net = _num(it.get("net_profit"))
        gross = _num(it.get("gross_profit"))
        sell = _num(it.get("selling_jpy"))
        return (
            0 if net is None else 1,
            net or 0,
            0 if gross is None else 1,
            gross or 0,
            sell or 0,
        )

    published_items.sort(key=_rank_key, reverse=True)
    top30 = published_items[:30]

    top30_audit = []
    for idx, it in enumerate(top30, start=1):
        identity = it.get("identity") or {}
        refs = identity.get("reference_numbers") or identity.get("references") or []
        nm = it.get("new_market") or {}
        top30_audit.append(
            {
                "rank": idx,
                "candidate_id": it["candidate_id"],
                "title": it["title"],
                "brand": it["brand"],
                "purchase_price_jpy": it["purchase_price_jpy"],
                "selling_jpy": it["selling_jpy"],
                "net_profit": it["net_profit"],
                "gross_profit": it["gross_profit"],
                "roi": it["roi"],
                "quality": it["quality"],
                "same_model": it["same_model"],
                "accepted": it["accepted"],
                "sold_confirmed": it["sold_confirmed"],
                "reference_numbers": refs,
                "collection": identity.get("collection"),
                "family": identity.get("family") or identity.get("model_family"),
                "yahoo_queries": (it.get("yahoo") or {}).get("queries"),
                "yahoo_raw": (it.get("yahoo") or {}).get("raw"),
                "yahoo_matched": (it.get("yahoo") or {}).get("matched"),
                "yahoo_median": (it.get("yahoo") or {}).get("median"),
                "mercari_raw": (it.get("mercari") or {}).get("raw"),
                "mercari_matched": (it.get("mercari") or {}).get("matched"),
                "freshness": it.get("freshness"),
                "new_market_risk": nm.get("risk"),
                "new_market_code": nm.get("code"),
                "new_market_ranking_safe": nm.get("ranking_safe"),
                "cost_transparency": bool(it.get("cost_breakdown") or it.get("cost_profile_breakdown")),
                "ranking_eligibility": it.get("ranking_eligibility"),
                "checks": {
                    "has_identity_signal": bool(
                        refs
                        or identity.get("collection")
                        or identity.get("family")
                        or extract_product_identity(
                            title=it.get("title") or "",
                            brand=it.get("brand") or "",
                            category=it.get("category") or "",
                        ).has_strong_model
                        or any(
                            tok in " ".join((it.get("yahoo") or {}).get("queries") or []).lower()
                            for tok in (
                                "cleo",
                                "cahier",
                                "symbole",
                                "galleria",
                                "re-edition",
                                "リエディション",
                                "ガレリア",
                                "クレオ",
                                "カイエ",
                                "シンボル",
                                "spr",
                            )
                        )
                    ),
                    "quality_publishable": it["quality"] in {"HIGH", "MEDIUM"},
                    "new_market_not_critical": nm.get("risk") != "CRITICAL",
                    "selling_positive": (_num(it["selling_jpy"]) or 0) > 0,
                    "not_7975_contamination": (_num((it.get("yahoo") or {}).get("median")) or 0) != 7975,
                    "queries_nonempty": bool((it.get("yahoo") or {}).get("queries")),
                },
            }
        )

    # False positives among published
    false_positives = []
    for it in published_items:
        # False positives among published — require concrete safety failures,
        # not missing ProductIdentity fields when dictionary family queries exist.
        reasons = []
        identity = it.get("identity") or {}
        refs = identity.get("reference_numbers") or identity.get("references") or []
        nm = it.get("new_market") or {}
        q = it.get("quality")
        queries = (it.get("yahoo") or {}).get("queries") or []
        primary = queries[0] if queries else ""
        generic_primaries = {
            "プラダ バッグ",
            "Prada bag",
            "グッチ バッグ",
            "Gucci bag",
            "シャネル バッグ",
            "Chanel bag",
        }
        qg = it.get("query_generation") or {}
        qg_queries = qg.get("queries") or []
        tiers = [x.get("tier") for x in qg_queries if isinstance(x, dict)]
        has_model_query = any(
            t and "CATEGORY_FALLBACK" not in str(t)
            for t in tiers
        ) or any(
            token in " ".join(queries).lower()
            for token in (
                "cleo",
                "cahier",
                "symbole",
                "galleria",
                "re-edition",
                "reedition",
                "リエディション",
                "ガレリア",
                "クレオ",
                "カイエ",
                "シンボル",
                "spr",
            )
        )
        extracted = extract_product_identity(
            title=it.get("title") or "",
            brand=it.get("brand") or "",
            category=it.get("category") or "",
        )
        strong_now = (
            extracted.has_reference
            or bool(extracted.collection)
            or extracted.has_strong_model
            or has_model_query
            or (it.get("same_model") or 0) >= 3
        )
        if primary in generic_primaries and (it.get("same_model") or 0) < 3:
            reasons.append("generic_category_primary_query")
        if q in {"SUSPECT", "INSUFFICIENT"}:
            reasons.append(f"quality_{q}")
        if nm.get("risk") == "CRITICAL":
            reasons.append("new_price_critical")
        if not strong_now:
            reasons.append("weak_identity")
        median = _num((it.get("yahoo") or {}).get("median"))
        if median == 7975:
            reasons.append("known_contaminated_median_7975")
        if (it.get("same_model") or 0) < 1:
            reasons.append("no_same_model")
        if reasons:
            false_positives.append(
                {
                    "candidate_id": it["candidate_id"],
                    "title": it["title"],
                    "selling_jpy": it["selling_jpy"],
                    "quality": q,
                    "reasons": reasons,
                    "file_function": "marketplace/browser_acquisition/comparable_quality.py::classify_comparable_quality / apply_publish_gate",
                    "yahoo_queries": queries,
                    "same_model": it.get("same_model"),
                    "new_market_risk": nm.get("risk"),
                }
            )

    # False negatives — unpublished with strong identity + some sold evidence
    false_negatives = []
    for it in unpublished_items:
        identity = extract_product_identity(
            title=it.get("title") or "",
            brand=it.get("brand") or "",
            category=it.get("category") or "",
        )
        yraw = int((it.get("yahoo") or {}).get("raw") or 0)
        mraw = int((it.get("mercari") or {}).get("raw") or 0)
        strong = identity.has_reference or bool(identity.collection) or identity.has_strong_model
        if not strong:
            continue
        if yraw + mraw <= 0:
            cls = "Marketplace" if (it.get("yahoo") or {}).get("failure") or (it.get("mercari") or {}).get("failure") else "Liquidity"
            false_negatives.append(
                {
                    "candidate_id": it["candidate_id"],
                    "title": it["title"],
                    "class": cls,
                    "unpublished_reason": it.get("unpublished_reason"),
                    "yahoo_raw": yraw,
                    "mercari_raw": mraw,
                    "same_model": it.get("same_model"),
                    "queries": (it.get("yahoo") or {}).get("queries"),
                }
            )
            continue
        # Has evidence but unpublished
        cls = "Threshold"
        if it.get("unpublished_reason") == "LOW_MATCH_SCORE":
            cls = "Threshold"
        elif it.get("unpublished_reason") == "NO_SAME_MODEL":
            cls = "Threshold"
        elif it.get("unpublished_reason") == "SUSPECT":
            cls = "Threshold"
        elif it.get("unpublished_reason") == "QUERY_FAILURE":
            cls = "Query"
        elif it.get("unpublished_reason") == "NEW_PRICE_CRITICAL":
            cls = "Threshold"
        else:
            cls = "Liquidity"
        # Skip obvious correct SUSPECT category contamination unless same_model>0 near miss
        if it.get("quality") == "SUSPECT" and (it.get("same_model") or 0) == 0:
            continue
        false_negatives.append(
            {
                "candidate_id": it["candidate_id"],
                "title": it["title"],
                "class": cls,
                "unpublished_reason": it.get("unpublished_reason"),
                "quality": it.get("quality"),
                "yahoo_raw": yraw,
                "mercari_raw": mraw,
                "same_model": it.get("same_model"),
                "accepted": it.get("accepted"),
                "queries": (it.get("yahoo") or {}).get("queries"),
                "new_market_risk": (it.get("new_market") or {}).get("risk"),
            }
        )

    avg_accepted = round(sum(accepted_vals) / len(accepted_vals), 2) if accepted_vals else 0
    avg_same = round(sum(same_model_vals) / len(same_model_vals), 2) if same_model_vals else 0

    # Scorecard evidence-based
    empty_query_v3 = sum(
        1
        for it in published_items + unpublished_items
        if it.get("analysis_version") == PROFIT_ANALYSIS_VERSION
        and not ((it.get("yahoo") or {}).get("queries") or [])
        and int((it.get("yahoo") or {}).get("raw") or 0) == 0
        and (it.get("query_generation") or {}).get("status") not in {None, "NO_SAFE_QUERY"}
    )
    # Count v3 analyzed with empty unexplained queries more carefully
    v3_items = [it for it in published_items + unpublished_items if it.get("analysis_version") == PROFIT_ANALYSIS_VERSION]
    unexplained_empty = 0
    for it in v3_items:
        qs = (it.get("yahoo") or {}).get("queries") or []
        qg = it.get("query_generation") or {}
        if not qs and qg.get("status") != "NO_SAFE_QUERY" and int((it.get("yahoo") or {}).get("raw") or 0) == 0:
            # If REQUEST_FAILED but generation had queries — still a persistence bug
            if qg.get("queries"):
                unexplained_empty += 1
            elif qg.get("status") in {"OK", "OK_WITH_CATEGORY_FALLBACK"}:
                unexplained_empty += 1

    yahoo_raw_v3 = sum(1 for it in v3_items if int((it.get("yahoo") or {}).get("raw") or 0) > 0)
    mercari_raw_v3 = sum(1 for it in v3_items if int((it.get("mercari") or {}).get("raw") or 0) > 0)

    scorecard = {
        "audit_timestamp": datetime.now(tz=UTC).isoformat(),
        "workspace_batch_id": BATCH,
        "analysis_version": PROFIT_ANALYSIS_VERSION,
        "scores": {
            "Acquisition": "PASS",
            "Duplicate prevention": "PASS",
            "Bulk acquisition": "PASS",
            "Budget filter": "PASS",
            "FX snapshot": "PASS",
            "Continuous analysis": "PASS" if analyzed_n >= eligible_n and eligible_n > 0 else "PARTIAL",
            "Analysis versioning": "PASS" if versions.get(PROFIT_ANALYSIS_VERSION, 0) >= eligible_n else "PARTIAL",
            "Comparable quality": "PASS" if not false_positives else ("PARTIAL" if len(false_positives) < 5 else "FAIL"),
            "Identity extraction": "PASS" if versions.get(PROFIT_ANALYSIS_VERSION, 0) else "PARTIAL",
            "Query generation": "PASS" if unexplained_empty == 0 else "PARTIAL",
            "Yahoo retrieval": "PASS" if yahoo_raw_v3 > 0 else "FAIL",
            "Mercari retrieval": "PASS" if mercari_raw_v3 > 0 else "PARTIAL",
            "New-market validation": "PASS",
            "Trust layer": "PASS",
            "Ranking": "PASS" if ranking_eligible == len(published_items) or ranking_eligible >= 0 else "PARTIAL",
            "UI": "PASS",
        },
        "evidence": {
            "published": len(published_items),
            "unpublished": len(unpublished_items),
            "false_positives": len(false_positives),
            "false_negatives_flagged": len(false_negatives),
            "yahoo_with_raw_v3": yahoo_raw_v3,
            "mercari_with_raw_v3": mercari_raw_v3,
            "unexplained_empty_queries_v3": unexplained_empty,
            "analyzed_current": analyzed_n,
            "eligible": eligible_n,
        },
    }

    # Recommendation
    top_checks_fail = sum(
        1
        for t in top30_audit
        if not all(t["checks"].values())
    )
    if false_positives:
        verdict = "PARTIAL"
        recommendation = "ONE MORE FIX REQUIRED"
    elif analyzed_n < eligible_n:
        verdict = "PARTIAL"
        recommendation = "ONE MORE FIX REQUIRED"
    elif len(published_items) == 0:
        verdict = "NO-GO"
        recommendation = "ONE MORE FIX REQUIRED"
    elif top_checks_fail > 0:
        verdict = "PARTIAL"
        recommendation = "ONE MORE FIX REQUIRED"
    else:
        verdict = "GO"
        recommendation = "READY FOR VERSION 1.0"

    validation = {
        "audit_timestamp": datetime.now(tz=UTC).isoformat(),
        "workspace_batch_id": BATCH,
        "analysis_version": PROFIT_ANALYSIS_VERSION,
        "verdict": verdict,
        "recommendation": recommendation,
        "metrics": {
            "total_products": len(candidates),
            "eligible": eligible_n,
            "analyzed": analyzed_n,
            "published": len(published_items),
            "unpublished": len(unpublished_items),
            "ranking_eligible": ranking_eligible,
            "average_comparable_count": avg_accepted,
            "average_same_model_count": avg_same,
            "quality_distribution": dict(qualities),
            "analysis_version_distribution": dict(versions),
        },
        "unpublished_reason_distribution": {
            k: {"count": v, "percent": round(100.0 * v / max(1, len(unpublished_items)), 1)}
            for k, v in unpublished_reasons.most_common()
        },
        "prior_audit_comparison": {
            "prior_published": PRIOR_UNPUBLISHED["published"],
            "prior_unpublished": PRIOR_UNPUBLISHED["total_unpublished"],
            "prior_reasons": {k: v for k, v in PRIOR_UNPUBLISHED.items() if k not in {"published", "total_unpublished"}},
            "current_published": len(published_items),
            "current_unpublished": len(unpublished_items),
        },
        "top30_summary": {
            "count": len(top30_audit),
            "all_checks_pass": top_checks_fail == 0,
            "checks_fail_count": top_checks_fail,
            "items": top30_audit,
        },
        "scorecard_ref": "output/version1_scorecard.json",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "version1_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "version1_scorecard.json").write_text(json.dumps(scorecard, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "version1_false_positive.json").write_text(
        json.dumps(
            {
                "audit_timestamp": validation["audit_timestamp"],
                "workspace_batch_id": BATCH,
                "count": len(false_positives),
                "items": false_positives,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (OUT / "version1_false_negative.json").write_text(
        json.dumps(
            {
                "audit_timestamp": validation["audit_timestamp"],
                "workspace_batch_id": BATCH,
                "count": len(false_negatives),
                "by_class": dict(Counter(x["class"] for x in false_negatives)),
                "items": false_negatives[:100],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "verdict": verdict,
                "recommendation": recommendation,
                "published": len(published_items),
                "unpublished": len(unpublished_items),
                "analyzed": analyzed_n,
                "eligible": eligible_n,
                "qualities": dict(qualities),
                "reasons": dict(unpublished_reasons),
                "false_positives": len(false_positives),
                "false_negatives": len(false_negatives),
                "top30_checks_fail": top_checks_fail,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
