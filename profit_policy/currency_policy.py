"""Currency validation and exchange-rate resolution policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from config.settings import DEFAULT_EXCHANGE_RATE
from models.product import Product

KNOWN_CURRENCIES = frozenset({"USD", "EUR", "JPY"})


@dataclass(frozen=True, slots=True)
class CurrencyPolicy:
    """
    Validate currencies and resolve exchange rates from explicit inputs only.

    Does not perform network lookups or currency conversion beyond applying a
    known rate to a source amount (handled by the profit calculator).
    """

    known_currencies: frozenset[str] = KNOWN_CURRENCIES
    exchange_rates: dict[str, Decimal] = field(default_factory=dict)
    default_exchange_rate: Decimal = Decimal(str(DEFAULT_EXCHANGE_RATE))

    def normalize_currency(self, currency: str) -> str:
        """Normalize a currency code to uppercase."""
        return currency.strip().upper() or "USD"

    def is_known_currency(self, currency: str) -> bool:
        """Return True when currency is in the known set."""
        return self.normalize_currency(currency) in self.known_currencies

    def validate_currency(self, currency: str) -> bool:
        """Return True when currency is recognized for rate resolution."""
        return self.is_known_currency(currency)

    def resolve_exchange_rate(self, product: Product, currency: str) -> Decimal | None:
        """
        Resolve an exchange rate from product override, configured rates, or default.

        Returns None for unknown currencies without an explicit rate.
        """
        normalized = self.normalize_currency(currency)
        if normalized == "JPY":
            return Decimal("1")

        if product.exchange_rate and product.exchange_rate > 0:
            return Decimal(str(product.exchange_rate))

        configured = self.exchange_rates.get(normalized)
        if configured is not None:
            return configured

        if normalized in self.known_currencies:
            return self.default_exchange_rate

        return None
