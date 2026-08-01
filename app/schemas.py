"""Pydantic schemas for the browser dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ControlledLiveVerificationRow(BaseModel):
    """One controlled live profit verification row for browser display."""

    rank: int
    product_id: str
    product: str
    fashionphile_url: str
    purchase_price: str
    purchase_currency: str
    purchase_price_jpy: str
    exchange_rate: str
    yahoo_search_terms: str
    yahoo_sold_samples: int
    yahoo_matched_samples: int
    matching_score: float
    matching_reliability: str
    median_selling_price: str
    average_selling_price: str
    cost_configuration_status: str
    estimated_shipping: str
    estimated_import_cost: str
    estimated_profit: str
    profit_margin: str
    roi: str
    demand_score: float
    turnover_score: float
    decision: str
    acquisition_status: str
    data_status: str
    verification_complete: bool
    retrieved_at: str
    blocking_reason: str = ""


class ValidationForm(BaseModel):
    """Search criteria for profit validation discovery."""

    brand: str = Field(default="Chanel")
    category: str = Field(default="Wallet")
    market_mode: str = Field(default="FIXTURE")
    verification_mode: str = Field(default="STANDARD")
    run_controlled_live: bool = Field(default=False)
    manual_purchase_url: str = Field(default="")
    manual_purchase_title: str = Field(default="")
    manual_purchase_price: str = Field(default="")
    manual_purchase_currency: str = Field(default="USD")


class ValidationResultRow(BaseModel):
    """One profit validation result row."""

    rank: int
    product_id: str
    product: str
    purchase_source: str
    purchase_price: str
    domestic_market: str
    domestic_price: str
    estimated_profit: str
    profit_margin: str
    demand_score: float
    turnover_score: float
    decision: str
    can_save: bool = False


class RealProfitVerificationRow(BaseModel):
    """One real profit verification row for browser display."""

    rank: int
    product_id: str
    product: str
    purchase_source: str
    purchase_url: str
    purchase_price: str
    purchase_currency: str
    purchase_price_jpy: str
    exchange_rate: str
    estimated_shipping: str
    estimated_import_cost: str
    domestic_source: str
    domestic_sold_samples: int
    domestic_average: str
    domestic_median: str
    domestic_url: str
    estimated_profit: str
    profit_margin: str
    roi: str
    demand_score: float
    turnover_score: float
    decision: str
    requested_mode: str
    actual_purchase_source: str
    actual_domestic_source: str
    purchase_fallback: bool
    domestic_fallback: bool
    data_status: str
    retrieved_at: str
    verification_complete: bool
    can_save: bool = False
    yahoo_search_queries: str = ""
    yahoo_live_sample_count: int = 0
    yahoo_matched_sample_count: int = 0
    yahoo_matched_sample_titles: str = ""
    yahoo_sold_prices_display: str = ""
    matching_score: float = 0.0
    matching_reliability: str = ""
    yahoo_diagnostics: str = ""
    purchase_subtype: str = ""
    purchase_material: str = ""
    yahoo_rejected_sample_count: int = 0
    yahoo_accepted_comparables: str = ""
    yahoo_rejected_samples: str = ""
    comparable_median: str = ""
    legacy_median: str = ""
    comparable_data_warning: str = ""


class BatchProfitRow(BaseModel):
    """One batch profit ranking row."""

    rank: int
    candidate_id: str
    product: str
    purchase_source: str
    purchase_price: str
    purchase_price_jpy: str
    subtype: str
    material: str
    accepted_comparables: int
    reliability: str
    recommended_estimate: str
    gross_profit: str
    net_profit: str
    margin: str
    roi: str
    decision: str
    data_status: str
    warning: str
    yahoo_source: str
    details_json: str = ""


class BatchHistoryRow(BaseModel):
    """One batch history row."""

    batch_id: str
    run_date: str
    product_count: int
    strong_candidate_count: int
    top_net_profit: str
    data_status: str
    cost_profile: str


class SearchForm(BaseModel):
    """Search criteria submitted from the dashboard."""

    brand: str = Field(default="Louis Vuitton")
    category: str = Field(default="Wallet")
    market_mode: str = Field(default="FIXTURE")


class RankingCard(BaseModel):
    """One arbitrage ranking card for dashboard display."""

    rank: int
    product_id: str
    product: str
    brand: str
    category: str
    purchase_source: str
    purchase_url: str
    purchase_price: str
    selling_market: str
    selling_url: str
    selling_price: str
    estimated_profit: str
    profit_margin: str
    demand_score: float
    turnover_score: float
    arbitrage_score: float
    decision: str
    market_source: str = ""
    condition: str = ""
    listing_url: str = ""
    listing_source: str = ""
    listing_price: str = "N/A"


class ConnectorExecutionView(BaseModel):
    """Connector execution metadata for one market."""

    market_name: str
    requested_source: str
    actual_source: str
    fallback_used: bool


class SavedOpportunityRow(BaseModel):
    """One saved opportunity row for the saved list page."""

    id: int
    product: str
    brand: str
    purchase_source: str
    profit: str
    score: float
    status: str
    created_date: str


class ImportedListingRow(BaseModel):
    """One imported listing row for the imported listings page."""

    id: int
    product: str
    brand: str
    market_name: str
    price: str
    condition: str
    url: str


class ImportForm(BaseModel):
    """Manual import form fields."""

    title: str = ""
    brand: str = ""
    category: str = "Wallet"
    condition: str = "Used"
    price: str = ""
    currency: str = "JPY"
    market_name: str = "Fashionphile"
    url: str = ""


class ProductDetailView(BaseModel):
    """Detailed product view for the product detail page."""

    product_id: str
    product: str
    brand: str
    category: str
    purchase_source: str
    purchase_url: str
    purchase_price: str
    selling_market: str
    selling_url: str
    selling_price: str
    price_difference: str
    estimated_profit: str
    profit_margin: str
    roi: str
    demand_score: float
    turnover_score: float
    arbitrage_score: float
    profit_rank: int | None = None
    decision: str
    market_mode: str
    market_source: str = ""
    condition: str = ""
    listing_url: str = ""
    saved_record_id: int | None = None
    saved_status: str | None = None
    status_actions: list[str] = Field(default_factory=list)
