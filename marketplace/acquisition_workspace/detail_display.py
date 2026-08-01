"""Presentation builder for acquisition workspace candidate detail pages.

Uses existing stored values only. Does not calculate profit or change ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from marketplace.acquisition_workspace.price_display import (
    format_yen,
    resolve_purchase_text,
    split_brand_title,
)


@dataclass(frozen=True, slots=True)
class SourcingDetailView:
    """View model for the sourcing decision detail page."""

    candidate_id: str
    batch_id: str
    demo_mode: bool
    brand: str
    product_name: str
    category: str
    marketplace: str
    overall_score: str
    net_profit: str
    roi: str
    confidence: str
    purchase_price: str
    selling_price: str
    profit: str
    analysis: str
    purchase_url: str
    back_url: str
    breakdown: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sales_info: list[tuple[str, str]] = field(default_factory=list)
    analysis_positives: list[str] = field(default_factory=list)
    analysis_cautions: list[str] = field(default_factory=list)
    analysis_summary: list[str] = field(default_factory=list)


def build_sourcing_detail(
    *,
    candidate,
    rank=None,
    batch_id: str = "",
    demo_mode: bool = False,
    selling_estimate: Decimal | None = None,
    batch_result=None,
    demo_detail: dict | None = None,
) -> SourcingDetailView:
    """Assemble a detail view from existing candidate / ranking / batch values."""
    brand, product_name = split_brand_title(candidate.brand, candidate.title)
    purchase = resolve_purchase_text(candidate)
    if selling_estimate is None and batch_result is not None:
        selling = "算出不可"
    else:
        selling = format_yen(selling_estimate)
        if selling == "-" and batch_result is not None:
            selling = "算出不可"
    profit = _resolve_profit_text(candidate, rank)
    roi = _resolve_roi_text(candidate, rank)
    confidence = "-"
    overall = "-"
    analysis = "まだ分析結果はありません。"
    if rank is not None:
        overall = str(rank.overall_score) if rank.overall_score is not None else "-"
        confidence = rank.confidence_level or "-"
        analysis = rank.analysis_summary or analysis
        if selling == "-" and getattr(rank, "source_listing_url", None):
            pass
    else:
        confidence = candidate.data_truth_summary.confidence_level or "-"
        if candidate.last_warning:
            analysis = candidate.last_warning

    if demo_detail and demo_detail.get("analysis"):
        analysis = str(demo_detail["analysis"])

    warnings = _collect_warnings(candidate, rank, demo_detail)
    breakdown = _build_breakdown(candidate, rank, batch_result, demo_detail, selling, profit)
    sales_info = _build_sales_info(candidate, rank, batch_result, demo_detail)
    trust_rows = _trust_summary_rows(batch_result)
    cost_settings = _cost_settings_rows(batch_result, candidate=candidate)
    # Trust + cost transparency first, then market evidence.
    extras: list[tuple[str, str]] = []
    if trust_rows:
        extras.extend(trust_rows)
    if cost_settings:
        extras.extend(cost_settings)
    if extras:
        sales_info = [*extras, *sales_info]
    positives, cautions, summary_parts = split_analysis_sections(analysis)

    back_url = "/acquisition-workspace"
    if batch_id and not demo_mode:
        back_url = f"/acquisition-workspace?batch_id={batch_id}"
    elif demo_mode:
        back_url = "/acquisition-workspace"

    return SourcingDetailView(
        candidate_id=candidate.candidate_id,
        batch_id=batch_id,
        demo_mode=demo_mode,
        brand=brand or (candidate.brand or "-"),
        product_name=product_name or candidate.title,
        category=candidate.category or "-",
        marketplace=candidate.source_name or candidate.source_type or "-",
        overall_score=overall,
        net_profit=profit,
        roi=roi,
        confidence=confidence,
        purchase_price=purchase,
        selling_price=selling,
        profit=profit,
        analysis=analysis,
        purchase_url=candidate.purchase_url or "",
        back_url=back_url,
        breakdown=breakdown,
        warnings=warnings,
        sales_info=sales_info,
        analysis_positives=positives,
        analysis_cautions=cautions,
        analysis_summary=summary_parts,
    )


def split_analysis_sections(analysis: str) -> tuple[list[str], list[str], list[str]]:
    """Reorganize existing analysis text into display sections without inventing content."""
    text = str(analysis or "").strip()
    if not text:
        return [], [], []

    sentences = _split_analysis_sentences(text)
    if not sentences:
        return [], [], [text]

    positives: list[str] = []
    cautions: list[str] = []
    summary: list[str] = []
    positive_markers = (
        "高め",
        "高く",
        "プラス",
        "安定",
        "販売実績があります",
        "良好",
        "利益率が高く",
        "回転が良く",
        "再販しやすい",
    )
    caution_markers = (
        "低め",
        "マイナス",
        "不確実",
        "確認",
        "ゼロ以下",
        "ありません",
        "算出できません",
        "平均以下",
        "要確認",
        "真贋",
    )
    for sentence in sentences:
        if any(marker in sentence for marker in caution_markers):
            cautions.append(sentence)
        elif any(marker in sentence for marker in positive_markers):
            positives.append(sentence)
        else:
            summary.append(sentence)

    if not positives and not cautions and not summary:
        summary = [text]
    return positives, cautions, summary


def _split_analysis_sentences(text: str) -> list[str]:
    normalized = text.replace("。", "。\n").replace(". ", ".\n")
    parts: list[str] = []
    for chunk in normalized.split("\n"):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def resolve_batch_result_for_candidate(
    candidate,
    *,
    database_path: Path | str | None = None,
):
    """Load an existing batch profit result for a candidate when available."""
    batch_id = getattr(candidate, "last_profit_batch_id", "") or ""
    if not batch_id:
        return None
    from app.storage.batch_profit_repository import BatchProfitRepository

    run = BatchProfitRepository(database_path=database_path).get_run(batch_id)
    if run is None:
        return None
    for item in run.results:
        if item.candidate.candidate_id == candidate.candidate_id:
            return item
    return None


def resolve_selling_from_batch_result(batch_result) -> Decimal | None:
    if batch_result is None:
        return None
    trace = getattr(batch_result, "operational_trace", None) or {}
    profit = trace.get("profit") if isinstance(trace, dict) else {}
    quality = {}
    if isinstance(profit, dict):
        quality = profit.get("comparable_quality") or {}
    publish = bool(quality.get("publish_price", True))
    qlabel = str(quality.get("quality") or "")
    warning = getattr(batch_result.domestic, "comparable_warning", "") or ""
    recommended = batch_result.domestic.recommended_selling_estimate_jpy
    if (
        (not publish)
        or qlabel in {"SUSPECT", "INSUFFICIENT"}
        or warning in {"COMPARABLE_DATA_SUSPECT", "COMPARABLE_DATA_INSUFFICIENT"}
        or recommended is None
        or recommended <= 0
    ):
        return None
    return recommended


def _resolve_profit_text(candidate, rank) -> str:
    if rank is not None and rank.net_profit is not None:
        return format_yen(rank.net_profit)
    if candidate.last_net_profit is not None:
        return format_yen(candidate.last_net_profit)
    if candidate.last_gross_profit is not None:
        return format_yen(candidate.last_gross_profit)
    return "-"


def _resolve_roi_text(candidate, rank) -> str:
    if rank is not None and rank.roi is not None:
        return f"{rank.roi}%"
    return "-"


def _collect_warnings(candidate, rank, demo_detail: dict | None) -> list[str]:
    warnings: list[str] = []
    for item in getattr(candidate, "validation_warnings", ()) or ():
        if item:
            warnings.append(str(item))
    if rank is not None:
        for item in getattr(rank, "ranking_warnings", ()) or ():
            if item:
                warnings.append(str(item))
    truth = candidate.data_truth_summary
    if truth.used_estimated_price:
        warnings.append("価格推定")
    if truth.used_estimated_shipping:
        warnings.append("送料推定")
    if demo_detail:
        for item in demo_detail.get("warnings", ()) or ():
            if item:
                warnings.append(str(item))
    # De-dupe while preserving order
    return list(dict.fromkeys(warnings))


def _build_breakdown(candidate, rank, batch_result, demo_detail, selling: str, profit: str) -> list[tuple[str, str]]:
    if demo_detail and demo_detail.get("breakdown"):
        return [(str(label), str(value)) for label, value in demo_detail["breakdown"]]

    if batch_result is not None:
        calculator_rows = _calculator_breakdown_rows(batch_result, profit)
        if calculator_rows is not None:
            return calculator_rows

        reconstructed = _reconstruct_calculator_breakdown(candidate, batch_result, profit)
        if reconstructed is not None:
            return reconstructed

        costs = batch_result.estimated_costs
        selling_value = format_yen(batch_result.domestic.recommended_selling_estimate_jpy)
        if selling_value == "-":
            selling_value = "算出不可"
        net = (
            format_yen(batch_result.net_estimated_profit)
            if batch_result.net_estimated_profit is not None
            else format_yen(batch_result.gross_estimated_profit)
        )
        purchase = format_yen(getattr(batch_result.candidate, "purchase_price_jpy", None) or candidate.purchase_price_jpy)
        fee_label = _marketplace_fee_label(batch_result=batch_result, domestic_market="")
        return [
            ("予測販売価格", selling_value),
            ("仕入価格", purchase),
            ("国際送料（CostProfile）", _format_yen_allow_zero(costs.international_shipping_jpy)),
            ("関税（CostProfile）", _format_yen_allow_zero(costs.import_duty_jpy)),
            ("輸入消費税（CostProfile）", _format_yen_allow_zero(costs.import_tax_jpy)),
            ("国内送料（CostProfile）", _format_yen_allow_zero(costs.domestic_shipping_jpy)),
            (f"{fee_label}（CostProfile）", _format_yen_allow_zero(costs.domestic_platform_fee_jpy)),
            ("決済手数料（CostProfile）", _format_yen_allow_zero(costs.payment_fee_jpy)),
            ("転送手数料（CostProfile）", _format_yen_allow_zero(costs.forwarding_fee_jpy)),
            ("検品・修理準備金（CostProfile）", _format_yen_allow_zero(costs.inspection_or_repair_reserve_jpy)),
            ("その他費用（CostProfile）", _format_yen_allow_zero(costs.miscellaneous_cost_jpy)),
            ("表示利益", net),
        ]

    purchase = resolve_purchase_text(candidate)
    return [
        ("予測販売価格", selling),
        ("仕入価格", purchase),
        ("国際送料", "-"),
        ("関税", "-"),
        ("輸入消費税", "-"),
        ("国内送料", "-"),
        ("国内販売手数料", "-"),
        ("決済手数料", "-"),
        ("保険", "-"),
        ("梱包費", "-"),
        ("その他費用", "-"),
        ("表示利益", profit),
    ]


def _calculator_breakdown_rows(batch_result, fallback_profit: str) -> list[tuple[str, str]] | None:
    """Prefer ProfitCalculator/ImportCostEngine lines when persisted on the result."""
    trace = getattr(batch_result, "operational_trace", None) or {}
    profit_trace = trace.get("profit") if isinstance(trace, dict) else None
    breakdown = None
    if isinstance(profit_trace, dict):
        breakdown = profit_trace.get("cost_breakdown")
    if not isinstance(breakdown, dict):
        return None
    if breakdown.get("source") != "ProfitCalculator/ImportCostEngine":
        return None

    selling = format_yen(batch_result.domestic.recommended_selling_estimate_jpy)
    if selling == "-":
        selling = format_yen(batch_result.domestic.median_jpy)
    if selling == "-" and isinstance(profit_trace, dict) and profit_trace.get("domestic_predicted_sale_price_jpy"):
        selling = format_yen(profit_trace.get("domestic_predicted_sale_price_jpy"))

    domestic_market = str(breakdown.get("domestic_market") or "")
    return _rows_from_calculator_amounts(
        selling=selling,
        purchase=breakdown.get("purchase_price_jpy"),
        international_shipping=breakdown.get("international_shipping_jpy"),
        customs_duty=breakdown.get("customs_duty_jpy"),
        import_tax=breakdown.get("import_tax_jpy"),
        domestic_shipping=breakdown.get("domestic_shipping_jpy"),
        marketplace_fee=breakdown.get("marketplace_fee_jpy"),
        payment_fee=breakdown.get("payment_fee_jpy", "0"),
        insurance=breakdown.get("insurance_jpy", "0"),
        packaging=breakdown.get("packaging_jpy", "0"),
        other_costs=breakdown.get("other_costs_jpy"),
        profit_jpy=breakdown.get("profit_jpy"),
        batch_result=batch_result,
        fallback_profit=fallback_profit,
        incomplete_note=_incomplete_note(profit_trace),
        domestic_market=domestic_market,
    )


def _reconstruct_calculator_breakdown(candidate, batch_result, fallback_profit: str) -> list[tuple[str, str]] | None:
    """Display-only replay of ProfitCalculator for older runs that lack engine cost lines."""
    selling_price = resolve_selling_from_batch_result(batch_result)
    purchase_price = getattr(candidate, "purchase_price", None)
    currency = str(getattr(candidate, "currency", "") or "USD")
    if selling_price is None or selling_price <= 0 or purchase_price is None:
        return None
    try:
        from models.product import Product
        from price_compare.profit_calculator import ProfitCalculator

        exchange = None
        costs = getattr(batch_result, "estimated_costs", None)
        if costs is not None and getattr(costs, "exchange_rate", None):
            # e.g. "160 JPY/USD"
            raw = str(costs.exchange_rate).split()[0]
            exchange = float(raw)
        product = Product(
            name=str(getattr(candidate, "title", "") or "item"),
            brand=str(getattr(candidate, "brand", "") or ""),
            price=float(purchase_price),
            currency=currency,
            store_name=str(getattr(candidate, "source_name", "") or getattr(candidate, "purchase_source", "") or ""),
            url=str(getattr(candidate, "purchase_url", "") or ""),
            exchange_rate=exchange,
        )
        # Match batch pipeline: fee schedule is resolved for yahoo_auction.
        result = ProfitCalculator().calculate(product, selling_price, domestic_market="yahoo_auction")
    except Exception:
        return None
    if result.profit_jpy is None:
        return None
    return _rows_from_calculator_amounts(
        selling=format_yen(selling_price),
        purchase=result.purchase_price_jpy,
        international_shipping=result.international_shipping_jpy,
        customs_duty=result.customs_duty_jpy,
        import_tax=result.import_tax_jpy,
        domestic_shipping=result.domestic_shipping_jpy,
        marketplace_fee=result.marketplace_fee_jpy,
        payment_fee=Decimal("0"),
        insurance=Decimal("0"),
        packaging=Decimal("0"),
        other_costs=result.other_costs_jpy,
        profit_jpy=result.profit_jpy,
        batch_result=batch_result,
        fallback_profit=fallback_profit,
        incomplete_note="（表示用に ImportCostEngine を再構成）",
        domestic_market=str(result.domestic_market or "yahoo_auction"),
    )


def _incomplete_note(profit_trace: dict | None) -> str:
    if not isinstance(profit_trace, dict):
        return ""
    profile_bd = profit_trace.get("cost_profile_breakdown")
    if isinstance(profile_bd, dict) and not profile_bd.get("net_profit_complete", True):
        return "（CostProfile未完了のため ImportCostEngine 基準）"
    return ""


def _trust_summary_rows(batch_result) -> list[tuple[str, str]]:
    if batch_result is None:
        return []
    trace = getattr(batch_result, "operational_trace", None) or {}
    profit = trace.get("profit") if isinstance(trace, dict) else {}
    if not isinstance(profit, dict):
        return []
    from marketplace.acquisition_workspace.trust_display import trust_summary_from_profit_trace

    summary = trust_summary_from_profit_trace(profit)
    return list(summary.display_rows)


def _cost_settings_rows(batch_result, *, candidate=None) -> list[tuple[str, str]]:
    """Display CostProfile rates/amounts without changing calculations."""
    if batch_result is None:
        return []
    trace = getattr(batch_result, "operational_trace", None) or {}
    profit = trace.get("profit") if isinstance(trace, dict) else {}
    profile = profit.get("cost_profile_breakdown") if isinstance(profit, dict) else {}
    if not isinstance(profile, dict) or not profile:
        return []

    def _pct(rate) -> str:
        if rate is None or rate == "":
            return "-"
        try:
            value = Decimal(str(rate))
            return f"{(value * 100).quantize(Decimal('1'))}%"
        except Exception:
            return str(rate)

    purchase = "-"
    if candidate is not None:
        purchase = format_yen(getattr(candidate, "purchase_price_jpy", None))
    if purchase == "-" and hasattr(batch_result, "candidate"):
        purchase = format_yen(getattr(batch_result.candidate, "purchase_price_jpy", None))

    rows = [
        ("輸入コスト詳細", str(profile.get("calculation_source") or "標準CostProfile")),
        ("商品", purchase if purchase != "-" else _format_yen_allow_zero(profit.get("overseas_price_jpy"))),
        ("送料", _format_yen_allow_zero(profile.get("international_shipping_jpy"))),
        ("関税", _pct(profile.get("import_duty_rate"))),
        ("輸入消費税", _pct(profile.get("import_tax_rate"))),
        ("国内送料", _format_yen_allow_zero(profile.get("domestic_shipping_jpy"))),
        ("販売手数料", _pct(profile.get("domestic_platform_fee_rate"))),
        ("決済手数料", _pct(profile.get("payment_fee_rate")) if profile.get("payment_fee_rate") is not None else _format_yen_allow_zero(profile.get("payment_fee_jpy"))),
    ]
    rows.extend(_new_market_validation_rows(profit if isinstance(profit, dict) else {}))
    return rows


def _new_market_validation_rows(profit: dict) -> list[tuple[str, str]]:
    """Transparent used-vs-new price check display."""
    validation = profit.get("new_market_validation") if isinstance(profit, dict) else None
    warning = profit.get("new_market_warning") if isinstance(profit, dict) else None
    payload = validation if isinstance(validation, dict) and validation.get("risk") not in {None, "", "NONE"} else warning
    if not isinstance(payload, dict):
        return []
    risk = str(payload.get("risk") or "")
    if risk in {"", "NONE"} and not payload.get("new_market_warning"):
        return []
    used = int(payload.get("used_predicted_price_jpy") or payload.get("used_estimate_jpy") or 0)
    new_price = payload.get("new_market_price_jpy")
    label = str(payload.get("display_label") or "販売価格チェック")
    rows: list[tuple[str, str]] = [("販売価格チェック", label)]
    if used > 0:
        rows.append(("中古予想", f"¥{used:,}"))
    if new_price is not None:
        rows.append(("新品参考", f"¥{int(new_price):,}"))
    if risk == "NORMAL":
        rows.append(("判定", "正常"))
    elif risk == "WARNING":
        rows.append(("理由", str(payload.get("reason") or payload.get("warning") or "新品価格が中古予想を下回っています")))
    elif risk == "CRITICAL":
        rows.append(("利益ランキング", "注意"))
        rows.append(("理由", str(payload.get("reason") or payload.get("warning") or "新品価格が中古予想を大きく下回っています")))
    marketplace = payload.get("marketplace") or ""
    if marketplace:
        rows.append(("新品ソース", str(marketplace)))
    return rows


def _marketplace_fee_label(*, batch_result, domestic_market: str) -> str:
    """Label the selling fee with the market actually used by ProfitCalculator."""
    market = (domestic_market or "").strip().lower()
    if not market:
        trace = getattr(batch_result, "operational_trace", None) or {}
        profit = trace.get("profit") if isinstance(trace, dict) else None
        if isinstance(profit, dict):
            breakdown = profit.get("cost_breakdown") if isinstance(profit.get("cost_breakdown"), dict) else {}
            market = str(breakdown.get("domestic_market") or "").strip().lower()
    if not market:
        # Batch pipeline currently always calculates fees with yahoo_auction config.
        # Do not infer from comparable marketplace (Yahoo/Mercari comps ≠ fee schedule).
        market = "yahoo_auction"
    if "ebay" in market:
        return "eBay販売手数料"
    if "mercari" in market:
        return "メルカリ販売手数料"
    if "yahoo" in market:
        return "Yahooオークション販売手数料"
    return "国内販売手数料"


def _rows_from_calculator_amounts(
    *,
    selling: str,
    purchase,
    international_shipping,
    customs_duty,
    import_tax,
    domestic_shipping,
    marketplace_fee,
    payment_fee,
    insurance,
    packaging,
    other_costs,
    profit_jpy,
    batch_result,
    fallback_profit: str,
    incomplete_note: str,
    domestic_market: str = "",
) -> list[tuple[str, str]]:
    profit_value = format_yen(profit_jpy)
    if profit_value == "-":
        profit_value = (
            format_yen(batch_result.net_estimated_profit)
            if batch_result.net_estimated_profit is not None
            else format_yen(batch_result.gross_estimated_profit)
        )
    if profit_value == "-":
        profit_value = fallback_profit

    fee_label = _marketplace_fee_label(batch_result=batch_result, domestic_market=domestic_market)

    # Always show every ProfitCalculator cost line, including zeros — no hidden deductions.
    # PriceResult.other_costs_jpy already includes payment+insurance+packaging+other;
    # when those inputs are zero (current defaults), show the rolled-up line as ¥0 and
    # also show the explicit zero ancillary lines for audit transparency.
    other_amount = _to_decimal_amount(other_costs) or Decimal("0")
    payment_amount = _to_decimal_amount(payment_fee) or Decimal("0")
    insurance_amount = _to_decimal_amount(insurance) or Decimal("0")
    packaging_amount = _to_decimal_amount(packaging) or Decimal("0")
    # Avoid double-counting in the displayed sum when other_costs already includes ancillaries.
    # ProfitCalculator reports other_costs_jpy = payment + insurance + packaging + other.
    # Display ancillaries individually and show residual "その他固定費" only.
    residual_other = other_amount - payment_amount - insurance_amount - packaging_amount
    if residual_other < 0:
        residual_other = Decimal("0")

    rows = [
        ("予測販売価格", selling),
        ("仕入価格", _format_yen_allow_zero(purchase)),
        ("国際送料", _format_yen_allow_zero(international_shipping)),
        ("関税", _format_yen_allow_zero(customs_duty)),
        ("輸入消費税", _format_yen_allow_zero(import_tax)),
        ("国内送料", _format_yen_allow_zero(domestic_shipping)),
        (fee_label, _format_yen_allow_zero(marketplace_fee)),
        ("決済手数料", _format_yen_allow_zero(payment_amount)),
        ("保険", _format_yen_allow_zero(insurance_amount)),
        ("梱包費", _format_yen_allow_zero(packaging_amount)),
        ("その他固定費", _format_yen_allow_zero(residual_other)),
        (f"最終利益{incomplete_note}", profit_value),
    ]
    return rows


def reconcile_breakdown_rows(rows: list[tuple[str, str]]) -> dict[str, Decimal]:
    """Parse displayed breakdown rows and verify sale - purchase - costs = profit."""
    labels = dict(rows)
    selling = _parse_yen_label(labels.get("予測販売価格") or labels.get("販売価格"))
    purchase = _parse_yen_label(labels.get("仕入価格"))
    profit_key = next((k for k in labels if k.startswith("最終利益") or k in {"表示利益", "純利益"}), None)
    profit = _parse_yen_label(labels.get(profit_key)) if profit_key else None
    cost_total = Decimal("0")
    for label, value in rows:
        if label in {"予測販売価格", "販売価格", "仕入価格"} or label.startswith("最終利益") or label in {
            "表示利益",
            "純利益",
        }:
            continue
        amount = _parse_yen_label(value)
        if amount is not None:
            cost_total += amount
    expected_profit = None
    if selling is not None and purchase is not None:
        expected_profit = selling - purchase - cost_total
    return {
        "selling": selling or Decimal("0"),
        "purchase": purchase or Decimal("0"),
        "cost_total": cost_total,
        "displayed_profit": profit or Decimal("0"),
        "expected_profit": expected_profit or Decimal("0"),
        "reconciles": bool(
            selling is not None
            and purchase is not None
            and profit is not None
            and expected_profit == profit
        ),
    }


def _parse_yen_label(value: str | None) -> Decimal | None:
    if value is None or value in {"", "-"}:
        return None
    cleaned = str(value).replace("¥", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _to_decimal_amount(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _format_yen_allow_zero(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        amount = Decimal(str(value))
    except Exception:
        return "-"
    if amount < 0:
        return "-"
    return f"¥{int(amount):,}"


def _first_existing_yen(*values) -> str:
    for value in values:
        text = format_yen(value)
        if text != "-":
            return text
    return "-"


def _build_sales_info(candidate, rank, batch_result, demo_detail) -> list[tuple[str, str]]:
    if demo_detail and demo_detail.get("sales_info"):
        return [(str(label), str(value)) for label, value in demo_detail["sales_info"]]

    listing_info = _build_listing_info(candidate)

    sold = "-"
    median = "-"
    minimum = "-"
    maximum = "-"
    confidence = candidate.data_truth_summary.confidence_level or "-"

    if rank is not None:
        sold = str(rank.sales_count)
        confidence = rank.confidence_level or confidence

    if batch_result is not None:
        domestic = batch_result.domestic
        sold = str(domestic.accepted_count if domestic.accepted_count else batch_result.accepted_comparable_count)
        median = format_yen(domestic.median_jpy)
        minimum = format_yen(domestic.minimum_jpy)
        maximum = format_yen(domestic.maximum_jpy)
        confidence = domestic.reliability or confidence
        quality_rows: list[tuple[str, str]] = []
        trace = getattr(batch_result, "operational_trace", None) or {}
        profit = trace.get("profit") if isinstance(trace, dict) else {}
        quality = profit.get("comparable_quality") if isinstance(profit, dict) else {}
        if isinstance(quality, dict) and quality:
            from marketplace.acquisition_workspace.trust_display import format_latest_sold_display

            latest_raw = str(quality.get("latest_sold_date") or "")
            quality_rows = [
                ("販売予想根拠", ""),
                ("比較件数", f"{quality.get('sold_confirmed_count', sold)}件"),
                ("同一モデル", f"{quality.get('same_model_matches', '-')}件"),
                ("マーケット", str(quality.get("marketplaces") or "Yahoo Auction")),
                ("データ期間", str(quality.get("freshness_label") or "-")),
                ("最新販売", format_latest_sold_display(latest_raw)),
                ("品質", str(quality.get("quality") or "-")),
                ("価格公開", "可" if quality.get("publish_price") else "不可"),
                ("理由", str(quality.get("reason") or "-")),
            ]
            if not quality.get("publish_price"):
                median = "算出不可"
        return [
            *listing_info,
            ("Sold件数", sold),
            ("中央値", median),
            ("最低価格", minimum),
            ("最高価格", maximum),
            ("Confidence", confidence),
            *quality_rows,
            *_build_yahoo_match_info(batch_result),
        ]
    else:
        comparable = candidate.discovery_metadata.comparable_count
        if comparable:
            sold = str(comparable)

    return [
        *listing_info,
        ("Sold件数", sold),
        ("中央値", median),
        ("最低価格", minimum),
        ("最高価格", maximum),
        ("Confidence", confidence),
        *_build_yahoo_match_info(batch_result),
    ]


def _build_yahoo_match_info(batch_result) -> list[tuple[str, str]]:
    """Selected marketplace comparable rows for Market Information (existing layout)."""
    if batch_result is None:
        return []
    title = getattr(batch_result, "yahoo_best_title", "") or ""
    if not title:
        return []
    price = format_yen(getattr(batch_result, "yahoo_best_price_jpy", 0) or None)
    url = getattr(batch_result, "yahoo_best_url", "") or "-"
    score = getattr(batch_result, "yahoo_best_score", 0) or 0
    attrs = getattr(batch_result, "yahoo_best_attributes", "") or "-"
    marketplace = getattr(batch_result, "yahoo_marketplace", "") or "Yahoo Auctions"
    profit = "-"
    net = getattr(batch_result, "net_estimated_profit", None)
    gross = getattr(batch_result, "gross_estimated_profit", None)
    if net is not None:
        profit = format_yen(net)
    elif gross is not None:
        profit = format_yen(gross)
    return [
        ("Marketplace", marketplace),
        ("Title", title),
        ("Price", price),
        ("URL", url),
        ("Matching confidence", str(score) if score else "-"),
        ("Matched attributes", attrs),
        ("Profit", profit),
    ]


def _build_listing_info(candidate) -> list[tuple[str, str]]:
    """Overseas listing facts for the detail Market Information section."""
    marketplace = candidate.source_name or candidate.source_type or "-"
    currency = (candidate.currency or "-").strip() or "-"
    price = "-"
    if candidate.purchase_price is not None:
        try:
            amount = candidate.purchase_price
            if amount > 0:
                if amount == amount.to_integral_value():
                    price = f"{int(amount):,}"
                else:
                    price = f"{amount}"
        except Exception:
            price = str(candidate.purchase_price)
    original = f"{price} {currency}".strip() if price != "-" else "-"
    jpy = format_yen(getattr(candidate, "purchase_price_jpy", None))
    condition = (
        getattr(candidate, "detected_condition", "")
        or getattr(candidate, "condition", "")
        or "-"
    )
    if not str(condition).strip():
        condition = "-"
    url = candidate.purchase_url or "-"
    retrieved = getattr(candidate, "acquired_at", None) or getattr(candidate, "imported_at", None) or "-"
    return [
        ("Marketplace", marketplace),
        ("Price", price),
        ("Currency", currency),
        ("Condition", str(condition)),
        ("Listing URL", url),
        ("Retrieved", retrieved),
        ("Original price", original),
        ("Converted JPY", jpy),
    ]
