"""Unit tests for time series cleaning, unit conversion, outlier detection, and data quality scoring."""

import numpy as np
import pandas as pd
import pytest
from app.core.errors import ClimateAnalyzerException
from app.services.cleaning import (
    clean_series,
    interpolate_short_gaps_only,
    verify_and_convert_units,
)
from tests.fixtures.synthetic_series import generate_synthetic_series, make_noisy_series_with_issues


def test_verify_and_convert_units_celsius():
    s = pd.Series([20.0, 30.0, 40.0])
    res = verify_and_convert_units(s, "°C")
    pd.testing.assert_series_equal(res, s)

    res_lower = verify_and_convert_units(s, "celsius")
    pd.testing.assert_series_equal(res_lower, s)


def test_verify_and_convert_units_fahrenheit():
    # 32°F = 0°C, 212°F = 100°C
    s_f = pd.Series([32.0, 212.0])
    res_c = verify_and_convert_units(s_f, "°F")
    assert pytest.approx(res_c.iloc[0], rel=1e-3) == 0.0
    assert pytest.approx(res_c.iloc[1], rel=1e-3) == 100.0


def test_verify_and_convert_units_kelvin():
    # 273.15 K = 0°C, 373.15 K = 100°C
    s_k = pd.Series([273.15, 373.15])
    res_c = verify_and_convert_units(s_k, "K")
    assert pytest.approx(res_c.iloc[0], rel=1e-3) == 0.0
    assert pytest.approx(res_c.iloc[1], rel=1e-3) == 100.0


def test_verify_and_convert_units_invalid():
    s = pd.Series([20.0, 30.0])
    with pytest.raises(ClimateAnalyzerException):
        verify_and_convert_units(s, "InvalidUnit")


def test_interpolate_short_gaps_only():
    # Index with 1-day gap, 2-day gap, and 3-day gap
    # Indices: 0: 10, 1: NaN (1 day), 2: 12, 3: NaN, 4: NaN (2 days), 5: 15, 6: NaN, 7: NaN, 8: NaN (3 days), 9: 20
    series = pd.Series([10.0, np.nan, 12.0, np.nan, np.nan, 15.0, np.nan, np.nan, np.nan, 20.0])
    cleaned, filled_count = interpolate_short_gaps_only(series, max_gap_days=2)

    # 1-day gap at index 1 should be filled: (10 + 12)/2 = 11.0
    assert cleaned.iloc[1] == 11.0

    # 2-day gap at indices 3, 4 should be filled: 12.0 -> 13.0 -> 14.0 -> 15.0
    assert pytest.approx(cleaned.iloc[3], rel=1e-3) == 13.0
    assert pytest.approx(cleaned.iloc[4], rel=1e-3) == 14.0

    # 3-day gap at indices 6, 7, 8 MUST remain NaN!
    assert pd.isna(cleaned.iloc[6])
    assert pd.isna(cleaned.iloc[7])
    assert pd.isna(cleaned.iloc[8])

    # Exactly 3 days were filled (1 + 2)
    assert filled_count == 3


def test_clean_series_full_pipeline_with_noisy_data():
    df_noisy = make_noisy_series_with_issues()
    cleaned_df, qa_report = clean_series(df_noisy, start_year=2000, end_year=2006, unit="°C")

    # 1. Check full calendar reindexing
    expected_days = (pd.to_datetime("2006-12-31") - pd.to_datetime("2000-01-01")).days + 1
    assert len(cleaned_df) == expected_days

    # 2. Check outlier detection
    # Date 2001-06-15 had 75°C -> must be NaN in tmax and flagged as outlier
    assert pd.isna(cleaned_df.loc["2001-06-15", "tmax"])
    assert cleaned_df.loc["2001-06-15", "is_outlier"]

    # Date 2002-01-10 had -95°C -> must be NaN and flagged as outlier
    assert pd.isna(cleaned_df.loc["2002-01-10", "tmax"])
    assert cleaned_df.loc["2002-01-10", "is_outlier"]

    # 3. Check short gap fill
    # 2003-04-10 (1 day gap) must be filled
    assert pd.notna(cleaned_df.loc["2003-04-10", "tmax"])
    assert cleaned_df.loc["2003-04-10", "is_interpolated"]

    # 2003-05-12 and 2003-05-13 (2 day gap) must be filled
    assert pd.notna(cleaned_df.loc["2003-05-12", "tmax"])
    assert pd.notna(cleaned_df.loc["2003-05-13", "tmax"])

    # 4. Check long gap stays NaN
    # 2004-07-01 to 2004-07-05 (5 days gap) must remain NaN
    for date_str in ["2004-07-01", "2004-07-02", "2004-07-03", "2004-07-04", "2004-07-05"]:
        assert pd.isna(cleaned_df.loc[date_str, "tmax"])

    # 5. Check data quality exclusion
    # Year 2005 had 60 missing days (valid % < 85%) -> must be in excluded_years
    assert 2005 in qa_report.excluded_years
    year_2005_score = next(y for y in qa_report.yearly_scores if y.year == 2005)
    assert not year_2005_score.is_valid
    assert year_2005_score.valid_pct < 85.0

    # Clean years should be valid
    year_2000_score = next(y for y in qa_report.yearly_scores if y.year == 2000)
    assert year_2000_score.is_valid
    assert year_2000_score.valid_pct == 100.0


def test_clean_series_empty_dataframe():
    with pytest.raises(ClimateAnalyzerException):
        clean_series(pd.DataFrame(), start_year=2000, end_year=2005)
