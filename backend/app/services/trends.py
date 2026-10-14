"""Trend analysis engine: OLS regression, Theil-Sen estimator, Mann-Kendall test, and rolling averages."""

import logging
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats
from app.models.schemas import (
    MannKendallStats,
    OLSStats,
    RollingAveragePoint,
    RollingAverages,
    TheilSenStats,
    TrendStats,
    YearlyMetrics,
)

logger = logging.getLogger("climate_analyzer.trends")


def compute_rolling_averages(
    yearly_metrics: List[YearlyMetrics],
    window: int = 5,
) -> RollingAverages:
    """
    Computes a 5-year rolling average series for charting.
    Note: Rolling averages are intended purely for visual smoothing in UI charts,
    and are NEVER used for statistical hypothesis tests or trend slope calculations.
    """
    if not yearly_metrics:
        return RollingAverages(window=window, series=[])

    df = pd.DataFrame([m.model_dump() for m in yearly_metrics])
    df = df.sort_values("year")

    # Rolling average with min_periods=1 to provide smooth visual curve even near bounds
    df["heatwave_days_rolling"] = df["total_heatwave_days"].rolling(window=window, min_periods=1).mean()
    df["event_count_rolling"] = df["event_count"].rolling(window=window, min_periods=1).mean()

    points = []
    for _, row in df.iterrows():
        points.append(
            RollingAveragePoint(
                year=int(row["year"]),
                heatwave_days_rolling_avg=round(float(row["heatwave_days_rolling"]), 2),
                event_count_rolling_avg=round(float(row["event_count_rolling"]), 2),
            )
        )

    return RollingAverages(window=window, series=points)


def compute_trend_statistics(
    yearly_metrics: List[YearlyMetrics],
    excluded_years: Optional[List[int]] = None,
) -> TrendStats:
    """
    Computes rigorous trend statistics on annual heatwave days:
    1. OLS Linear Regression (slope per decade, intercept, R², p-value)
    2. Theil-Sen Robust Estimator (median slope per decade, outlier-resistant)
    3. Mann-Kendall Non-Parametric Trend Test (tau, p-value, trend direction)
    
    CRITICAL STATISTICAL METHODOLOGY NOTE:
    Trend regression (OLS), Theil-Sen estimator, and the Mann-Kendall non-parametric test
    MUST run on raw annual metric values, NEVER on the rolling average.
    Applying rolling averages artificially introduces strong positive serial autocorrelation
    into the time series. This violates the fundamental independence assumption (i.i.d.) of
    the Mann-Kendall test and causes OLS standard errors to be severely underestimated,
    leading to falsely inflated t-statistics and spurious statistical significance.
    """
    excluded_set = set(excluded_years or [])

    # Filter out excluded years to prevent biased trends from incomplete data
    valid_points = [m for m in yearly_metrics if m.year not in excluded_set]

    if len(valid_points) < 3:
        # Not enough data points to compute statistical regression
        return TrendStats(
            ols=OLSStats(slope_per_decade=0.0, intercept=0.0, r_squared=0.0, p_value=1.0),
            theil_sen=TheilSenStats(slope_per_decade=0.0),
            mann_kendall=MannKendallStats(
                tau=0.0,
                p_value=1.0,
                trend="no trend",
                statistically_significant=False,
            ),
        )

    years = np.array([p.year for p in valid_points], dtype=float)
    y_days = np.array([p.total_heatwave_days for p in valid_points], dtype=float)

    # 1. OLS Linear Regression
    ols_res = stats.linregress(years, y_days)
    ols_slope_per_year = ols_res.slope if not np.isnan(ols_res.slope) else 0.0
    ols_slope_per_decade = round(float(ols_slope_per_year * 10.0), 3)
    ols_intercept = round(float(ols_res.intercept), 3)
    ols_r2 = round(float(ols_res.rvalue ** 2), 4)
    ols_p = round(float(ols_res.pvalue), 4)

    # 2. Theil-Sen Robust Estimator
    # Theil-Sen computes the median of slopes between all pairs of points, resistant to single-year anomalies
    ts_res = stats.theilslopes(y_days, years)
    ts_slope_per_year = ts_res.slope if not np.isnan(ts_res.slope) else 0.0
    ts_slope_per_decade = round(float(ts_slope_per_year * 10.0), 3)

    # 3. Mann-Kendall Non-Parametric Test
    try:
        mk_res = mk.original_test(y_days)
        mk_tau = round(float(mk_res.Tau), 4)
        mk_p = round(float(mk_res.p), 4)
        mk_trend = str(mk_res.trend).lower()
        mk_sig = bool(mk_p < 0.05)
    except Exception as exc:
        logger.warning(f"Mann-Kendall test calculation encountered error: {exc}")
        mk_tau = 0.0
        mk_p = 1.0
        mk_trend = "no trend"
        mk_sig = False

    return TrendStats(
        ols=OLSStats(
            slope_per_decade=ols_slope_per_decade,
            intercept=ols_intercept,
            r_squared=ols_r2,
            p_value=ols_p,
        ),
        theil_sen=TheilSenStats(
            slope_per_decade=ts_slope_per_decade,
        ),
        mann_kendall=MannKendallStats(
            tau=mk_tau,
            p_value=mk_p,
            trend=mk_trend,
            statistically_significant=mk_sig,
        ),
    )
