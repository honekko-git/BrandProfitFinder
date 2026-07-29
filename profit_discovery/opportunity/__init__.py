"""Opportunity ranking layer for purchase-priority discovery results."""

from profit_discovery.opportunity.auto_demand_pipeline import build_auto_demand_integrated_ranking
from profit_discovery.opportunity.demand_integration import (
    analyze_demand_for_queries,
    build_demand_integrated_opportunities,
)
from profit_discovery.opportunity.demand_ranking import rank_demand_integrated_opportunities
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_discovery.opportunity.identity_pipeline import build_identity_demand_integrated_ranking
from profit_discovery.opportunity.models import (
    DemandIntegratedOpportunityResult,
    DemandIntegratedOpportunityScore,
    OpportunityResult,
    OpportunityScore,
)
from profit_discovery.opportunity.ranking import rank_opportunities
from profit_discovery.opportunity.scorer import OpportunityScorer

__all__ = [
    "DemandIntegratedOpportunityResult",
    "DemandIntegratedOpportunityScore",
    "DemandIntegratedOpportunityScorer",
    "OpportunityResult",
    "OpportunityScore",
    "OpportunityScorer",
    "analyze_demand_for_queries",
    "build_auto_demand_integrated_ranking",
    "build_demand_integrated_opportunities",
    "build_identity_demand_integrated_ranking",
    "rank_demand_integrated_opportunities",
    "rank_opportunities",
]
