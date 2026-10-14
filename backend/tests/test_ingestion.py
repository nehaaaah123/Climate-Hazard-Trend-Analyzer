"""Unit tests for coordinate resolution, bounding box centroid, cache refresh policy, and Open-Meteo ingestion."""

from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from app.core.errors import InvalidRegionError
from app.services.open_meteo import (
    group_contiguous_years,
    resolve_coordinates,
    should_refresh_record,
)


def test_resolve_coordinates_point_snapping():
    # Delhi: 28.6139° N, 77.2090° E
    region, grid_lat, grid_lon = resolve_coordinates(lat=28.6139, lon=77.2090)
    assert grid_lat == 28.5
    assert grid_lon == 77.25
    assert region.snapped is True
    assert region.is_bbox is False
    assert region.warning is None


def test_resolve_coordinates_bbox_centroid_and_warning():
    # Bbox: 28.0, 77.0 to 29.0, 78.0 -> centroid: (28.5, 77.5)
    region, grid_lat, grid_lon = resolve_coordinates(bbox="28.0, 77.0, 29.0, 78.0")
    assert grid_lat == 28.5
    assert grid_lon == 77.5
    assert region.is_bbox is True
    assert "analysis results represent the centroid grid cell" in region.warning


def test_resolve_coordinates_bbox_size_limit():
    # Bbox larger than 10 degrees must raise InvalidRegionError
    with pytest.raises(InvalidRegionError):
        resolve_coordinates(bbox="10.0, 70.0, 25.0, 85.0")


def test_resolve_coordinates_invalid_bounds():
    with pytest.raises(InvalidRegionError):
        resolve_coordinates(lat=95.0, lon=77.0)

    with pytest.raises(InvalidRegionError):
        resolve_coordinates(lat=28.0, lon=195.0)


def test_raw_daily_refresh_rule():
    """
    Test requirement:
    - Past years permanent (never refreshed).
    - Current year refetched if fetched_at is older than 24h.
    """
    current_year = datetime.now(timezone.utc).year
    past_year = current_year - 2

    # 1. Past year with very old fetched_at (e.g. 100 days ago) -> False (permanent)
    old_time = datetime.now(timezone.utc) - timedelta(days=100)
    past_doc = {"year": past_year, "fetched_at": old_time}
    assert should_refresh_record(past_doc, current_year) is False

    # 2. Current year fetched 2 hours ago -> False (fresh)
    recent_time = datetime.now(timezone.utc) - timedelta(hours=2)
    fresh_current_doc = {"year": current_year, "fetched_at": recent_time}
    assert should_refresh_record(fresh_current_doc, current_year) is False

    # 3. Current year fetched 25 hours ago (>24h) -> True (refresh required)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
    stale_current_doc = {"year": current_year, "fetched_at": stale_time}
    assert should_refresh_record(stale_current_doc, current_year) is True

    # 4. Current year with missing or invalid fetched_at -> True
    no_time_doc = {"year": current_year, "fetched_at": None}
    assert should_refresh_record(no_time_doc, current_year) is True


def test_group_contiguous_years():
    years = [1991, 1992, 1993, 2000, 2001, 2005]
    spans = group_contiguous_years(years)
    assert spans == [(1991, 1993), (2000, 2001), (2005, 2005)]

    assert group_contiguous_years([]) == []
    assert group_contiguous_years([2020]) == [(2020, 2020)]


@pytest.mark.asyncio
async def test_get_temperature_series_mocked_upstream(monkeypatch):
    """Verify that get_temperature_series correctly fetches and parses upstream data without live DB."""
    from app.services import open_meteo

    called_spans = []

    async def mock_fetch_chunk(grid_lat, grid_lon, start_date, end_date, client=None):
        called_spans.append((start_date, end_date))
        dates = pd.date_range(start_date, end_date, freq="D").strftime("%Y-%m-%d").tolist()
        return {
            "latitude": grid_lat,
            "longitude": grid_lon,
            "daily_units": {"temperature_2m_max": "°C"},
            "daily": {
                "time": dates,
                "temperature_2m_max": [35.0] * len(dates),
            },
        }

    monkeypatch.setattr(open_meteo, "fetch_open_meteo_chunk", mock_fetch_chunk)

    # Request years 1991, 1992 (union with baseline or range)
    df, unit = await open_meteo.get_temperature_series(
        grid_lat=28.5,
        grid_lon=77.25,
        required_years=[1991, 1992],
    )

    assert unit == "°C"
    assert len(df) == 365 + 366  # 1991 (365) + 1992 (leap year 366)
    assert df["tmax"].iloc[0] == 35.0
    assert len(called_spans) == 1
    assert called_spans[0] == ("1991-01-01", "1992-12-31")

