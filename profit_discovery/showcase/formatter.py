"""Format discovery ranking results for showcase dashboard display."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_discovery.showcase.models import ShowcaseOpportunity

SHOWCASE_HEADER = "AI PROFIT DISCOVERY SHOWCASE"
SHOWCASE_DIVIDER = "================================"


class ShowcaseFormatter:
    """Convert ranked discovery results into human-readable showcase output."""

    def format_top_opportunities(
        self,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
        *,
        limit: int = 5,
    ) -> str:
        """Format ranked opportunities for the TOP Opportunity Dashboard view."""
        showcase_items = [self._to_showcase(item) for item in opportunities[:limit]]
        if not showcase_items:
            return "\n".join(
                [
                    SHOWCASE_DIVIDER,
                    "",
                    SHOWCASE_HEADER,
                    "",
                    SHOWCASE_DIVIDER,
                    "",
                    "TOP OPPORTUNITIES",
                    "",
                    "(none)",
                ]
            )

        lines = [
            SHOWCASE_DIVIDER,
            "",
            SHOWCASE_HEADER,
            "",
            SHOWCASE_DIVIDER,
            "",
            "TOP OPPORTUNITIES",
            "",
        ]
        for item in showcase_items:
            lines.extend(self._format_opportunity_block(item))
            lines.append("--------------------------------")
        if lines[-1] == "--------------------------------":
            lines.pop()
        return "\n".join(lines)

    def format_summary(self, result: MultiBrandDiscoveryResult) -> str:
        """Format aggregate candidate counts for the showcase summary block."""
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

        return "\n".join(
            [
                "Summary:",
                "",
                "Total Candidates:",
                f"{result.total_candidates}",
                "",
                "BUY:",
                f"{buy_count}",
                "",
                "HOLD:",
                f"{hold_count}",
                "",
                "PASS:",
                f"{pass_count}",
            ]
        )

    def format_showcase(
        self,
        result: MultiBrandDiscoveryResult,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
        *,
        limit: int = 5,
    ) -> str:
        """Format the full showcase dashboard view."""
        sections = [
            self.format_top_opportunities(opportunities, limit=limit),
            "",
            self.format_summary(result),
        ]
        return "\n".join(sections)

    def to_showcase_opportunities(
        self,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
    ) -> tuple[ShowcaseOpportunity, ...]:
        """Convert ranked demand-integrated results into showcase models."""
        return tuple(self._to_showcase(item) for item in opportunities)

    def _to_showcase(self, item: DemandIntegratedOpportunityResult) -> ShowcaseOpportunity:
        candidate = item.candidate
        product = candidate.supplier_product
        product_name = (
            item.demand_profile.query
            if item.demand_profile is not None
            else product.title
        )
        return ShowcaseOpportunity(
            rank=item.recommendation_rank or 0,
            product_name=product_name,
            supplier=_format_supplier_name(product.supplier_name),
            profit_jpy=_resolve_profit_jpy(candidate),
            roi=_resolve_roi(candidate),
            demand_score=item.score.demand_score,
            opportunity_score=item.score.total_score,
            decision=candidate.buy_decision.decision.value if candidate.buy_decision else "N/A",
            category=product.category,
            brand=product.brand,
        )

    def _format_opportunity_block(self, item: ShowcaseOpportunity) -> list[str]:
        return [
            f"{item.rank}.",
            "Product:",
            item.product_name,
            "Brand:",
            item.brand,
            "Supplier:",
            item.supplier,
            "",
            "Profit:",
            _format_jpy(item.profit_jpy),
            "",
            "ROI:",
            _format_roi(item.roi),
            "",
            "Demand:",
            f"{int(round(item.demand_score))}/100",
            "",
            "Score:",
            f"{item.opportunity_score:.1f}",
            "",
            "Decision:",
            item.decision,
            "",
        ]


def _format_supplier_name(raw_supplier: str) -> str:
    supplier = raw_supplier.strip()
    if not supplier:
        return "Unknown"
    if supplier.islower():
        return supplier.title()
    return supplier


def _resolve_profit_jpy(candidate: DiscoveryCandidateResult) -> Decimal | None:
    if candidate.profit_result is None:
        return None
    return candidate.profit_result.profit_jpy


def _resolve_roi(candidate: DiscoveryCandidateResult) -> Decimal | None:
    if candidate.profit_result is None:
        return None
    return candidate.profit_result.roi


def _format_jpy(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} JPY"


def _format_roi(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    normalized = float(value)
    if normalized == int(normalized):
        return f"{int(normalized)}%"
    return f"{normalized:.1f}%"
