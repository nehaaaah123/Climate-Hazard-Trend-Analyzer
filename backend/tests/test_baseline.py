"""Unit tests for baseline climatology computation and 366-day calendar mapping."""

import numpy as np
import pandas as pd
import pytest
from app.services.baseline import compute_baseline_thresholds, map_date_to_doy366
from tests.fixtures.synthetic_series import generate_synthetic_series


def test_map_date_to_doy366_consistency():
    """Verify that calendar dates align to identical indices in leap and non-leap years."""
    # 2020 is a leap year; 2021 is a non-leap year
    dates = pd.to_datetime([
        "2020-01-01", "2021-01-01",  # Jan 1 -> 1
        "2020-02-28", "2021-02-28",  # Feb 28 -> 59
        "2020-02-29",                # Feb 29 -> 60
        "2020-03-01", "2021-03-01",  # Mar 1 -> 61
        "2020-07-04", "2021-07-04",  # Jul 4 -> same index
        "2020-12-31", "2021-12-31",  # Dec 31 -> 366
    ])
    doy366 = map_date_to_doy366(pd.Series(dates)).values

    assert doy366[0] == 1 and doy366[1] == 1
    assert doy366[2] == 59 and doy366[3] == 59
    assert doy366[4] == 60  # Feb 29 leap day
    assert doy366[5] == 61 and doy366[6] == 61
    assert doy366[7] == doy366[8]  # Jul 4 identical
    assert doy366[9] == 366 and doy366[10] == 366  # Dec 31 identical


def test_baseline_threshold_shape_and_feb29_interpolation():
    """Verify that thresholds are computed for 1..366 and Feb 29 is interpolated between Feb 28 and Mar 1."""
    df = generate_synthetic_series(start_year=1991, end_year=2020, seed=42)
    thresholds, baseline_info = compute_baseline_thresholds(
        cleaned_df=df,
        percentile=95.0,
        baseline_start=1991,
        baseline_end=2020,
        window_days=15,
    )

    assert len(thresholds) == 367
    assert baseline_info.years_used == 30
    assert not baseline_info.is_fallback

    # Valid non-NaN numbers for all calendar days
    for d in range(1, 367):
        assert not np.isnan(thresholds[d]), f"DOY {d} threshold should not be NaN"

    # Crucial spec requirement 1: For Feb 29 (DOY 60), interpolate between Feb 28 (DOY 59) and Mar 1 (DOY 61)
    expected_feb29 = (thresholds[59] + thresholds[61]) / 2.0
    assert pytest.approx(thresholds[60], abs=1e-5) == expected_feb29


def test_baseline_fallback_on_partial_data():
    """Verify fallback flag when baseline years are incomplete."""
    df_short = generate_synthetic_series(start_year=2000, end_year=2010, seed=42)
    thresholds, baseline_info = compute_baseline_thresholds(
        cleaned_df=df_short,
        percentile=95.0,
        baseline_start=1991,
        baseline_end=2020,
    )

    assert baseline_info.is_fallback is True
    assert baseline_info.years_used == 11
    assert "unavailable" in baseline_info.note.lower() or "partially available" in baseline_info.note.lower()
