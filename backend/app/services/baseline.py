"""Baseline climatology threshold computation using a 366-day index and 15-day centered window."""

import logging
from typing import Dict, Tuple, Optional
import numpy as np
import pandas as pd
from app.core.config import settings
from app.models.schemas import BaselineInfo

logger = logging.getLogger("climate_analyzer.baseline")


def map_date_to_doy366(dt_series: pd.Series) -> pd.Series:
    """
    Maps a datetime series to a standardized 366-day calendar:
    - Jan 1 -> 1 ... Feb 28 -> 59
    - Feb 29 (in leap years) -> 60
    - Mar 1 -> 61 ... Dec 31 -> 366
    In non-leap years, days on or after Mar 1 (month > 2) are shifted by +1
    so that calendar dates (e.g. July 4) align to the exact same day-of-year index.
    """
    month = dt_series.dt.month
    dayofyear = dt_series.dt.dayofyear
    is_leap = dt_series.dt.is_leap_year

    # For non-leap years after February, shift by +1 so DOY 60 remains reserved for Feb 29
    shift_mask = (~is_leap) & (month > 2)
    standardized_doy = dayofyear.copy()
    standardized_doy.loc[shift_mask] += 1
    return standardized_doy


def compute_baseline_thresholds(
    cleaned_df: pd.DataFrame,
    percentile: float = 95.0,
    baseline_start: int = settings.BASELINE_START_YEAR,
    baseline_end: int = settings.BASELINE_END_YEAR,
    window_days: int = settings.BASELINE_WINDOW_DAYS,
) -> Tuple[np.ndarray, BaselineInfo]:
    """
    Computes daily climatological percentile thresholds for DOY 1 to 366.
    
    Methodology:
    1. Filter data to baseline period (default 1991-2020).
    2. Map all baseline dates to a 366-day index.
    3. For each DOY d (1..366, except DOY 60):
       Pool daily tmax values within a centered 15-day window [d - 7, d + 7] across all baseline years,
       with circular wrap-around at year ends (Dec 31 wraps to Jan 1).
       Compute the P-th percentile (np.percentile).
    4. Feb 29 (DOY 60):
       Interpolate threshold linearly between Feb 28 (DOY 59) and Mar 1 (DOY 61).
       (Documented in code and README per spec).
       
    Returns:
    - 1D numpy array of length 367 (1-indexed, index 0 unused, index 1..366 thresholds)
    - BaselineInfo metadata model
    """
    df = cleaned_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

    # Slice baseline years
    baseline_mask = (df.index.year >= baseline_start) & (df.index.year <= baseline_end)
    baseline_slice = df[baseline_mask]

    years_present = sorted(baseline_slice.index.year.unique().tolist())
    expected_years = baseline_end - baseline_start + 1
    is_fallback = len(years_present) < expected_years

    if len(years_present) == 0:
        # Fallback to whatever years are available in cleaned_df
        logger.warning(f"No baseline data in {baseline_start}-{baseline_end}. Falling back to available years.")
        baseline_slice = df
        years_present = sorted(df.index.year.unique().tolist())
        is_fallback = True
        note = f"Warning: Reference period {baseline_start}-{baseline_end} unavailable. Fell back to available years ({years_present[0]}-{years_present[-1]})."
    elif is_fallback:
        note = f"Reference period partially available ({len(years_present)} of {expected_years} years present: {min(years_present)}-{max(years_present)})."
    else:
        note = f"Standard fixed baseline period {baseline_start}-{baseline_end} ({len(years_present)} years). Centered {window_days}-day window across all baseline years."

    # Map dates to DOY 1..366
    dt_index_series = pd.Series(baseline_slice.index, index=baseline_slice.index)
    baseline_slice = baseline_slice.assign(doy366=map_date_to_doy366(dt_index_series))

    # Pre-aggregate valid temperatures by standardized doy
    doy_values_map: Dict[int, np.ndarray] = {}
    for d in range(1, 367):
        vals = baseline_slice.loc[baseline_slice["doy366"] == d, "tmax"].dropna().values
        doy_values_map[d] = vals

    # Array of thresholds 1..366 (size 367)
    thresholds = np.zeros(367, dtype=float)
    half_window = window_days // 2  # 7 for 15-day window

    for target_doy in range(1, 367):
        if target_doy == 60:
            # DOY 60 is Feb 29 - will interpolate between DOY 59 and DOY 61 after the loop
            continue

        # Gather circular window: [target_doy - half_window, target_doy + half_window]
        window_samples = []
        for offset in range(-half_window, half_window + 1):
            d = target_doy + offset
            # Circular wrap around 1..366 (skipping 60 during sample gathering)
            while d < 1:
                d += 366
            while d > 366:
                d -= 366
            if d == 60:
                continue  # Leap day samples are rare; pool standard calendar days
            sample = doy_values_map.get(d)
            if sample is not None and len(sample) > 0:
                window_samples.append(sample)

        if window_samples:
            combined = np.concatenate(window_samples)
            thresholds[target_doy] = float(np.percentile(combined, percentile))
        else:
            thresholds[target_doy] = np.nan

    # 4. Feb 29 (DOY 60) interpolation: exactly halfway between Feb 28 (DOY 59) and Mar 1 (DOY 61)
    thresholds[60] = float((thresholds[59] + thresholds[61]) / 2.0)

    baseline_info = BaselineInfo(
        reference_period=f"{baseline_start}-{baseline_end}",
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        years_used=len(years_present),
        is_fallback=is_fallback,
        note=note,
    )

    return thresholds, baseline_info
