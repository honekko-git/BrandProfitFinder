"""
Deterministic risk scoring component.

Risk score: 0 = lower observed risk, 100 = higher observed risk.
"""

from __future__ import annotations

from profit_intelligence.constants import (
    HIGH_VOLATILITY_THRESHOLD,
    LOW_LIQUIDITY_ASKS,
    LOW_LIQUIDITY_SALES_30D,
)
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import clamp_score, dedupe_preserve_order


class RiskScorer:
    """Evaluate observed risk signals without authenticity judgments."""

    def score(self, data: ProfitIntelligenceInput) -> ScoreComponentResult:
        reasons: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []
        contributions: list[float] = []
        has_risk_signal = False
        has_information = False

        def add(contribution: float, reason: str) -> None:
            nonlocal has_risk_signal
            has_risk_signal = True
            contributions.append(contribution)
            reasons.append(reason)

        def note_known() -> None:
            nonlocal has_information
            has_information = True

        if data.shipping_cost_known is False:
            add(8.0, "Shipping cost is unknown, increasing financial uncertainty.")
            warnings.append("Shipping cost is unknown.")
        elif data.shipping_cost_known is True:
            note_known()
        elif data.shipping_cost_known is None:
            missing.append("shipping_cost_known")

        if data.marketplace_fee_known is False:
            add(8.0, "Marketplace fee is unknown, increasing financial uncertainty.")
            warnings.append("Marketplace fee is unknown.")
        elif data.marketplace_fee_known is True:
            note_known()
        elif data.marketplace_fee_known is None:
            missing.append("marketplace_fee_known")

        if data.duties_tax_known is False:
            add(8.0, "Duties or tax exposure is unknown.")
            warnings.append("Duties or tax is unknown.")
        elif data.duties_tax_known is True:
            note_known()
        elif data.duties_tax_known is None:
            missing.append("duties_tax_known")

        currency = (data.currency or "").upper()
        if currency and currency != "JPY":
            add(10.0, "Non-JPY currency without confirmed JPY normalization.")
            warnings.append("Currency is not JPY and conversion is not confirmed.")
        elif currency == "JPY":
            note_known()

        if data.volatility_percent is not None:
            note_known()
            vol = float(data.volatility_percent)
            if vol >= HIGH_VOLATILITY_THRESHOLD:
                add(15.0, "Price volatility is high in the available data.")
                warnings.append("Price volatility is high in the available data.")
            elif vol >= 0.15:
                add(8.0, "Moderate price volatility observed in available data.")
        else:
            missing.append("volatility_percent")

        if data.profit_amount_jpy is not None and data.profit_amount_jpy < 0:
            add(20.0, "Observed profit amount is negative.")
            warnings.append("Observed profit amount is negative.")

        identifier_gaps = 0
        if data.style_code_present is False:
            identifier_gaps += 1
        elif data.style_code_present is None:
            missing.append("style_code_present")
        if data.product_id_present is False:
            identifier_gaps += 1
        elif data.product_id_present is None:
            missing.append("product_id_present")
        if data.jan_present is False:
            identifier_gaps += 1
        elif data.jan_present is None:
            missing.append("jan_present")

        if identifier_gaps > 0:
            add(min(12.0, identifier_gaps * 5.0), "Product identifiers are incomplete.")
            warnings.append("Product identifiers are incomplete.")
        elif (
            data.style_code_present is True
            or data.product_id_present is True
            or data.jan_present is True
        ):
            note_known()

        if data.size_match is False:
            add(10.0, "Size match could not be confirmed.")
            warnings.append("Size match could not be confirmed.")
        elif data.size_match is True:
            note_known()
        elif data.size_match is None:
            missing.append("size_match")

        if data.validation_warning_count is not None and data.validation_warning_count > 0:
            add(min(10.0, data.validation_warning_count * 2.0), "Validation warnings were recorded.")
            warnings.append("Validation warnings were recorded.")

        if data.rejected_listing_count is not None and data.rejected_listing_count > 0:
            add(min(8.0, data.rejected_listing_count * 2.0), "Rejected listings were observed.")
            warnings.append("Rejected listings were observed.")

        if data.sales_last_30_days is None and data.last_sale_price is None:
            missing.append("sales_last_30_days")
            missing.append("last_sale_price")
        elif data.sales_last_30_days is not None and data.sales_last_30_days < LOW_LIQUIDITY_SALES_30D:
            note_known()
            add(5.0, "Recent sale history appears limited.")
            warnings.append("Recent sales activity is limited or unavailable.")
        elif data.sales_last_30_days is not None:
            note_known()

        if data.asks_count is not None and data.asks_count < LOW_LIQUIDITY_ASKS:
            note_known()
            add(5.0, "Market liquidity appears limited in available data.")
        elif data.asks_count is not None:
            note_known()

        if data.listing_count is not None and data.listing_count == 0:
            add(8.0, "No valid listings were available for evaluation.")
        elif data.listing_count is not None:
            note_known()

        if not has_information and not has_risk_signal:
            return ScoreComponentResult(
                score=None,
                available=False,
                missing_fields=dedupe_preserve_order(missing),
            )

        final = clamp_score(sum(contributions))
        if final <= 15:
            reasons.insert(0, "Observed risk signals are limited in available data.")

        return ScoreComponentResult(
            score=final,
            available=True,
            reasons=dedupe_preserve_order(reasons),
            warnings=dedupe_preserve_order(warnings),
            missing_fields=dedupe_preserve_order(missing),
        )
