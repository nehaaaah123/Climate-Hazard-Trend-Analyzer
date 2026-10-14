"""Vectorized heatwave detection and annual metrics calculation."""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from app.models.schemas import (
    EventsSummary,
    HeatwaveEvent,
    YearlyMetrics,
)
from app.services.baseline import map_date_to_doy366

logger = logging.getLogger("climate_analyzer.detector")


def detect_heatwave_events(
    continuous_df: pd.DataFrame,
    thresholds: np.ndarray,
    min_days: int = 3,
) -> List[HeatwaveEvent]:
    """
    Detects heatwave events across a continuous multi-year daily series using a vectorized run-length algorithm.
    
    A heatwave is defined as >= min_days consecutive days where daily tmax exceeds that calendar day's threshold.
    Any NaN gap breaks the streak immediately.
    Events spanning year boundaries (e.g. Dec 31 to Jan 2) are preserved continuous and attributed to their start year.
    """
    if continuous_df.empty:
        return []

    df = continuous_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

    # Map daily timestamps to standardized DOY 1..366 and look up daily threshold
    doy_series = map_date_to_doy366(pd.Series(df.index, index=df.index))
    daily_thresholds = thresholds[doy_series.values]
    df["threshold"] = daily_thresholds

    # Identify hot days (must be strictly greater than threshold and not NaN)
    is_hot = (df["tmax"] > df["threshold"]) & df["tmax"].notna()

    if not is_hot.any():
        return []

    # Vectorized run-length encoding:
    # A new run begins whenever is_hot differs from the preceding day
    run_id = (is_hot != is_hot.shift()).cumsum()

    # Filter strictly to the hot slices and group by run_id
    hot_slices = df[is_hot]
    grouped = hot_slices.groupby(run_id)

    events: List[HeatwaveEvent] = []
    event_counter = 1

    for _, group in grouped:
        duration = len(group)
        if duration >= min_days:
            start_dt = group.index[0]
            end_dt = group.index[-1]
            start_yr = int(start_dt.year)
            peak_temp = round(float(group["tmax"].max()), 2)
            
            # Intensity is the mean temperature anomaly above the daily threshold
            anomalies = group["tmax"] - group["threshold"]
            mean_intensity = round(float(anomalies.mean()), 2)

            event = HeatwaveEvent(
                event_id=event_counter,
                start_date=start_dt.strftime("%Y-%m-%d"),
                end_date=end_dt.strftime("%Y-%m-%d"),
                duration=duration,
                peak_temp=peak_temp,
                mean_intensity=mean_intensity,
                start_year=start_yr,
            )
            events.append(event)
            event_counter += 1

    return events


def compute_yearly_metrics(
    cleaned_df: pd.DataFrame,
    events: List[HeatwaveEvent],
    start_year: int,
    end_year: int,
    excluded_years: Optional[List[int]] = None,
) -> List[YearlyMetrics]:
    """
    Aggregates per-year metrics:
    - event_count: number of events starting in that year
    - total_heatwave_days: total days of events attributed to that year
    - max_duration: longest event starting in that year (0 if none)
    - mean_intensity: average intensity of events starting in that year (0.0 if none)
    - peak_temp: maximum temperature reached during events (or highest tmax in year if no events)
    """
    excluded_set = set(excluded_years or [])
    yearly_metrics: List[YearlyMetrics] = []

    # Map events by start_year
    events_by_year: Dict[int, List[HeatwaveEvent]] = {}
    for yr in range(start_year, end_year + 1):
        events_by_year[yr] = []
    for ev in events:
        if ev.start_year in events_by_year:
            events_by_year[ev.start_year].append(ev)

    for yr in range(start_year, end_year + 1):
        year_events = events_by_year.get(yr, [])
        year_mask = (cleaned_df.index.year == yr)
        year_df = cleaned_df[year_mask]
        
        # Max annual temperature observed
        max_ann_temp = round(float(year_df["tmax"].max()), 2) if not year_df["tmax"].dropna().empty else 0.0

        if not year_events:
            yearly_metrics.append(
                YearlyMetrics(
                    year=yr,
                    event_count=0,
                    total_heatwave_days=0,
                    max_duration=0,
                    mean_intensity=0.0,
                    peak_temp=max_ann_temp,
                )
            )
        else:
            total_days = sum(e.duration for e in year_events)
            max_dur = max(e.duration for e in year_events)
            mean_intens = round(float(np.mean([e.mean_intensity for e in year_events])), 2)
            peak_t = max(e.peak_temp for e in year_events)

            yearly_metrics.append(
                YearlyMetrics(
                    year=yr,
                    event_count=len(year_events),
                    total_heatwave_days=total_days,
                    max_duration=max_dur,
                    mean_intensity=mean_intens,
                    peak_temp=peak_t,
                )
            )

    return yearly_metrics
