"""Unit tests for vectorized run-length heatwave event detection."""

import numpy as np
import pandas as pd
import pytest
from app.services.heatwave_detector import compute_yearly_metrics, detect_heatwave_events


def make_constant_thresholds(value: float = 30.0) -> np.ndarray:
    """Helper to return uniform threshold across all 366 days."""
    arr = np.full(367, value, dtype=float)
    return arr


def test_detect_heatwave_exact_duration_filtering():
    """Verify that runs < min_days (e.g. 2 days) are ignored, while >= 3 days are detected."""
    dates = pd.date_range("2020-05-01", "2020-05-10", freq="D")
    # Days:
    # 05-01: 32 (hot)
    # 05-02: 32 (hot) -> 2 days only (ignored for min_days=3)
    # 05-03: 25 (cool)
    # 05-04: 35 (hot)
    # 05-05: 36 (hot)
    # 05-06: 37 (hot) -> exactly 3 days (detected)
    # 05-07..05-10: 25 (cool)
    temps = [32.0, 32.0, 25.0, 35.0, 36.0, 37.0, 25.0, 25.0, 25.0, 25.0]
    df = pd.DataFrame({"tmax": temps}, index=dates)
    thresholds = make_constant_thresholds(30.0)

    events = detect_heatwave_events(df, thresholds, min_days=3)
    assert len(events) == 1
    ev = events[0]
    assert ev.start_date == "2020-05-04"
    assert ev.end_date == "2020-05-06"
    assert ev.duration == 3
    assert ev.peak_temp == 37.0
    # Anomalies: (35-30)=5, (36-30)=6, (37-30)=7 -> mean anomaly = 6.0
    assert pytest.approx(ev.mean_intensity, rel=1e-3) == 6.0


def test_detect_heatwave_spanning_year_boundary():
    """
    Spec Change Requirement 5:
    Run event detection on the continuous multi-year series.
    Attribute each event to its start year.
    Test an event spanning Dec 31 to Jan 2.
    """
    dates = pd.date_range("2021-12-29", "2022-01-05", freq="D")
    # Dec 29: 25
    # Dec 30: 25
    # Dec 31: 35 (hot)
    # Jan 01: 36 (hot)
    # Jan 02: 37 (hot) -> 3-day continuous event crossing year boundary!
    # Jan 03: 25
    # Jan 04: 25
    # Jan 05: 25
    temps = [25.0, 25.0, 35.0, 36.0, 37.0, 25.0, 25.0, 25.0]
    df = pd.DataFrame({"tmax": temps}, index=dates)
    thresholds = make_constant_thresholds(30.0)

    events = detect_heatwave_events(df, thresholds, min_days=3)
    assert len(events) == 1
    ev = events[0]
    assert ev.start_date == "2021-12-31"
    assert ev.end_date == "2022-01-02"
    assert ev.duration == 3
    # Attributed to start year (2021)
    assert ev.start_year == 2021

    # Check annual metrics attribution
    yearly = compute_yearly_metrics(df, events, start_year=2021, end_year=2022)
    m_2021 = next(m for m in yearly if m.year == 2021)
    m_2022 = next(m for m in yearly if m.year == 2022)

    assert m_2021.event_count == 1
    assert m_2021.total_heatwave_days == 3
    assert m_2022.event_count == 0
    assert m_2022.total_heatwave_days == 0


def test_detect_heatwave_nan_gap_interruption():
    """Verify that a NaN gap breaks an event run immediately."""
    dates = pd.date_range("2020-06-01", "2020-06-05", freq="D")
    # 2 hot days, 1 NaN day, 2 hot days -> neither slice reaches 3 days
    temps = [35.0, 35.0, np.nan, 35.0, 35.0]
    df = pd.DataFrame({"tmax": temps}, index=dates)
    thresholds = make_constant_thresholds(30.0)

    events = detect_heatwave_events(df, thresholds, min_days=3)
    assert len(events) == 0
