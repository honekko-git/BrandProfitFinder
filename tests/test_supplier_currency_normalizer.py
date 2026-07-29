"""Tests for supplier currency normalization."""

from __future__ import annotations

from supplier.overseas_new.normalizer import CurrencyNormalizer


def test_currency_normalizer_converts_usd_to_jpy() -> None:
    normalizer = CurrencyNormalizer(exchange_rates={"USD": 150})

    result = normalizer.normalize_mapping({"amount": 300, "currency": "USD"})

    assert result.amount_jpy == 45000.0
    assert result.original_amount == 300.0
    assert result.currency == "USD"


def test_currency_normalizer_converts_eur_to_jpy() -> None:
    normalizer = CurrencyNormalizer(exchange_rates={"EUR": 160})

    result = normalizer.normalize(250.0, "eur")

    assert result.amount_jpy == 40000.0
    assert result.original_amount == 250.0
    assert result.currency == "EUR"


def test_currency_normalizer_handles_unknown_currency() -> None:
    normalizer = CurrencyNormalizer(exchange_rates={"USD": 150})

    result = normalizer.normalize(500.0, "GBP")

    assert result.amount_jpy is None
    assert result.original_amount == 500.0
    assert result.currency == "GBP"


def test_currency_normalizer_uses_exchange_rate_provider() -> None:
    rates = {"AUD": 100.0}

    def provider(currency: str) -> float | None:
        return rates.get(currency)

    normalizer = CurrencyNormalizer(exchange_rate_provider=provider)

    result = normalizer.normalize(120.0, "AUD")

    assert result.amount_jpy == 12000.0
    assert result.original_amount == 120.0
    assert result.currency == "AUD"


def test_currency_normalizer_jpy_is_deterministic() -> None:
    normalizer = CurrencyNormalizer(exchange_rates={"USD": 150})

    first = normalizer.normalize(45000.0, "JPY")
    second = normalizer.normalize(45000.0, "JPY")

    assert first == second
    assert first.amount_jpy == 45000.0
    assert first.currency == "JPY"
