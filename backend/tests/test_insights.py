"""Unit tests for insight generation rules and scientific caveats."""

import pytest
from app.models.schemas import MannKendallStats, OLSStats, TheilSenStats, TrendStats, YearlyMetrics
from app.services.insights import generate_honest_insights


def test_insight_honest_significance_claim():
    """Verify that increased/decreased is only claimed when Mann-Kendall p < 0.05."""
    metrics = [
        YearlyMetrics(
            year=yr, event_count=1, total_heatwave_days=5, max_duration=5, mean_intensity=1.5, peak_temp=35.0
        )
        for yr in range(1990, 2020)
    ]

    # Case A: p = 0.20 (NOT significant)
    stats_not_sig = TrendStats(
        ols=OLSStats(slope_per_decade=1.5, intercept=3.0, r_squared=0.08, p_value=0.20),
        theil_sen=TheilSenStats(slope_per_decade=1.2),
        mann_kendall=MannKendallStats(tau=0.15, p_value=0.20, trend="no trend", statistically_significant=False),
    )
    insights_not_sig = generate_honest_insights(metrics, stats_not_sig, start_year=1990, end_year=2019)
    first_insight = insights_not_sig[0]
    assert "no statistically significant trend detected" in first_insight.lower()
    assert "statistically significant upward trend" not in first_insight.lower()

    # Case B: p = 0.002 (statistically significant)
    stats_sig = TrendStats(
        ols=OLSStats(slope_per_decade=2.5, intercept=3.0, r_squared=0.45, p_value=0.002),
        theil_sen=TheilSenStats(slope_per_decade=2.3),
        mann_kendall=MannKendallStats(tau=0.42, p_value=0.002, trend="increasing", statistically_significant=True),
    )
    insights_sig = generate_honest_insights(metrics, stats_sig, start_year=1990, end_year=2019)
    first_insight_sig = insights_sig[0]
    assert "statistically significant upward trend" in first_insight_sig.lower()


def test_insight_zero_baseline_handling():
    """Verify that a zero baseline does not generate 'infinite %'."""
    # First decade: all 0 heatwave days; Last decade: positive days
    metrics = []
    for yr in range(1990, 2000):
        metrics.append(YearlyMetrics(year=yr, event_count=0, total_heatwave_days=0, max_duration=0, mean_intensity=0.0, peak_temp=30.0))
    for yr in range(2000, 2020):
        metrics.append(YearlyMetrics(year=yr, event_count=2, total_heatwave_days=8, max_duration=4, mean_intensity=2.0, peak_temp=38.0))

    stats = TrendStats(
        ols=OLSStats(slope_per_decade=3.0, intercept=0.0, r_squared=0.6, p_value=0.001),
        theil_sen=TheilSenStats(slope_per_decade=2.8),
        mann_kendall=MannKendallStats(tau=0.6, p_value=0.001, trend="increasing", statistically_significant=True),
    )

    insights = generate_honest_insights(metrics, stats, start_year=1990, end_year=2019)
    joined_text = " ".join(insights).lower()

    assert "infinite" not in joined_text
    assert "increased from none" in joined_text or "0.0 days/year" in joined_text


def test_insight_caveats_for_short_range_and_excluded_years():
    """Verify caveats are present for range < 20 years, excluded data quality years, and single cell."""
    # 10-year range (short)
    metrics = [
        YearlyMetrics(year=yr, event_count=1, total_heatwave_days=4, max_duration=4, mean_intensity=1.0, peak_temp=32.0)
        for yr in range(2010, 2020)
    ]
    stats = TrendStats(
        ols=OLSStats(slope_per_decade=0.5, intercept=2.0, r_squared=0.05, p_value=0.4),
        theil_sen=TheilSenStats(slope_per_decade=0.4),
        mann_kendall=MannKendallStats(tau=0.1, p_value=0.4, trend="no trend", statistically_significant=False),
    )

    insights = generate_honest_insights(
        metrics,
        stats,
        start_year=2010,
        end_year=2019,
        excluded_years=[2014],
        grid_lat=28.5,
        grid_lon=77.25,
    )

    joined = " ".join(insights).lower()
    # 1. Short range caveat
    assert "shorter than the standard 20–30 year" in joined or "shorter than the standard" in joined
    # 2. Excluded years caveat
    assert "excluded from trend calculations due to insufficient data completeness" in joined
    assert "2014" in joined
    # 3. 0.25° ERA5 cell caveat
    assert "single 0.25° era5 grid cell" in joined
