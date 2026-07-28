"""
Price comparison result model.
"""

from dataclasses import dataclass


@dataclass
class PriceResult:
    """Normalized price from a Japanese marketplace search."""

    marketplace: str
    query: str
    price: float | None
    currency: str = "JPY"
    url: str = ""
    title: str = ""

    @property
    def is_valid(self) -> bool:
        """Return True when a positive price is available."""
        return self.price is not None and self.price > 0
