"""Human-readable discovery CLI output formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import IO, Any, TextIO

from marketplace.domestic_market.execution import MarketExecutionResult
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand.models import BrandDiscoveryResult, MultiBrandDiscoveryResult
from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult, OpportunityResult
from profit_discovery.profit_ranking.models import UsedLuxuryProfitRankedResult
from profit_discovery.showcase.formatter import ShowcaseFormatter


@dataclass(frozen=True, slots=True)
class DiscoveryDisplaySummary:
    """Aggregated counts and issue details for CLI display."""

    brands: tuple[str, ...]
    products: int
    buy_count: int
    hold_count: int
    pass_count: int
    supplier_failures: tuple[str, ...] = ()
    market_failures: tuple[str, ...] = ()
    empty_brands: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def build_display_summary(
    result: MultiBrandDiscoveryResult,
    *,
    brands: list[str] | tuple[str, ...],
    market_execution: MarketExecutionResult | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
) -> DiscoveryDisplaySummary:
    """Build display summary from a multi-brand discovery result."""
    buy_count = 0
    hold_count = 0
    pass_count = 0

    for candidate in result.ranked_candidates:
        if candidate.buy_decision is None:
            continue
        if candidate.buy_decision.decision is BuyDecision.BUY:
            buy_count += 1
        elif candidate.buy_decision.decision is BuyDecision.HOLD:
            hold_count += 1
        elif candidate.buy_decision.decision is BuyDecision.PASS:
            pass_count += 1

    execution = market_execution or MarketExecutionResult(
        requested_mode="FIXTURE",
        actual_source="Fixture",
        fallback_used=False,
        client_name="YahooAuctionDomesticMarketClient",
    )
    metadata = {
        "requested_market_mode": execution.requested_mode,
        "actual_market_source": execution.actual_source,
        "fallback_used": execution.fallback_used,
    }
    if used_luxury_config is not None and used_luxury_config.enabled:
        metadata.update(
            {
                "business_mode": "USED LUXURY",
                "market_coverage": " / ".join(used_luxury_config.market_display_names()),
                "used_luxury_markets": used_luxury_config.market_display_names(),
            }
        )
    return DiscoveryDisplaySummary(
        brands=tuple(brands),
        products=result.total_candidates,
        buy_count=buy_count,
        hold_count=hold_count,
        pass_count=pass_count,
        supplier_failures=_format_supplier_failures(result.results),
        market_failures=_format_market_failures(result.ranked_candidates),
        empty_brands=_format_empty_brands(result.results),
        metadata=metadata,
    )


def format_discovery_summary(summary: DiscoveryDisplaySummary) -> str:
    """Format the discovery summary block."""
    lines = ["検索概要", ""]
    if summary.metadata.get("business_mode"):
        lines.extend(
            [
                "モード:",
                str(summary.metadata.get("business_mode")),
                "",
                "市場:",
                *summary.metadata.get("used_luxury_markets", ()),
                "",
            ]
        )
    lines.extend(
        [
            "要求市場モード:",
            str(summary.metadata.get("requested_market_mode", "FIXTURE")),
            "",
            "実際の市場ソース:",
            str(summary.metadata.get("actual_market_source", "Fixture")),
            "",
            "フォールバック:",
            _format_fallback_label(summary.metadata.get("fallback_used")),
            "",
            "ブランド:",
            *summary.brands,
            "",
            f"商品数:",
            f"{summary.products}",
            "",
            f"BUY:",
            f"{summary.buy_count}",
            "",
            f"HOLD:",
            f"{summary.hold_count}",
            "",
            f"PASS:",
            f"{summary.pass_count}",
        ]
    )
    issue_lines = _format_issue_lines(summary)
    if issue_lines:
        lines.extend(["", *issue_lines])
    return "\n".join(lines)


def format_top_buy_candidates(
    candidates: tuple[DiscoveryCandidateResult, ...] | list[DiscoveryCandidateResult],
    *,
    limit: int = 5,
) -> str:
    """Format ranked BUY candidates for manual review."""
    buy_candidates = [
        candidate
        for candidate in candidates
        if candidate.buy_decision is not None
        and candidate.buy_decision.decision is BuyDecision.BUY
    ][:limit]

    if not buy_candidates:
        return "BUY候補上位\n\n（なし）"

    lines = ["BUY候補上位", ""]
    for index, candidate in enumerate(buy_candidates, start=1):
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        roi = _format_percent(candidate.profit_result.roi if candidate.profit_result else None)
        lines.extend(
            [
                f"{index}.",
                f"商品名: {candidate.supplier_product.title}",
                f"仕入先: {candidate.supplier_product.supplier_name}",
                f"利益: {profit}",
                f"ROI: {roi}",
                f"判定: {candidate.buy_decision.decision.value if candidate.buy_decision else 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_export_message(export_path: Path | str) -> str:
    """Format export success message."""
    path = Path(export_path)
    try:
        display_path = path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        display_path = path.as_posix()
    return "\n".join(["Excelをエクスポートしました:", "", display_path])


def format_opportunity_ranking(
    opportunities: tuple[OpportunityResult, ...] | list[OpportunityResult],
    *,
    limit: int = 5,
) -> str:
    """Format ranked opportunity results for manual purchase review."""
    ranked = list(opportunities)[:limit]
    if not ranked:
        return "候補順位\n\n（なし）"

    lines = ["候補順位", ""]
    for item in ranked:
        candidate = item.candidate
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        roi = _format_percent(candidate.profit_result.roi if candidate.profit_result else None)
        decision = candidate.buy_decision.decision.value if candidate.buy_decision else "N/A"
        lines.extend(
            [
                f"{item.recommendation_rank}.",
                f"商品名:",
                candidate.supplier_product.title,
                "",
                f"仕入先:",
                candidate.supplier_product.supplier_name,
                "",
                f"スコア:",
                f"{item.score.total_score:.1f}",
                "",
                f"利益:",
                profit,
                "",
                f"ROI:",
                roi,
                "",
                f"判定:",
                decision,
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_demand_opportunity_ranking(
    opportunities: tuple[DemandIntegratedOpportunityResult, ...] | list[DemandIntegratedOpportunityResult],
    *,
    limit: int = 5,
) -> str:
    """Format ranked demand-integrated opportunity results for manual purchase review."""
    ranked = list(opportunities)[:limit]
    if not ranked:
        return "需要込み候補順位\n\n（なし）"

    lines = ["需要込み候補順位", ""]
    for item in ranked:
        candidate = item.candidate
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        roi = _format_percent(candidate.profit_result.roi if candidate.profit_result else None)
        decision = candidate.buy_decision.decision.value if candidate.buy_decision else "N/A"
        product_name = (
            item.demand_profile.query
            if item.demand_profile is not None
            else candidate.supplier_product.title
        )
        lines.extend(
            [
                f"{item.recommendation_rank}.",
                f"商品名:",
                product_name,
                "",
                f"仕入先:",
                candidate.supplier_product.supplier_name,
                "",
                f"利益:",
                profit,
                "",
                f"需要:",
                f"{int(round(item.score.demand_score))}",
                "",
                f"スコア:",
                f"{item.score.total_score:.1f}",
                "",
                f"ROI:",
                roi,
                "",
                f"判定:",
                decision,
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_used_luxury_profit_ranking(
    ranking: tuple[UsedLuxuryProfitRankedResult, ...] | list[UsedLuxuryProfitRankedResult],
    *,
    limit: int = 5,
) -> str:
    """Format used luxury profit ranking for CLI display."""
    ranked = list(ranking)[:limit]
    if not ranked:
        return "中古高級品 利益順位\n\n（なし）"

    lines = ["中古高級品 利益順位", ""]
    for item in ranked:
        candidate = item.candidate
        product = candidate.supplier_product
        product_name = (
            item.demand_profile.query
            if item.demand_profile is not None
            else product.title
        )
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        decision = candidate.buy_decision.decision.value if candidate.buy_decision else "N/A"
        lines.extend(
            [
                f"{item.score.recommendation_rank}.",
                "商品名:",
                product_name,
                "",
                "ブランド:",
                product.brand,
                "",
                "カテゴリ:",
                product.category,
                "",
                "仕入先:",
                product.supplier_name,
                "",
                "利益:",
                profit,
                "",
                "需要:",
                f"{int(round(item.score.demand_score))}",
                "",
                "回転:",
                f"{item.score.turnover_score:.1f}",
                "",
                "スコア:",
                f"{item.score.total_score:.1f}",
                "",
                "判定:",
                decision,
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_used_luxury_arbitrage_ranking(
    ranking: tuple[ArbitrageOpportunity, ...] | list[ArbitrageOpportunity],
    *,
    limit: int = 5,
) -> str:
    """Format used luxury arbitrage ranking for CLI display."""
    ranked = list(ranking)[:limit]
    if not ranked:
        return "中古高級品 裁定順位\n\n（なし）"

    lines = ["中古高級品 裁定順位", ""]
    for item in ranked:
        lines.extend(
            [
                f"{item.recommendation_rank}.",
                "商品名:",
                item.product,
                "",
                "仕入先:",
                item.purchase_source,
                "",
                "仕入価格:",
                _format_jpy(item.purchase_price),
                "",
                "販売市場:",
                item.selling_market,
                "",
                "販売価格:",
                _format_jpy(item.selling_price),
                "",
                "推定利益:",
                _format_jpy(item.estimated_profit),
                "",
                "利益率:",
                _format_percent(item.profit_margin),
                "",
                "需要:",
                f"{int(round(item.demand_score))}",
                "",
                "回転:",
                f"{item.turnover_score:.1f}",
                "",
                "スコア:",
                f"{item.arbitrage_score:.1f}",
                "",
                "判定:",
                item.decision,
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def render_showcase(
    result: MultiBrandDiscoveryResult,
    opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
    *,
    limit: int = 5,
    formatter: ShowcaseFormatter | None = None,
    market_execution: MarketExecutionResult | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
    profit_ranking: list[UsedLuxuryProfitRankedResult] | tuple[UsedLuxuryProfitRankedResult, ...] | None = None,
    arbitrage_ranking: list[ArbitrageOpportunity] | tuple[ArbitrageOpportunity, ...] | None = None,
) -> str:
    """Render the showcase dashboard view for ranked demand opportunities."""
    active_formatter = formatter or ShowcaseFormatter()
    return active_formatter.format_showcase(
        result,
        opportunities,
        limit=limit,
        market_execution=market_execution,
        used_luxury_config=used_luxury_config,
        profit_ranking=profit_ranking,
        arbitrage_ranking=arbitrage_ranking,
    )


def render_discovery_run(
    result: MultiBrandDiscoveryResult,
    *,
    brands: list[str] | tuple[str, ...],
    export_path: Path | None = None,
    ranked_opportunities: list[OpportunityResult] | None = None,
    ranked_demand_opportunities: list[DemandIntegratedOpportunityResult] | None = None,
    used_luxury_profit_ranking: list[UsedLuxuryProfitRankedResult] | None = None,
    used_luxury_arbitrage_ranking: list[ArbitrageOpportunity] | None = None,
    market_execution: MarketExecutionResult | None = None,
    used_luxury_config: UsedLuxuryModeConfig | None = None,
    output: TextIO | None = None,
) -> str:
    """Render the full discovery CLI output and optionally write it to a stream."""
    summary = build_display_summary(
        result,
        brands=brands,
        market_execution=market_execution,
        used_luxury_config=used_luxury_config,
    )
    sections = [
        format_discovery_summary(summary),
        "",
        format_top_buy_candidates(result.ranked_candidates),
    ]
    if ranked_demand_opportunities is not None:
        sections.extend(["", format_demand_opportunity_ranking(ranked_demand_opportunities)])
        if used_luxury_profit_ranking is not None:
            sections.extend(
                ["", format_used_luxury_profit_ranking(used_luxury_profit_ranking)]
            )
        if used_luxury_arbitrage_ranking is not None:
            sections.extend(
                ["", format_used_luxury_arbitrage_ranking(used_luxury_arbitrage_ranking)]
            )
        sections.extend(
            [
                "",
                render_showcase(
                    result,
                    ranked_demand_opportunities,
                    market_execution=market_execution,
                    used_luxury_config=used_luxury_config,
                    profit_ranking=used_luxury_profit_ranking,
                    arbitrage_ranking=used_luxury_arbitrage_ranking,
                ),
            ]
        )
    elif ranked_opportunities is not None:
        sections.extend(["", format_opportunity_ranking(ranked_opportunities)])
    if export_path is not None:
        sections.extend(["", format_export_message(export_path)])

    rendered = "\n".join(sections)
    if output is not None:
        output.write(rendered)
        output.write("\n")
    return rendered


def _format_fallback_label(value: object) -> str:
    if value is True:
        return "はい"
    return "いいえ"


def _format_issue_lines(summary: DiscoveryDisplaySummary) -> list[str]:
    lines: list[str] = []
    if summary.supplier_failures or summary.market_failures or summary.empty_brands:
        lines.append("注意事項")
        lines.append("")

    if summary.supplier_failures:
        lines.append("仕入先の失敗:")
        lines.extend(f"- {message}" for message in summary.supplier_failures)
        lines.append("")

    if summary.market_failures:
        lines.append("市場の失敗:")
        lines.extend(f"- {message}" for message in summary.market_failures)
        lines.append("")

    if summary.empty_brands:
        lines.append("結果なし:")
        lines.extend(f"- {message}" for message in summary.empty_brands)

    return lines


def _format_supplier_failures(results: tuple[BrandDiscoveryResult, ...]) -> tuple[str, ...]:
    messages: list[str] = []
    for brand_result in results:
        if brand_result.metadata.get("status") != "ERROR":
            continue
        error = brand_result.metadata.get("error", "unknown supplier error")
        messages.append(f"{brand_result.brand}: {error}")
    return tuple(messages)


def _format_market_failures(
    candidates: tuple[DiscoveryCandidateResult, ...] | list[DiscoveryCandidateResult],
) -> tuple[str, ...]:
    messages: list[str] = []
    for candidate in candidates:
        if candidate.status is not DiscoveryCandidateStatus.NO_MARKET_DATA:
            continue
        reason = candidate.metadata.get("reason", "no domestic market data")
        messages.append(f"{candidate.supplier_product.brand} / {candidate.supplier_product.title}: {reason}")
    return tuple(messages)


def _format_empty_brands(results: tuple[BrandDiscoveryResult, ...]) -> tuple[str, ...]:
    messages: list[str] = []
    for brand_result in results:
        if brand_result.metadata.get("status") != "SUCCESS":
            continue
        product_count = int(brand_result.metadata.get("product_count", 0))
        if product_count == 0:
            messages.append(f"{brand_result.brand}: 0 products found")
    return tuple(messages)


def _format_jpy(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} JPY"


def _format_percent(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"
