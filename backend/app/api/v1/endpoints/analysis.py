"""Analysis endpoints for heatwave detection, trend statistics, and paginated events."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, Query, Request, status
from app.core.config import settings
from app.core.database import get_database
from app.core.errors import ClimateAnalyzerException, InvalidRegionError
from app.core.limiter import limiter
from app.models.schemas import (
    AnalysisResponse,
    EventsSummary,
    HeatwaveAnalysisParams,
    HeatwaveEvent,
    PaginatedEventsResponse,
    RegionInfo,
)
from app.services.baseline import compute_baseline_thresholds
from app.services.cleaning import clean_series
from app.services.heatwave_detector import compute_yearly_metrics, detect_heatwave_events
from app.services.insights import generate_honest_insights
from app.services.open_meteo import get_temperature_series, resolve_coordinates
from app.services.trends import compute_rolling_averages, compute_trend_statistics

logger = logging.getLogger("climate_analyzer.analysis")

router = APIRouter()


def validate_analysis_query(
    lat: Optional[float] = Query(None, description="Latitude [-90.0, 90.0]"),
    lon: Optional[float] = Query(None, description="Longitude [-180.0, 180.0]"),
    bbox: Optional[str] = Query(None, description="Bounding box 'min_lat,min_lon,max_lat,max_lon'"),
    start_year: int = Query(1990, description="Start year [1950..current_year-1]"),
    end_year: int = Query(2023, description="End year [1950..current_year-1]"),
    percentile: float = Query(95.0, description="Climatological percentile threshold [85.0..99.0]"),
    min_days: int = Query(3, description="Minimum consecutive days [2..7]"),
    hazard_type: str = Query("heatwave", description="Hazard type (only 'heatwave' supported)"),
) -> Dict[str, Any]:
    """Validates input parameters according to spec bounds."""
    # 1. Hazard type check
    if hazard_type.strip().lower() != "heatwave":
        raise ClimateAnalyzerException(
            f"Hazard type '{hazard_type}' is unsupported. Currently only 'heatwave' is supported. Drought and rainfall hazards are out of scope.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"requested_hazard": hazard_type, "allowed": ["heatwave"]},
        )

    # 2. Year bounds check
    current_year = datetime.now(timezone.utc).year
    max_allowed_year = current_year - 1
    min_allowed_year = 1950

    if start_year < min_allowed_year or start_year > max_allowed_year:
        raise ClimateAnalyzerException(
            f"start_year {start_year} is out of bounds [{min_allowed_year}, {max_allowed_year}].",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if end_year < min_allowed_year or end_year > max_allowed_year:
        raise ClimateAnalyzerException(
            f"end_year {end_year} is out of bounds [{min_allowed_year}, {max_allowed_year}].",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if start_year > end_year:
        raise ClimateAnalyzerException(
            f"start_year ({start_year}) cannot be greater than end_year ({end_year}).",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if (end_year - start_year + 1) > 50:
        raise ClimateAnalyzerException(
            f"Requested year span ({end_year - start_year + 1} years) exceeds the maximum allowed 50 years.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Percentile check
    if percentile < 85.0 or percentile > 99.0:
        raise ClimateAnalyzerException(
            f"percentile {percentile} is out of bounds [85.0, 99.0].",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Min days check
    if min_days < 2 or min_days > 7:
        raise ClimateAnalyzerException(
            f"min_days {min_days} is out of bounds [2, 7].",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 5. Resolve coordinates & validate bbox
    region, grid_lat, grid_lon = resolve_coordinates(lat=lat, lon=lon, bbox=bbox)

    return {
        "region": region,
        "grid_lat": grid_lat,
        "grid_lon": grid_lon,
        "start_year": start_year,
        "end_year": end_year,
        "percentile": percentile,
        "min_days": min_days,
        "hazard_type": "heatwave",
    }


async def execute_heatwave_analysis(
    validated: Dict[str, Any],
) -> Tuple[AnalysisResponse, List[HeatwaveEvent]]:
    """
    Core orchestrator: checks MongoDB cache, or fetches data, cleans series,
    computes baseline, detects events, computes trends, and stores result (compute-on-miss).
    """
    grid_lat = validated["grid_lat"]
    grid_lon = validated["grid_lon"]
    start_year = validated["start_year"]
    end_year = validated["end_year"]
    percentile = validated["percentile"]
    min_days = validated["min_days"]
    region: RegionInfo = validated["region"]

    baseline_start = settings.BASELINE_START_YEAR
    baseline_end = settings.BASELINE_END_YEAR

    cache_key = {
        "grid_lat": grid_lat,
        "grid_lon": grid_lon,
        "start_year": start_year,
        "end_year": end_year,
        "percentile": percentile,
        "min_days": min_days,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
    }

    db = get_database()

    # 1. Check analysis_results collection cache
    if db is not None:
        try:
            cached_doc = await db.analysis_results.find_one(cache_key)
            if cached_doc and "result_payload" in cached_doc:
                payload = cached_doc["result_payload"]
                payload["cached"] = True
                response_obj = AnalysisResponse(**payload)
                # Parse all events if stored
                stored_events = [HeatwaveEvent(**e) for e in cached_doc.get("all_events", [])]
                return response_obj, stored_events
        except Exception as e:
            logger.warning(f"Error checking analysis_results cache: {e}")

    # 2. Cache miss: Fetch union of baseline years and requested study range
    union_years = sorted(list(set(range(start_year, end_year + 1)).union(range(baseline_start, baseline_end + 1))))
    raw_df, unit_str = await get_temperature_series(grid_lat, grid_lon, union_years)

    # 3. Run CPU-intensive computations in threadpool to keep asyncio event loop responsive
    def run_pipeline():
        # A. Clean entire series
        min_yr = min(union_years)
        max_yr = max(union_years)
        cleaned_df, qa_report = clean_series(raw_df, start_year=min_yr, end_year=max_yr, unit=unit_str)

        # B. Compute baseline thresholds (1991-2020)
        thresholds, baseline_info = compute_baseline_thresholds(
            cleaned_df,
            percentile=percentile,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
        )

        # Filter cleaned df to requested study period
        study_mask = (cleaned_df.index.year >= start_year) & (cleaned_df.index.year <= end_year)
        study_df = cleaned_df[study_mask]

        # Filter qa_report to requested study years
        study_scores = [s for s in qa_report.yearly_scores if start_year <= s.year <= end_year]
        study_excluded = [y for y in qa_report.excluded_years if start_year <= y <= end_year]
        qa_report.yearly_scores = study_scores
        qa_report.excluded_years = study_excluded
        qa_report.total_years = len(study_scores)
        qa_report.valid_years = len(study_scores) - len(study_excluded)

        # C. Detect continuous heatwave events across study period
        events = detect_heatwave_events(study_df, thresholds, min_days=min_days)

        # D. Aggregate per-year metrics
        yearly_metrics = compute_yearly_metrics(study_df, events, start_year, end_year, study_excluded)

        # E. Rolling averages and trend statistics
        rolling_avg = compute_rolling_averages(yearly_metrics, window=5)
        trend_stats = compute_trend_statistics(yearly_metrics, study_excluded)

        # F. Generate honest insights
        insights = generate_honest_insights(
            yearly_metrics,
            trend_stats,
            start_year,
            end_year,
            study_excluded,
            grid_lat=grid_lat,
            grid_lon=grid_lon,
        )

        # Sort top events by duration (descending) and peak_temp
        sorted_events = sorted(events, key=lambda e: (e.duration, e.peak_temp), reverse=True)
        top_events = sorted_events[:10]
        events_summary = EventsSummary(total_events=len(events), top_events=top_events)

        params_obj = HeatwaveAnalysisParams(
            hazard_type="heatwave",
            start_year=start_year,
            end_year=end_year,
            percentile=percentile,
            min_days=min_days,
            baseline_period=f"{baseline_start}-{baseline_end}",
        )

        analysis_resp = AnalysisResponse(
            region=region,
            parameters=params_obj,
            baseline_info=baseline_info,
            data_quality=qa_report,
            per_year_metrics=yearly_metrics,
            rolling_averages=rolling_avg,
            trend_stats=trend_stats,
            insights=insights,
            events_summary=events_summary,
            cached=False,
            computed_at=datetime.now(timezone.utc).isoformat(),
        )
        return analysis_resp, events

    analysis_response, all_events = await asyncio.to_thread(run_pipeline)

    # 4. Save computed result to analysis_results collection
    if db is not None:
        try:
            store_doc = {
                **cache_key,
                "result_payload": analysis_response.model_dump(),
                "all_events": [e.model_dump() for e in all_events],
                "computed_at": datetime.now(timezone.utc),
            }
            await db.analysis_results.update_one(
                cache_key,
                {"$set": store_doc},
                upsert=True,
            )
        except Exception as exc:
            logger.warning(f"Failed to cache analysis_results in MongoDB: {exc}")

    return analysis_response, all_events


@router.get("/heatwave", response_model=AnalysisResponse)
@limiter.limit(settings.RATE_LIMIT_ANALYSIS)
async def analyze_heatwave(
    request: Request,
    validated: Dict[str, Any] = Depends(validate_analysis_query),
) -> AnalysisResponse:
    """
    Main heatwave analysis endpoint.
    Performs data retrieval, cleaning, baseline calculation, event detection,
    trend analysis (OLS, Theil-Sen, Mann-Kendall), and returns insights with caching.
    """
    analysis_response, _ = await execute_heatwave_analysis(validated)
    return analysis_response


@router.get("/heatwave/events", response_model=PaginatedEventsResponse)
@limiter.limit(settings.RATE_LIMIT_ANALYSIS)
async def get_heatwave_events(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Events per page"),
    validated: Dict[str, Any] = Depends(validate_analysis_query),
) -> PaginatedEventsResponse:
    """Paginated heatwave events list sorted by start date."""
    _, all_events = await execute_heatwave_analysis(validated)

    total_events = len(all_events)
    total_pages = max(1, (total_events + page_size - 1) // page_size)

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = all_events[start_idx:end_idx]

    return PaginatedEventsResponse(
        total=total_events,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        events=page_items,
    )
