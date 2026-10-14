"""Pytest global fixtures and configuration."""

import asyncio
from datetime import datetime
import pytest
import pandas as pd
from tests.fixtures.synthetic_series import generate_synthetic_series, make_noisy_series_with_issues


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def synthetic_baseline_df() -> pd.DataFrame:
    """Standard 1991-2020 synthetic daily temperature series."""
    return generate_synthetic_series(start_year=1991, end_year=2020, seed=42)


@pytest.fixture
def synthetic_noisy_df() -> pd.DataFrame:
    """Synthetic series with injected outliers, short gaps, long gaps, and a bad year."""
    return make_noisy_series_with_issues()
