"""Purchase-price upper-limit presets and server-side budget filtering."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from marketplace.acquisition_workspace.fx_convert import convert_to_jpy
from marketplace.acquisition_workspace.fx_models import FxSnapshot

# Preset keys → JPY limit (None = unlimited)
BUDGET_PRESETS: dict[str, int | None] = {
    "none": None,
    "30000": 30_000,
    "50000": 50_000,
    "100000": 100_000,
    "150000": 150_000,
    "300000": 300_000,
    "500000": 500_000,
    "custom": -1,  # sentinel; use custom value
}

BUDGET_PRESET_LABELS: dict[str, str] = {
    "none": "制限なし",
    "30000": "30,000円以下",
    "50000": "50,000円以下",
    "100000": "100,000円以下",
    "150000": "150,000円以下",
    "300000": "300,000円以下",
    "500000": "500,000円以下",
    "custom": "自由入力",
}

MAX_CUSTOM_BUDGET_JPY = 10_000_000


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    result: str  # pass|over_budget|currency_unavailable|currency_missing|unsupported_currency|invalid_price
    reason: str
    original_price: Decimal | None
    original_currency: str
    fx_rate_used: Decimal | None
    converted_purchase_price_jpy: Decimal | None
    budget_limit_jpy: int | None


def parse_budget_limit_jpy(
    preset: str | None,
    custom_raw: str | int | None = None,
) -> tuple[int | None, str]:
    """
    Resolve budget limit. Returns (limit_or_None, error_message).
    None limit means unrestricted.
    """
    key = str(preset or "none").strip().lower()
    if key in {"", "none", "unlimited", "制限なし"}:
        return None, ""
    if key == "custom" or key == "自由入力":
        return _parse_custom_jpy(custom_raw)
    if key in BUDGET_PRESETS and BUDGET_PRESETS[key] is not None and BUDGET_PRESETS[key] != -1:
        return int(BUDGET_PRESETS[key]), ""
    # Allow direct integer string presets
    try:
        as_int = int(str(key).replace(",", "").replace("円", "").replace("以下", "").strip())
    except ValueError:
        return None, "仕入れ価格上限が不正です"
    if as_int <= 0:
        return None, "仕入れ価格上限は1円以上で指定してください"
    if as_int > MAX_CUSTOM_BUDGET_JPY:
        return None, f"仕入れ価格上限は{MAX_CUSTOM_BUDGET_JPY:,}円以下で指定してください"
    return as_int, ""


def _parse_custom_jpy(custom_raw: str | int | None) -> tuple[int | None, str]:
    if custom_raw is None:
        return None, "自由入力の金額を入力してください"
    text = str(custom_raw).strip().replace(",", "").replace("円", "").replace("¥", "")
    if not text:
        return None, "自由入力の金額を入力してください"
    if "." in text:
        return None, "仕入れ上限は整数円のみ指定できます"
    try:
        value = int(text)
    except ValueError:
        return None, "仕入れ上限は整数円のみ指定できます"
    if value <= 0:
        return None, "仕入れ価格上限は1円以上で指定してください"
    if value > MAX_CUSTOM_BUDGET_JPY:
        return None, f"仕入れ価格上限は{MAX_CUSTOM_BUDGET_JPY:,}円以下で指定してください"
    return value, ""


def budget_label(limit_jpy: int | None) -> str:
    if limit_jpy is None:
        return "制限なし"
    for key, value in BUDGET_PRESETS.items():
        if value == limit_jpy:
            return BUDGET_PRESET_LABELS.get(key, f"{limit_jpy:,}円以下")
    return f"{limit_jpy:,}円以下"


def evaluate_product_budget(
    *,
    price: Any,
    currency: str,
    snapshot: FxSnapshot,
    budget_limit_jpy: int | None,
) -> BudgetDecision:
    """PRODUCT PRICE ONLY — no landed costs. Uses session snapshot rates."""
    code = str(currency or "").strip().upper()
    try:
        amount = Decimal(str(price).replace(",", "").strip()) if price is not None else None
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        amount = None
    if amount is None or amount <= 0:
        return BudgetDecision(
            result="invalid_price",
            reason="missing_or_invalid_price",
            original_price=None,
            original_currency=code,
            fx_rate_used=None,
            converted_purchase_price_jpy=None,
            budget_limit_jpy=budget_limit_jpy,
        )
    if not code:
        return BudgetDecision(
            result="currency_missing",
            reason="currency_missing",
            original_price=amount,
            original_currency="",
            fx_rate_used=None,
            converted_purchase_price_jpy=None,
            budget_limit_jpy=budget_limit_jpy,
        )
    if code not in {"USD", "EUR", "GBP", "JPY"}:
        return BudgetDecision(
            result="unsupported_currency",
            reason="unsupported_currency",
            original_price=amount,
            original_currency=code,
            fx_rate_used=None,
            converted_purchase_price_jpy=None,
            budget_limit_jpy=budget_limit_jpy,
        )
    rate = snapshot.rate_for(code)
    if rate is None:
        return BudgetDecision(
            result="currency_unavailable",
            reason=f"fx_unavailable:{code}",
            original_price=amount,
            original_currency=code,
            fx_rate_used=None,
            converted_purchase_price_jpy=None,
            budget_limit_jpy=budget_limit_jpy,
        )
    converted = convert_to_jpy(amount, code, snapshot)
    if converted is None:
        return BudgetDecision(
            result="currency_unavailable",
            reason=f"fx_unavailable:{code}",
            original_price=amount,
            original_currency=code,
            fx_rate_used=rate,
            converted_purchase_price_jpy=None,
            budget_limit_jpy=budget_limit_jpy,
        )
    if budget_limit_jpy is not None and converted > Decimal(budget_limit_jpy):
        return BudgetDecision(
            result="over_budget",
            reason="over_budget",
            original_price=amount,
            original_currency=code,
            fx_rate_used=rate,
            converted_purchase_price_jpy=converted,
            budget_limit_jpy=budget_limit_jpy,
        )
    return BudgetDecision(
        result="pass",
        reason="within_budget" if budget_limit_jpy is not None else "no_limit",
        original_price=amount,
        original_currency=code,
        fx_rate_used=rate,
        converted_purchase_price_jpy=converted,
        budget_limit_jpy=budget_limit_jpy,
    )


def format_budget_meta(decision: BudgetDecision, *, snapshot_id: str) -> str:
    """Compact audit line stored on listing raw_title / description."""
    parts = [
        f"fx_snapshot_id={snapshot_id}",
        f"original_price={decision.original_price}",
        f"original_currency={decision.original_currency}",
        f"fx_rate_used={decision.fx_rate_used}",
        f"converted_purchase_price_jpy={decision.converted_purchase_price_jpy}",
        f"budget_limit_jpy={decision.budget_limit_jpy}",
        f"budget_filter_result={decision.result}",
        f"budget_filter_reason={decision.reason}",
        "budget_basis=product_price_only",
    ]
    return "; ".join(parts)
