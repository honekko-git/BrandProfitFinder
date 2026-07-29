"""Human-readable discovery CLI output formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import IO, Any, TextIO

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand.models import BrandDiscoveryResult, MultiBrandDiscoveryResult
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult, OpportunityResult
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

    return DiscoveryDisplaySummary(
        brands=tuple(brands),
        products=result.total_candidates,
        buy_count=buy_count,
        hold_count=hold_count,
        pass_count=pass_count,
        supplier_failures=_format_supplier_failures(result.results),
        market_failures=_format_market_failures(result.ranked_candidates),
        empty_brands=_format_empty_brands(result.results),
    )


def format_discovery_summary(summary: DiscoveryDisplaySummary) -> str:
    """Format the discovery summary block."""
    lines = [
        "Discovery Summary",
        "",
        "Brands:",
        *summary.brands,
        "",
        f"Products:",
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
        return "TOP BUY Candidates\n\n(none)"

    lines = ["TOP BUY Candidates", ""]
    for index, candidate in enumerate(buy_candidates, start=1):
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        roi = _format_percent(candidate.profit_result.roi if candidate.profit_result else None)
        lines.extend(
            [
                f"{index}.",
                f"Product: {candidate.supplier_product.title}",
                f"Supplier: {candidate.supplier_product.supplier_name}",
                f"Profit: {profit}",
                f"ROI: {roi}",
                f"Decision: {candidate.buy_decision.decision.value if candidate.buy_decision else 'N/A'}",
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
    return "\n".join(["Excel exported:", "", display_path])


def format_opportunity_ranking(
    opportunities: tuple[OpportunityResult, ...] | list[OpportunityResult],
    *,
    limit: int = 5,
) -> str:
    """Format ranked opportunity results for manual purchase review."""
    ranked = list(opportunities)[:limit]
    if not ranked:
        return "Opportunity Ranking\n\n(none)"

    lines = ["Opportunity Ranking", ""]
    for item in ranked:
        candidate = item.candidate
        profit = _format_jpy(candidate.profit_result.profit_jpy if candidate.profit_result else None)
        roi = _format_percent(candidate.profit_result.roi if candidate.profit_result else None)
        decision = candidate.buy_decision.decision.value if candidate.buy_decision else "N/A"
        lines.extend(
            [
                f"{item.recommendation_rank}.",
                f"Product:",
                candidate.supplier_product.title,
                "",
                f"Supplier:",
                candidate.supplier_product.supplier_name,
                "",
                f"Score:",
                f"{item.score.total_score:.1f}",
                "",
                f"Profit:",
                profit,
                "",
                f"ROI:",
                roi,
                "",
                f"Decision:",
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
        return "Demand Opportunity Ranking\n\n(none)"

    lines = ["Demand Opportunity Ranking", ""]
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
                f"Product:",
                product_name,
                "",
                f"Supplier:",
                candidate.supplier_product.supplier_name,
                "",
                f"Profit:",
                profit,
                "",
                f"Demand:",
                f"{int(round(item.score.demand_score))}",
                "",
                f"Score:",
                f"{item.score.total_score:.1f}",
                "",
                f"ROI:",
                roi,
                "",
                f"Decision:",
                decision,
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
) -> str:
    """Render the showcase dashboard view for ranked demand opportunities."""
    active_formatter = formatter or ShowcaseFormatter()
    return active_formatter.format_showcase(result, opportunities, limit=limit)


def render_discovery_run(
    result: MultiBrandDiscoveryResult,
    *,
    brands: list[str] | tuple[str, ...],
    export_path: Path | None = None,
    ranked_opportunities: list[OpportunityResult] | None = None,
    ranked_demand_opportunities: list[DemandIntegratedOpportunityResult] | None = None,
    output: TextIO | None = None,
) -> str:
    """Render the full discovery CLI output and optionally write it to a stream."""
    summary = build_display_summary(result, brands=brands)
    sections = [
        format_discovery_summary(summary),
        "",
        format_top_buy_candidates(result.ranked_candidates),
    ]
    if ranked_demand_opportunities is not None:
        sections.extend(["", format_demand_opportunity_ranking(ranked_demand_opportunities)])
        sections.extend(["", render_showcase(result, ranked_demand_opportunities)])
    elif ranked_opportunities is not None:
        sections.extend(["", format_opportunity_ranking(ranked_opportunities)])
    if export_path is not None:
        sections.extend(["", format_export_message(export_path)])

    rendered = "\n".join(sections)
    if output is not None:
        output.write(rendered)
        output.write("\n")
    return rendered


def _format_issue_lines(summary: DiscoveryDisplaySummary) -> list[str]:
    lines: list[str] = []
    if summary.supplier_failures or summary.market_failures or summary.empty_brands:
        lines.append("Issues")
        lines.append("")

    if summary.supplier_failures:
        lines.append("Supplier failures:")
        lines.extend(f"- {message}" for message in summary.supplier_failures)
        lines.append("")

    if summary.market_failures:
        lines.append("Market failures:")
        lines.extend(f"- {message}" for message in summary.market_failures)
        lines.append("")

    if summary.empty_brands:
        lines.append("Empty results:")
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
