"""Data cleaning and quality assurance for temperature time series."""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from app.core.config import settings
from app.core.errors import ClimateAnalyzerException
from app.models.schemas import DataQualityReport, YearQuality


def verify_and_convert_units(series: pd.Series, unit_str: Optional[str]) -> pd.Series:
    """
    Verifies temperature units. Asserts on °C, or converts from °F / K to °C.
    Raises ClimateAnalyzerException if unit is invalid or unknown.
    """
    if not unit_str:
        return series  # Default assumed °C if not provided

    normalized_unit = unit_str.strip().lower()
    if normalized_unit in ["°c", "c", "celsius", "degc"]:
        return series
    elif normalized_unit in ["°f", "f", "fahrenheit", "degf"]:
        # Convert Fahrenheit to Celsius: (F - 32) * 5 / 9
        return (series - 32.0) * (5.0 / 9.0)
    elif normalized_unit in ["k", "kelvin"]:
        # Convert Kelvin to Celsius: K - 273.15
        return series - 273.15
    else:
        raise ClimateAnalyzerException(
            f"Unrecognized temperature unit '{unit_str}'. Expected °C, °F, or K.",
            status_code=400,
            details={"unit": unit_str},
        )


def interpolate_short_gaps_only(series: pd.Series, max_gap_days: int = 2) -> Tuple[pd.Series, int]:
    """
    Fills only short gaps (<= max_gap_days) using linear interpolation.
    Longer gaps (> max_gap_days) remain NaN entirely (no partial filling).
    Returns (cleaned_series, count_of_filled_days).
    """
    s = series.copy()
    is_na = s.isna()

    if not is_na.any():
        return s, 0

    # Group contiguous blocks of NaNs
    # Every time is_na changes from True to False or vice versa, block_id increments
    block_id = (is_na != is_na.shift()).cumsum()

    # Identify size of each NaN block
    nan_blocks = is_na.groupby(block_id).transform("sum")

    # Linearly interpolate entire series bounded by endpoints
    interpolated = s.interpolate(method="linear", limit_direction="both")

    # Days to fill are those originally NaN where the contiguous gap length was <= max_gap_days
    # and interpolation succeeded (not boundary edges without anchors)
    eligible_mask = is_na & (nan_blocks <= max_gap_days) & interpolated.notna()

    filled_count = int(eligible_mask.sum())
    s[eligible_mask] = interpolated[eligible_mask]

    return s, filled_count


def clean_series(
    df: pd.DataFrame,
    start_year: int,
    end_year: int,
    unit: Optional[str] = "°C",
    min_temp_limit: float = -90.0,
    max_temp_limit: float = 60.0,
    min_valid_pct: float = settings.MIN_VALID_YEAR_PCT,
) -> Tuple[pd.DataFrame, DataQualityReport]:
    """
    Performs data cleaning:
    1. Unit verification and normalization to °C.
    2. Reindexing to a complete daily calendar from start_year-01-01 to end_year-12-31.
    3. Flags physically implausible values (< -90°C or > 60°C) as outliers -> NaN.
    4. Interpolates ONLY short gaps (<= 2 days); longer gaps remain NaN.
    5. Computes annual data quality score (% valid days) and excludes years < 85%.
    """
    if df.empty:
        raise ClimateAnalyzerException("Empty dataset provided for data cleaning.", status_code=422)

    df_work = df.copy()

    # Ensure date column is datetime and indexed
    if "date" in df_work.columns:
        df_work["date"] = pd.to_datetime(df_work["date"])
        df_work = df_work.set_index("date")
    elif not isinstance(df_work.index, pd.DatetimeIndex):
        raise ClimateAnalyzerException("DataFrame must have a 'date' column or DatetimeIndex.", status_code=400)

    # Sort index and drop duplicate dates if any
    df_work = df_work[~df_work.index.duplicated(keep="first")].sort_index()

    # Ensure tmax column exists
    if "tmax" not in df_work.columns:
        raise ClimateAnalyzerException("DataFrame missing required 'tmax' column.", status_code=400)

    # 1. Verify and convert units
    df_work["tmax"] = verify_and_convert_units(df_work["tmax"].astype(float), unit)

    # 2. Reindex to full calendar
    full_calendar = pd.date_range(
        start=f"{start_year}-01-01",
        end=f"{end_year}-12-31",
        freq="D",
        name="date",
    )
    raw_missing_calendar_days = len(full_calendar) - len(df_work.index.intersection(full_calendar))
    df_reindexed = df_work.reindex(full_calendar)

    # Record original raw values
    df_reindexed["original_tmax"] = df_reindexed["tmax"].copy()

    # 3. Detect and mask outliers (< -90°C or > 60°C)
    outlier_mask = (df_reindexed["tmax"] < min_temp_limit) | (df_reindexed["tmax"] > max_temp_limit)
    outliers_detected_count = int(outlier_mask.sum())
    df_reindexed.loc[outlier_mask, "tmax"] = np.nan
    df_reindexed["is_outlier"] = outlier_mask

    # 4. Interpolate short gaps (<= 2 days) on missing days only (outliers remain NaN)
    # Series without outliers for interpolation consideration
    non_outlier_series = df_reindexed["tmax"].copy()
    was_na_before_interp = non_outlier_series.isna() & (~outlier_mask)
    
    # Run gap interpolation on series
    interpolated_series, _ = interpolate_short_gaps_only(df_reindexed["tmax"], max_gap_days=2)
    # Apply interpolation only to non-outlier days
    fillable_mask = was_na_before_interp & interpolated_series.notna() & (~outlier_mask)
    
    df_reindexed.loc[fillable_mask, "tmax"] = interpolated_series.loc[fillable_mask]
    df_reindexed["is_interpolated"] = fillable_mask

    # 5. Annual quality scoring and exclusions
    df_reindexed["year"] = df_reindexed.index.year
    yearly_quality_list: List[YearQuality] = []
    excluded_years: List[int] = []
    warnings: List[str] = []

    for yr in range(start_year, end_year + 1):
        year_mask = df_reindexed["year"] == yr
        year_slice = df_reindexed[year_mask]
        total_days_in_year = len(year_slice)

        if total_days_in_year == 0:
            valid_pct = 0.0
            missing_count = 365
            outlier_count = 0
            filled_count = 0
            is_valid = False
        else:
            valid_days = int(year_slice["tmax"].notna().sum())
            valid_pct = round((valid_days / total_days_in_year) * 100.0, 2)
            missing_count = int(year_slice["original_tmax"].isna().sum())
            outlier_count = int(year_slice["is_outlier"].sum())
            filled_count = int(year_slice["is_interpolated"].sum())
            is_valid = valid_pct >= min_valid_pct

        if not is_valid:
            excluded_years.append(yr)

        yearly_quality_list.append(
            YearQuality(
                year=yr,
                valid_pct=valid_pct,
                missing_days=missing_count,
                short_gaps_filled=filled_count,
                outliers_detected=outlier_count,
                is_valid=is_valid,
            )
        )

    if excluded_years:
        warnings.append(
            f"{len(excluded_years)} year(s) excluded from trend analysis due to insufficient data quality (< {min_valid_pct}% valid days): {excluded_years}"
        )
    if outliers_detected_count > 0:
        warnings.append(f"{outliers_detected_count} physically implausible temperature reading(s) flagged and masked as outliers.")

    qa_report = DataQualityReport(
        total_years=len(yearly_quality_list),
        valid_years=len(yearly_quality_list) - len(excluded_years),
        excluded_years=excluded_years,
        yearly_scores=yearly_quality_list,
        warnings=warnings,
    )

    return df_reindexed, qa_report
