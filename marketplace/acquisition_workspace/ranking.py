"""Used listing ranking MVP for acquisition workspace candidates.

Normalization behavior (set-relative, deterministic):
- Profit/ROI/demand scores are min-max scaled across the eligible candidate set.
- When a metric set is empty, all equal, or has a non-positive max, scores fall back
  to 0 (or 100 only when every eligible value is identical and positive for profit/ROI).
- Negative profit and negative/zero ROI always map to the lowest score (0).
- Missing/zero sales count maps to demand score 0.
- Confidence maps fixed labels: HIGH=100, MEDIUM=60, LOW=25.
- Overall score uses fixed weights Profit 35%, ROI 30%, Demand 20%, Confidence 15%.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from marketplace.acquisition_workspace.models import AcquisitionCandidate, ConfidenceLevel

WEIGHT_PROFIT = Decimal("0.35")
WEIGHT_ROI = Decimal("0.30")
WEIGHT_DEMAND = Decimal("0.20")
WEIGHT_CONFIDENCE = Decimal("0.15")

CONFIDENCE_SCORE_MAP = {
    ConfidenceLevel.HIGH.value: Decimal("100"),
    ConfidenceLevel.MEDIUM.value: Decimal("60"),
    ConfidenceLevel.LOW.value: Decimal("25"),
}


@dataclass(frozen=True, slots=True)
class UsedListingRankResult:
    """One ranked used-listing candidate for MVP display and export."""

    candidate_id: str
    title: str
    rank: int
    overall_score: Decimal
    profit_score: Decimal
    roi_score: Decimal
    demand_score: Decimal
    confidence_score: Decimal
    net_profit: Decimal | None
    roi: Decimal | None
    sales_count: int
    confidence_level: str
    source_listing_url: str
    analysis_summary: str
    ranking_warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
            elif isinstance(value, tuple):
                payload[key] = list(value)
        return payload


def is_valid_source_listing_url(url: str | None) -> bool:
    """Return True when url is a non-empty HTTP or HTTPS listing URL."""
    if url is None:
        return False
    raw = str(url).strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_listing_url_warning(candidate: AcquisitionCandidate) -> str | None:
    if is_valid_source_listing_url(candidate.purchase_url):
        return None
    return "商品ページURLが未設定または無効です"


def resolve_net_profit(candidate: AcquisitionCandidate) -> Decimal | None:
    if candidate.last_net_profit is not None:
        return candidate.last_net_profit
    if candidate.last_gross_profit is not None:
        return candidate.last_gross_profit
    return None


def resolve_roi(candidate: AcquisitionCandidate, net_profit: Decimal | None) -> Decimal | None:
    """ROI as percent of purchase_price_jpy. None when profit or purchase price is unavailable."""
    if net_profit is None:
        return None
    if candidate.purchase_price_jpy is None or candidate.purchase_price_jpy <= 0:
        return None
    return (net_profit / candidate.purchase_price_jpy * Decimal("100")).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )


def resolve_sales_count(candidate: AcquisitionCandidate) -> int:
    """Use accepted comparable / sold sample count as MVP demand proxy."""
    return max(0, int(candidate.discovery_metadata.comparable_count or 0))


def is_ranking_eligible(candidate: AcquisitionCandidate) -> bool:
    """Eligible when listing URL is valid and a profit result exists."""
    if not is_valid_source_listing_url(candidate.purchase_url):
        return False
    return resolve_net_profit(candidate) is not None


def confidence_to_score(level: str) -> Decimal:
    return CONFIDENCE_SCORE_MAP.get((level or "").upper(), Decimal("25"))


def clamp_score(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 100:
        return Decimal("100")
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _min_max_score(value: Decimal, values: list[Decimal], *, allow_zero_floor: bool = True) -> Decimal:
    if not values:
        return Decimal("0")
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        if allow_zero_floor and value <= 0:
            return Decimal("0")
        return Decimal("100") if value > 0 else Decimal("0")
    scaled = (value - minimum) / (maximum - minimum) * Decimal("100")
    return clamp_score(scaled)


def build_ranking_warnings(candidate: AcquisitionCandidate, *, net_profit: Decimal | None, sales_count: int) -> tuple[str, ...]:
    warnings: list[str] = []
    url_warning = source_listing_url_warning(candidate)
    if url_warning:
        warnings.append(url_warning)
    if net_profit is None:
        warnings.append("利益データがありません")
    if sales_count <= 0:
        warnings.append("販売実績がありません")
    confidence = (candidate.data_truth_summary.confidence_level or "").upper()
    if confidence == ConfidenceLevel.LOW.value:
        warnings.append("信頼度はLOWです")
    truth = candidate.data_truth_summary
    if truth.used_estimated_shipping or (truth.shipping_source or "").lower() == "estimated":
        warnings.append("送料は推定値です")
    if truth.used_estimated_price or "estimated" in (truth.comparable_source or "").lower():
        warnings.append("価格は推定値です")
    warnings.append("購入前に商品の状態・付属品をご確認ください")
    return tuple(dict.fromkeys(warnings))


def build_analysis_summary(
    *,
    net_profit: Decimal | None,
    roi: Decimal | None,
    sales_count: int,
    confidence_level: str,
    average_profit: Decimal | None,
    average_roi: Decimal | None,
    warnings: tuple[str, ...],
) -> str:
    """Deterministic two-to-four sentence analysis. Never issues a buy decision."""
    sentences: list[str] = []

    if net_profit is None:
        sentences.append("利益データがありません。")
    elif average_profit is not None and net_profit > average_profit:
        sentences.append("利益は比較的高めです。")
    elif average_profit is not None and net_profit > 0:
        sentences.append("利益はプラスですが、候補平均より低めです。")
    elif net_profit > 0:
        sentences.append("利益はプラスです。")
    else:
        sentences.append("利益は低め、またはマイナスです。")

    if roi is None:
        sentences.append("仕入価格からROIを算出できませんでした。")
    elif average_roi is not None and roi > average_roi:
        sentences.append("ROIは候補平均より高めです。")
    elif roi > 0:
        sentences.append("ROIはプラスですが、候補平均以下です。")
    else:
        sentences.append("ROIはゼロ以下です。")

    if sales_count <= 0:
        demand_text = "販売実績がないため、需要は不確実です。"
    elif sales_count >= 5:
        demand_text = "販売実績があります。"
    else:
        demand_text = "販売実績は中程度です。"

    level = (confidence_level or ConfidenceLevel.LOW.value).upper()
    if warnings:
        sentences.append(
            f"{demand_text} 価格の信頼性は{level}です。"
            "購入前に商品の状態・付属品をご確認ください。"
        )
    else:
        sentences.append(demand_text)
        sentences.append(f"価格の信頼性は{level}です。")

    return " ".join(sentences[:4])

def rank_used_listings(candidates: list[AcquisitionCandidate]) -> list[UsedListingRankResult]:
    """Rank eligible candidates by overall MVP score. URL-less candidates are excluded."""
    eligible = [item for item in candidates if is_ranking_eligible(item)]
    if not eligible:
        return []

    metrics: list[tuple[AcquisitionCandidate, Decimal, Decimal | None, int]] = []
    for item in eligible:
        net_profit = resolve_net_profit(item)
        assert net_profit is not None
        roi = resolve_roi(item, net_profit)
        sales_count = resolve_sales_count(item)
        metrics.append((item, net_profit, roi, sales_count))

    profit_values = [net for _, net, _, _ in metrics]
    roi_values = [roi for _, _, roi, _ in metrics if roi is not None]
    sales_values = [Decimal(sales) for _, _, _, sales in metrics]

    positive_profits = [value for value in profit_values if value > 0]
    positive_rois = [value for value in roi_values if value > 0]
    average_profit = (
        sum(positive_profits, Decimal("0")) / Decimal(len(positive_profits))
        if positive_profits
        else None
    )
    average_roi = (
        sum(positive_rois, Decimal("0")) / Decimal(len(positive_rois))
        if positive_rois
        else None
    )

    scored: list[UsedListingRankResult] = []
    for item, net_profit, roi, sales_count in metrics:
        profit_for_scale = net_profit if net_profit > 0 else Decimal("0")
        profit_score = (
            Decimal("0")
            if net_profit <= 0
            else _min_max_score(profit_for_scale, [value if value > 0 else Decimal("0") for value in profit_values])
        )
        if roi is None or roi <= 0:
            roi_score = Decimal("0")
        else:
            roi_score = _min_max_score(
                roi,
                [value if value > 0 else Decimal("0") for value in roi_values] or [roi],
            )
        demand_score = (
            Decimal("0")
            if sales_count <= 0
            else _min_max_score(Decimal(sales_count), sales_values)
        )
        confidence_score = confidence_to_score(item.data_truth_summary.confidence_level)
        overall = clamp_score(
            profit_score * WEIGHT_PROFIT
            + roi_score * WEIGHT_ROI
            + demand_score * WEIGHT_DEMAND
            + confidence_score * WEIGHT_CONFIDENCE
        )
        warnings = build_ranking_warnings(item, net_profit=net_profit, sales_count=sales_count)
        analysis = build_analysis_summary(
            net_profit=net_profit,
            roi=roi,
            sales_count=sales_count,
            confidence_level=item.data_truth_summary.confidence_level,
            average_profit=average_profit,
            average_roi=average_roi,
            warnings=warnings,
        )
        scored.append(
            UsedListingRankResult(
                candidate_id=item.candidate_id,
                title=item.title,
                rank=0,
                overall_score=overall,
                profit_score=clamp_score(profit_score),
                roi_score=clamp_score(roi_score),
                demand_score=clamp_score(demand_score),
                confidence_score=clamp_score(confidence_score),
                net_profit=net_profit,
                roi=roi,
                sales_count=sales_count,
                confidence_level=item.data_truth_summary.confidence_level,
                source_listing_url=item.purchase_url.strip(),
                analysis_summary=analysis,
                ranking_warnings=warnings,
            )
        )

    scored.sort(key=lambda item: (item.overall_score, item.net_profit or Decimal("0"), item.candidate_id), reverse=True)
    ranked: list[UsedListingRankResult] = []
    for index, item in enumerate(scored, start=1):
        ranked.append(
            UsedListingRankResult(
                candidate_id=item.candidate_id,
                title=item.title,
                rank=index,
                overall_score=item.overall_score,
                profit_score=item.profit_score,
                roi_score=item.roi_score,
                demand_score=item.demand_score,
                confidence_score=item.confidence_score,
                net_profit=item.net_profit,
                roi=item.roi,
                sales_count=item.sales_count,
                confidence_level=item.confidence_level,
                source_listing_url=item.source_listing_url,
                analysis_summary=item.analysis_summary,
                ranking_warnings=item.ranking_warnings,
            )
        )
    return ranked


def ranking_by_candidate_id(candidates: list[AcquisitionCandidate]) -> dict[str, UsedListingRankResult]:
    return {item.candidate_id: item for item in rank_used_listings(candidates)}


def order_candidates_for_display(candidates: list[AcquisitionCandidate]) -> list[AcquisitionCandidate]:
    """Highest eligible score first; non-ranked candidates follow in original relative order."""
    ranks = ranking_by_candidate_id(candidates)
    ranked = sorted(
        [item for item in candidates if item.candidate_id in ranks],
        key=lambda item: (
            ranks[item.candidate_id].overall_score,
            ranks[item.candidate_id].net_profit or Decimal("0"),
            item.candidate_id,
        ),
        reverse=True,
    )
    unranked = [item for item in candidates if item.candidate_id not in ranks]
    return ranked + unranked
