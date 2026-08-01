"""Format discovery ranking results for showcase dashboard display."""

from __future__ import annotations

from decimal import Decimal

from marketplace.domestic_market.execution import MarketExecutionResult
from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_discovery.models import BuyDecision
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult
from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_discovery.profit_ranking.models import UsedLuxuryProfitRankedResult
from profit_discovery.showcase.models import ShowcaseOpportunity

SHOWCASE_HEADER = "AI利益発見ショーケース"
SHOWCASE_DIVIDER = "================================"


class ShowcaseFormatter:
    """Convert ranked discovery results into human-readable showcase output."""

    def format_top_opportunities(
        self,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
        *,
        limit: int = 5,
        market_execution: MarketExecutionResult | None = None,
        market_source: str | None = None,
        used_luxury_config: UsedLuxuryModeConfig | None = None,
        profit_ranking: list[UsedLuxuryProfitRankedResult] | tuple[UsedLuxuryProfitRankedResult, ...] | None = None,
        arbitrage_ranking: list[ArbitrageOpportunity] | tuple[ArbitrageOpportunity, ...] | None = None,
    ) -> str:
        """Format ranked opportunities for the TOP Opportunity Dashboard view."""
        execution = market_execution or _default_market_execution(market_source)
        header_lines = _build_showcase_header_lines(execution, used_luxury_config)
        profit_rank_map = _build_profit_rank_map(profit_ranking)
        arbitrage_rank_map = _build_arbitrage_rank_map(arbitrage_ranking)
        showcase_items = [
            self._to_showcase(
                item,
                market_execution=execution,
                used_luxury_config=used_luxury_config,
                profit_rank_map=profit_rank_map,
                arbitrage_rank_map=arbitrage_rank_map,
            )
            for item in opportunities[:limit]
        ]
        if not showcase_items:
            return "\n".join(
                [
                    SHOWCASE_DIVIDER,
                    "",
                    SHOWCASE_HEADER,
                    "",
                    SHOWCASE_DIVIDER,
                    "",
                    *header_lines,
                    "注目候補",
                    "",
                    "（なし）",
                ]
            )

        lines = [
            SHOWCASE_DIVIDER,
            "",
            SHOWCASE_HEADER,
            "",
            SHOWCASE_DIVIDER,
            "",
            *header_lines,
            "注目候補",
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
                "概要:",
                "",
                "候補合計:",
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

    def format_data_source_summary(self, values: dict[str, str | None]) -> str:
        """Format one structured transparency block with only populated fields."""
        lines = [SHOWCASE_DIVIDER, "", "データ取得情報", ""]
        for label, raw_value in values.items():
            value = (raw_value or "").strip()
            if not value:
                continue
            lines.extend([f"{label}:", value, ""])
        if lines[-1] == "":
            lines.pop()
        lines.extend(["", SHOWCASE_DIVIDER])
        return "\n".join(lines)

    def format_showcase(
        self,
        result: MultiBrandDiscoveryResult,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
        *,
        limit: int = 5,
        market_execution: MarketExecutionResult | None = None,
        market_source: str | None = None,
        used_luxury_config: UsedLuxuryModeConfig | None = None,
        profit_ranking: list[UsedLuxuryProfitRankedResult] | tuple[UsedLuxuryProfitRankedResult, ...] | None = None,
        arbitrage_ranking: list[ArbitrageOpportunity] | tuple[ArbitrageOpportunity, ...] | None = None,
    ) -> str:
        """Format the full showcase dashboard view."""
        sections = [
            self.format_top_opportunities(
                opportunities,
                limit=limit,
                market_execution=market_execution,
                market_source=market_source,
                used_luxury_config=used_luxury_config,
                profit_ranking=profit_ranking,
                arbitrage_ranking=arbitrage_ranking,
            ),
            "",
            self.format_summary(result),
        ]
        return "\n".join(sections)

    def to_showcase_opportunities(
        self,
        opportunities: list[DemandIntegratedOpportunityResult] | tuple[DemandIntegratedOpportunityResult, ...],
        *,
        market_execution: MarketExecutionResult | None = None,
        market_source: str | None = None,
        used_luxury_config: UsedLuxuryModeConfig | None = None,
        profit_ranking: list[UsedLuxuryProfitRankedResult] | tuple[UsedLuxuryProfitRankedResult, ...] | None = None,
        arbitrage_ranking: list[ArbitrageOpportunity] | tuple[ArbitrageOpportunity, ...] | None = None,
    ) -> tuple[ShowcaseOpportunity, ...]:
        """Convert ranked demand-integrated results into showcase models."""
        execution = market_execution or _default_market_execution(market_source)
        profit_rank_map = _build_profit_rank_map(profit_ranking)
        arbitrage_rank_map = _build_arbitrage_rank_map(arbitrage_ranking)
        return tuple(
            self._to_showcase(
                item,
                market_execution=execution,
                used_luxury_config=used_luxury_config,
                profit_rank_map=profit_rank_map,
                arbitrage_rank_map=arbitrage_rank_map,
            )
            for item in opportunities
        )

    def _to_showcase(
        self,
        item: DemandIntegratedOpportunityResult,
        *,
        market_execution: MarketExecutionResult,
        used_luxury_config: UsedLuxuryModeConfig | None = None,
        profit_rank_map: dict[str, UsedLuxuryProfitRankedResult] | None = None,
        arbitrage_rank_map: dict[str, ArbitrageOpportunity] | None = None,
    ) -> ShowcaseOpportunity:
        candidate = item.candidate
        product = candidate.supplier_product
        product_name = (
            item.demand_profile.query
            if item.demand_profile is not None
            else product.title
        )
        profit_rank_item = (
            profit_rank_map.get(product.external_id)
            if profit_rank_map is not None
            else None
        )
        arbitrage_item = (
            arbitrage_rank_map.get(product.external_id)
            if arbitrage_rank_map is not None
            else None
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
            market_source=market_execution.actual_source,
            requested_market_mode=market_execution.requested_mode,
            actual_market_source=market_execution.actual_source,
            fallback_used=market_execution.fallback_used,
            business_mode=(
                used_luxury_config.business_mode_label()
                if used_luxury_config is not None and used_luxury_config.enabled
                else ""
            ),
            market_coverage=(
                used_luxury_config.market_coverage_label()
                if used_luxury_config is not None and used_luxury_config.enabled
                else ""
            ),
            profit_rank=(
                profit_rank_item.score.recommendation_rank
                if profit_rank_item is not None
                else None
            ),
            turnover_score=(
                profit_rank_item.score.turnover_score
                if profit_rank_item is not None
                else None
            ),
            purchase_source=arbitrage_item.purchase_source if arbitrage_item is not None else "",
            purchase_url=arbitrage_item.purchase_url if arbitrage_item is not None else "",
            selling_market=arbitrage_item.selling_market if arbitrage_item is not None else "",
            selling_url=arbitrage_item.selling_url if arbitrage_item is not None else "",
            estimated_profit=(
                arbitrage_item.estimated_profit if arbitrage_item is not None else None
            ),
        )

    def _format_opportunity_block(self, item: ShowcaseOpportunity) -> list[str]:
        lines = [
            f"{item.rank}.",
            "商品名:",
            item.product_name,
            "ブランド:",
            item.brand,
            "仕入先:",
            item.supplier,
            "",
            "利益:",
            _format_jpy(item.profit_jpy),
            "",
            "ROI:",
            _format_roi(item.roi),
            "",
            "需要:",
            f"{int(round(item.demand_score))}/100",
            "",
        ]
        if item.profit_rank is not None:
            lines.extend(
                [
                    "利益順位:",
                    f"{item.profit_rank}",
                    "",
                ]
            )
        if item.turnover_score is not None:
            lines.extend(
                [
                    "回転スコア:",
                    f"{item.turnover_score:.1f}",
                    "",
                ]
            )
        if item.purchase_source:
            lines.extend(
                [
                    "仕入先:",
                    item.purchase_source,
                    "",
                ]
            )
        if item.purchase_url:
            lines.extend(
                [
                    "仕入URL:",
                    item.purchase_url,
                    "",
                ]
            )
        if item.selling_market:
            lines.extend(
                [
                    "販売市場:",
                    item.selling_market,
                    "",
                ]
            )
        if item.selling_url:
            lines.extend(
                [
                    "販売URL:",
                    item.selling_url,
                    "",
                ]
            )
        if item.estimated_profit is not None:
            lines.extend(
                [
                    "推定利益:",
                    _format_jpy(item.estimated_profit),
                    "",
                ]
            )
        lines.extend(
            [
                "スコア:",
                f"{item.opportunity_score:.1f}",
                "",
                "判定:",
                item.decision,
                "",
            ]
        )
        return lines

def _build_arbitrage_rank_map(
    arbitrage_ranking: list[ArbitrageOpportunity] | tuple[ArbitrageOpportunity, ...] | None,
) -> dict[str, ArbitrageOpportunity]:
    if not arbitrage_ranking:
        return {}
    return {item.external_id: item for item in arbitrage_ranking}


def _build_profit_rank_map(
    profit_ranking: list[UsedLuxuryProfitRankedResult] | tuple[UsedLuxuryProfitRankedResult, ...] | None,
) -> dict[str, UsedLuxuryProfitRankedResult]:
    if not profit_ranking:
        return {}
    return {
        item.candidate.supplier_product.external_id: item
        for item in profit_ranking
    }


def _build_showcase_header_lines(
    execution: MarketExecutionResult,
    used_luxury_config: UsedLuxuryModeConfig | None,
) -> list[str]:
    lines: list[str] = []
    if used_luxury_config is not None and used_luxury_config.enabled:
        lines.extend(
            [
                "事業モード:",
                used_luxury_config.business_mode_label(),
                "",
                "対象市場:",
                used_luxury_config.market_coverage_label(),
                "",
            ]
        )
    lines.extend(
        [
            "要求モード:",
            execution.requested_mode,
            "",
            "実際の取得元:",
            execution.actual_source,
            "",
            "フォールバック:",
            _format_fallback_label(execution.fallback_used),
            "",
        ]
    )
    return lines


def _default_market_execution(market_source: str | None) -> MarketExecutionResult:
    actual_source = market_source or "Fixture"
    return MarketExecutionResult(
        requested_mode="FIXTURE" if actual_source == "Fixture" else "LIVE",
        actual_source=actual_source,
        fallback_used=False,
        client_name="YahooAuctionDomesticMarketClient",
    )


def _format_fallback_label(value: bool) -> str:
    return "はい" if value else "いいえ"


def _format_supplier_name(raw_supplier: str) -> str:
    supplier = raw_supplier.strip()
    if not supplier:
        return "不明"
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
