"""Vestiaire Collective used luxury supplier integration."""

from supplier.vestiaire.adapter import to_supplier_product
from supplier.vestiaire.client import VestiaireClient
from supplier.vestiaire.models import VestiaireProduct

__all__ = [
    "VestiaireClient",
    "VestiaireProduct",
    "to_supplier_product",
]
