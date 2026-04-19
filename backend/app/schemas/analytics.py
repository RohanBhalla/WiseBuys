from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VendorAnalyticsSummary(BaseModel):
    vendor_user_id: int
    company_legal_name: str
    total_products: int
    published_products: int
    allowed_tag_count: int
    total_clicks: int
    clicks_last_30d: int
    clicks_last_7d: int
    distinct_click_users: int
    recommended_customers: int
    recommendation_appearances: int
    reach_sample_size: int
    total_active_customers: int


class CompetitorRow(BaseModel):
    vendor_user_id: int
    company_legal_name: str
    shared_categories: list[str]
    shared_tag_labels: list[str]
    overlap_product_count: int
    their_avg_price: float | None = None
    your_avg_price: float | None = None
    price_position: str
    co_recommendation_count: int
    overlap_score: float


class PricingInsightRow(BaseModel):
    category: str
    your_avg_price: float
    your_min_price: float
    your_max_price: float
    market_avg_price: float
    market_median_price: float
    market_min_price: float
    market_max_price: float
    market_sample_size: int
    percentile: float
    position: str
    recommendation: str


class TopProductRow(BaseModel):
    product_id: int
    name: str
    category: str | None = None
    price_hint: float | None = None
    is_published: bool
    recommendation_appearances: int
    click_count: int


class RecentClickRow(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    source: str
    created_at: datetime


class VendorAnalyticsResponse(BaseModel):
    summary: VendorAnalyticsSummary
    competitors: list[CompetitorRow]
    pricing_insights: list[PricingInsightRow]
    top_products: list[TopProductRow]
    recent_clicks: list[RecentClickRow]
