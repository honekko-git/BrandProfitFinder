"""Sales demand intelligence layer."""

from profit_intelligence.demand.analyzer import DemandAnalyzer
from profit_intelligence.demand.lookup import DemandLookup
from profit_intelligence.demand.models import DemandQuery, SalesDemandProfile
from profit_intelligence.demand.resolver import DemandQueryResolver

__all__ = [
    "DemandAnalyzer",
    "DemandLookup",
    "DemandQuery",
    "DemandQueryResolver",
    "SalesDemandProfile",
]
