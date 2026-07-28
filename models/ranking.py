"""
Ranking models for profit and brand aggregation.
"""

from dataclasses import dataclass, field

from models.product import Product


@dataclass
class RankingEntry:
    """Single ranked item with score metadata."""

    rank: int
    label: str
    score: float
    product: Product | None = None


@dataclass
class Ranking:
    """Ordered collection of ranking entries."""

    title: str
    entries: list[RankingEntry] = field(default_factory=list)

    def sort_by_score(self, descending: bool = True) -> None:
        """
        Sort entries by score and reassign rank numbers.

        Args:
            descending: Sort highest score first when True.
        """
        self.entries.sort(key=lambda item: item.score, reverse=descending)
        for index, entry in enumerate(self.entries, start=1):
            entry.rank = index

    @classmethod
    def from_products(
        cls,
        title: str,
        products: list[Product],
        score_attr: str = "profit",
    ) -> "Ranking":
        """
        Build a ranking from product list using the given score attribute.

        Args:
            title: Ranking sheet title.
            products: Source products.
            score_attr: Product attribute used as score.

        Returns:
            Ranking instance sorted by score descending.
        """
        entries = [
            RankingEntry(
                rank=0,
                label=getattr(product, "name", "") or product.brand,
                score=float(getattr(product, score_attr, 0.0) or 0.0),
                product=product,
            )
            for product in products
        ]
        ranking = cls(title=title, entries=entries)
        ranking.sort_by_score(descending=True)
        return ranking
