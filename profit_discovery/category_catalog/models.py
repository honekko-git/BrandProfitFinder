"""Category catalog models for brand-category discovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CategoryPriority(StrEnum):
    """Category exploration priority."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class CategoryProfile:
    """One discoverable product category entry."""

    name: str
    priority: str
    target_brands: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class BrandCategorySearchTarget:
    """One brand and category combination to search."""

    brand: str
    category: str
    query: str
