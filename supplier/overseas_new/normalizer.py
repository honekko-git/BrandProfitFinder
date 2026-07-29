"""Currency normalization for overseas new supplier products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


ExchangeRateProvider = Callable[[str], float | None]


@dataclass(frozen=True, slots=True)
class NormalizedCurrency:
    """Deterministic currency normalization result."""

    amount_jpy: float | None
    original_amount: float
    currency: str


class CurrencyNormalizer:
    """
    Normalize supplier currency values using static rates or a provider function.

    No external API calls are performed.
    """

    def __init__(
        self,
        *,
        exchange_rates: Mapping[str, float] | None = None,
        exchange_rate_provider: ExchangeRateProvider | None = None,
    ) -> None:
        self._exchange_rates = {
            currency.upper(): float(rate)
            for currency, rate in (exchange_rates or {}).items()
        }
        self._exchange_rate_provider = exchange_rate_provider

    def normalize(self, amount: float, currency: str) -> NormalizedCurrency:
        """Normalize one amount and currency pair."""
        normalized_currency = currency.strip().upper() or "USD"
        original_amount = float(amount)

        if normalized_currency == "JPY":
            return NormalizedCurrency(
                amount_jpy=original_amount,
                original_amount=original_amount,
                currency="JPY",
            )

        rate = self._resolve_rate(normalized_currency)
        if rate is None:
            return NormalizedCurrency(
                amount_jpy=None,
                original_amount=original_amount,
                currency=normalized_currency,
            )

        return NormalizedCurrency(
            amount_jpy=round(original_amount * rate, 2),
            original_amount=original_amount,
            currency=normalized_currency,
        )

    def normalize_mapping(self, payload: Mapping[str, object]) -> NormalizedCurrency:
        """Normalize a mapping such as {"amount": 300, "currency": "USD"}."""
        amount = float(payload["amount"])
        currency = str(payload["currency"])
        return self.normalize(amount, currency)

    def _resolve_rate(self, currency: str) -> float | None:
        if currency in self._exchange_rates:
            return self._exchange_rates[currency]
        if self._exchange_rate_provider is not None:
            return self._exchange_rate_provider(currency)
        return None
