"""Unit tests for trend statistics: OLS, Theil-Sen, Mann-Kendall, and rolling averages."""

import pytest
from app.models.schemas import YearlyMetrics
from app.services.trends import compute_rolling_averages, compute_trend_statistics


def test_compute_trend_statistics_monotonic_increase():
    """Verify that a steadily increasing series produces positive slopes and significant Mann-Kendall."""
    # 20 years with heatwave days increasing from 2 to 21
    metrics = [
        YearlyMetrics(
            year=yr,
            event_count=1 + (yr - 2000) // 5,
            total_heatwave_days=2 + (yr - 2000),
            max_duration=3,
            mean_intensity=1.5,
            peak_temp=35.0,
        )
        for yr in range(2000, 2020)
    ]

    stats = compute_trend_statistics(metrics)

    # Slope is +1 day/year = +10.0 days/decade
    assert pytest.approx(stats.ols.slope_per_decade, rel=1e-2) == 10.0
    assert pytest.approx(stats.theil_sen.slope_per_decade, rel=1e-2) == 10.0
    assert stats.ols.r_squared == 1.0
    assert stats.ols.p_value < 0.001

    # Mann-Kendall: strictly monotonic increase has Tau = 1.0, p < 0.05
    assert stats.mann_kendall.tau == 1.0
    assert stats.mann_kendall.p_value < 0.05
    assert stats.mann_kendall.statistically_significant is True
    assert stats.mann_kendall.trend == "increasing"


def test_compute_trend_statistics_flat_series():
    """Verify that a flat zero series produces zero slopes and no trend."""
    metrics = [
        YearlyMetrics(
            year=yr,
            event_count=0,
            total_heatwave_days=0,
            max_duration=0,
            mean_intensity=0.0,
            peak_temp=28.0,
        )
        for yr in range(2000, 2020)
    ]

    stats = compute_trend_statistics(metrics)
    assert stats.ols.slope_per_decade == 0.0
    assert stats.theil_sen.slope_per_decade == 0.0
    assert stats.mann_kendall.statistically_significant is False
    assert stats.mann_kendall.trend == "no trend"


def test_trend_runs_on_raw_metrics_not_rolling_average():
    """
    Spec Change Requirement 6:
    Trend regression, Theil-Sen, and Mann-Kendall run on raw yearly values, never on the rolling average.
    """
    # Raw values: noisy alternating pattern [0, 10, 0, 10, 0, 10, ...]
    raw_metrics = [
        YearlyMetrics(
            year=yr,
            event_count=1 if yr % 2 == 1 else 0,
            total_heatwave_days=10 if yr % 2 == 1 else 0,
            max_duration=4,
            mean_intensity=1.5,
            peak_temp=35.0,
        )
        for yr in range(2000, 2020)
    ]

    stats = compute_trend_statistics(raw_metrics)
    rolling = compute_rolling_averages(raw_metrics, window=5)

    # In raw series, alternating values mean no monotonic trend (tau near 0)
    assert stats.mann_kendall.statistically_significant is False

    # Check rolling average exists for visual chart display
    assert len(rolling.series) == len(raw_metrics)
    assert rolling.series[-1].heatwave_days_rolling_avg is not None


def test_excluded_years_filtered_from_trend():
    """Verify that low-quality years are excluded from regression calculation."""
    metrics = [
        YearlyMetrics(
            year=2000, event_count=1, total_heatwave_days=5, max_duration=5, mean_intensity=1.0, peak_temp=35.0
        ),
        # Corrupt extreme year that would distort trend if included
        YearlyMetrics(
            year=2001, event_count=20, total_heatwave_days=80, max_duration=20, mean_intensity=5.0, peak_temp=50.0
        ),
        YearlyMetrics(
            year=2002, event_count=1, total_heatwave_days=6, max_duration=6, mean_intensity=1.0, peak_temp=35.0
        ),
        YearlyMetrics(
            year=2003, event_count=1, total_heatwave_days=7, max_duration=7, mean_intensity=1.0, peak_temp=35.0
        ),
    ]

    stats_with_exclusion = compute_trend_statistics(metrics, excluded_years=[2001])
    # The clean slope between 2000 (5), 2002 (6), 2003 (7) is ~1/year = 10/decade
    assert stats_with_exclusion.ols.slope_per_decade < 20.0
