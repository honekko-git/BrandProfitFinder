"""
Exchange rate utilities.
"""

from config.settings import DEFAULT_EXCHANGE_RATE


def get_exchange_rate(currency: str) -> float:
    """
    Return the exchange rate to JPY for the given currency.

    Args:
        currency: ISO currency code (e.g. USD, EUR).

    Returns:
        Exchange rate multiplier to JPY.
    """
    normalized = currency.upper()
    if normalized == "JPY":
        return 1.0
    if normalized in ("USD", "EUR"):
        return DEFAULT_EXCHANGE_RATE
    return DEFAULT_EXCHANGE_RATE


def convert_to_jpy(amount: float, currency: str, rate: float | None = None) -> float:
    """
    Convert a foreign currency amount to JPY.

    Args:
        amount: Amount in source currency.
        currency: ISO currency code.
        rate: Optional explicit exchange rate override.

    Returns:
        Amount in JPY.
    """
    effective_rate = rate if rate is not None else get_exchange_rate(currency)
    return round(amount * effective_rate, 2)
