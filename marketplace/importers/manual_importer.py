"""Manual market listing input helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from marketplace.connectors.models import MarketListing
from marketplace.importers.validators import validate_row


class ManualImporter:
    """Create MarketListing rows from manual form input."""

    def create_listing(
        self,
        *,
        title: str,
        brand: str,
        category: str = "",
        condition: str = "used",
        price: str | Decimal | float | int = "0",
        currency: str = "JPY",
        market_name: str = "",
        url: str = "",
    ) -> MarketListing:
        """Validate manual input and return one MarketListing."""
        row = {
            "title": title.strip(),
            "brand": brand.strip(),
            "category": category.strip() or "bag",
            "condition": condition.strip() or "used",
            "price": str(price).strip(),
            "currency": currency.strip().upper() or "JPY",
            "market_name": market_name.strip(),
            "url": url.strip(),
        }
        ok, errors = validate_row(row)
        if not ok:
            raise ValueError("; ".join(errors))
        return _row_to_market_listing(row)


def _row_to_market_listing(row: dict[str, str]) -> MarketListing:
    return MarketListing(
        id=f"manual-{uuid4().hex[:12]}",
        title=row["title"],
        brand=row["brand"],
        category=row["category"],
        condition=row["condition"],
        price=Decimal(str(row["price"]).replace(",", "")),
        currency=row["currency"],
        market_name=row["market_name"],
        url=row["url"],
        source_type="IMPORT",
        created_at=datetime.now(tz=UTC),
    )
