"""Synthetic weather series generator fixtures for unit testing."""

from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd


def generate_synthetic_series(
    start_year: int = 1990,
    end_year: int = 2020,
    mean_temp: float = 28.0,
    amplitude: float = 12.0,  # Seasonal oscillation
    trend_deg_per_decade: float = 0.5,
    noise_std: float = 1.5,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates a realistic daily temperature series with seasonal cycle and optional warming trend.
    """
    np.random.seed(seed)
    date_index = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")
    n_days = len(date_index)

    # Days of year for sinusoidal cycle: peak around DOY 150 (late May/early June)
    doy = date_index.dayofyear.values
    seasonal_cycle = amplitude * np.sin(2 * np.pi * (doy - 60) / 365.25)

    # Linear decadal trend
    years_elapsed = (date_index.year - start_year) + (doy / 365.25)
    warming_trend = (trend_deg_per_decade / 10.0) * years_elapsed

    # Stochastic Gaussian noise
    noise = np.random.normal(0, noise_std, n_days)

    tmax = mean_temp + seasonal_cycle + warming_trend + noise
    return pd.DataFrame({"date": date_index, "tmax": np.round(tmax, 2)})


def make_noisy_series_with_issues() -> pd.DataFrame:
    """
    Creates a synthetic series containing known issues for test assertions:
    - Outliers (< -90°C and > 60°C)
    - 1-day and 2-day short gaps (must be filled)
    - 5-day long gap (must NOT be filled)
    - A year (2005) with 50 missing days (exceeds 15% threshold, must be excluded)
    """
    df = generate_synthetic_series(start_year=2000, end_year=2006, seed=123)

    # 1. Outliers
    # Date 2001-06-15 set to 75.0°C (physically implausible)
    df.loc[df["date"] == "2001-06-15", "tmax"] = 75.0
    # Date 2002-01-10 set to -95.0°C (physically implausible)
    df.loc[df["date"] == "2002-01-10", "tmax"] = -95.0

    # 2. Short gaps (1 day: 2003-04-10, 2 days: 2003-05-12 to 2003-05-13)
    df.loc[df["date"] == "2003-04-10", "tmax"] = np.nan
    df.loc[(df["date"] >= "2003-05-12") & (df["date"] <= "2003-05-13"), "tmax"] = np.nan

    # 3. Long gap (5 days: 2004-07-01 to 2004-07-05) -> must stay NaN
    df.loc[(df["date"] >= "2004-07-01") & (df["date"] <= "2004-07-05"), "tmax"] = np.nan

    # 4. Low data quality year (2005): 60 consecutive missing days (>15% missing)
    df.loc[(df["date"] >= "2005-06-01") & (df["date"] <= "2005-07-30"), "tmax"] = np.nan

    return df
