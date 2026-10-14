"""Pydantic schemas and validation for queries and API responses."""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


def snap_coordinate(value: float, step: float = 0.25) -> float:
    """Snap a coordinate to the nearest step (e.g. 0.25 degrees)."""
    return round(round(value / step) * step, 4)


class RegionInfo(BaseModel):
    input_lat: Optional[float] = None
    input_lon: Optional[float] = None
    grid_lat: float
    grid_lon: float
    snapped: bool = True
    is_bbox: bool = False
    bbox: Optional[List[float]] = None
    warning: Optional[str] = None


class YearQuality(BaseModel):
    year: int
    valid_pct: float
    missing_days: int
    short_gaps_filled: int
    outliers_detected: int
    is_valid: bool


class DataQualityReport(BaseModel):
    total_years: int
    valid_years: int
    excluded_years: List[int]
    yearly_scores: List[YearQuality]
    warnings: List[str] = Field(default_factory=list)


class BaselineInfo(BaseModel):
    reference_period: str
    baseline_start: int
    baseline_end: int
    years_used: int
    is_fallback: bool = False
    note: str


class YearlyMetrics(BaseModel):
    year: int
    event_count: int
    total_heatwave_days: int
    max_duration: int
    mean_intensity: float
    peak_temp: float


class RollingAveragePoint(BaseModel):
    year: int
    heatwave_days_rolling_avg: Optional[float] = None
    event_count_rolling_avg: Optional[float] = None


class RollingAverages(BaseModel):
    window: int = 5
    series: List[RollingAveragePoint]


class OLSStats(BaseModel):
    slope_per_decade: float
    intercept: float
    r_squared: float
    p_value: float


class TheilSenStats(BaseModel):
    slope_per_decade: float


class MannKendallStats(BaseModel):
    tau: float
    p_value: float
    trend: str  # 'increasing', 'decreasing', 'no trend'
    statistically_significant: bool


class TrendStats(BaseModel):
    ols: OLSStats
    theil_sen: TheilSenStats
    mann_kendall: MannKendallStats


class HeatwaveEvent(BaseModel):
    event_id: int
    start_date: str
    end_date: str
    duration: int
    peak_temp: float
    mean_intensity: float
    start_year: int


class EventsSummary(BaseModel):
    total_events: int
    top_events: List[HeatwaveEvent]


class HeatwaveAnalysisParams(BaseModel):
    hazard_type: str = "heatwave"
    start_year: int
    end_year: int
    percentile: float = 95.0
    min_days: int = 3
    baseline_period: str = "1991-2020"
    window_days: int = 15


class AnalysisResponse(BaseModel):
    region: RegionInfo
    parameters: HeatwaveAnalysisParams
    baseline_info: BaselineInfo
    data_quality: DataQualityReport
    per_year_metrics: List[YearlyMetrics]
    rolling_averages: RollingAverages
    trend_stats: TrendStats
    insights: List[str]
    events_summary: EventsSummary
    cached: bool
    computed_at: str


class PaginatedEventsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    events: List[HeatwaveEvent]


class RegionPreset(BaseModel):
    name: str
    country: str
    lat: float
    lon: float
    description: str


class RegionsResponse(BaseModel):
    regions: List[RegionPreset]
