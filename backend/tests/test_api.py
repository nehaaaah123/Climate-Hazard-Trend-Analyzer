"""Integration and validation unit tests for FastAPI endpoints."""

import numpy as np
import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services import open_meteo


@pytest.fixture
def mock_open_meteo(monkeypatch):
    """Mocks Open-Meteo upstream API to return deterministic synthetic temperatures."""
    async def fake_fetch_chunk(grid_lat, grid_lon, start_date, end_date, client=None):
        dates = pd.date_range(start_date, end_date, freq="D")
        n_days = len(dates)
        # Seasonal sinusoidal cycle peaking in May/June
        doy = dates.dayofyear.values
        temps = 28.0 + 10.0 * np.sin(2 * np.pi * (doy - 60) / 365.25)
        # Inject artificial heatwaves in later years to produce measurable events
        for i, dt in enumerate(dates):
            if dt.year >= 2015 and dt.month == 5 and 10 <= dt.day <= 15:
                temps[i] += 8.0  # Spike

        return {
            "latitude": grid_lat,
            "longitude": grid_lon,
            "daily_units": {"temperature_2m_max": "°C"},
            "daily": {
                "time": dates.strftime("%Y-%m-%d").tolist(),
                "temperature_2m_max": [round(float(t), 2) for t in temps],
            },
        }

    monkeypatch.setattr(open_meteo, "fetch_open_meteo_chunk", fake_fetch_chunk)


@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "environment" in data


@pytest.mark.asyncio
async def test_regions_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/regions")
        assert response.status_code == 200
        data = response.json()
        assert "regions" in data
        assert len(data["regions"]) >= 5
        city_names = [r["name"] for r in data["regions"]]
        assert "Delhi" in city_names
        assert "London" in city_names


@pytest.mark.asyncio
async def test_analysis_validation_unsupported_hazard():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/analysis/heatwave",
            params={"lat": 28.6, "lon": 77.2, "hazard_type": "drought"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "drought" in data["message"].lower() or "unsupported" in data["message"].lower()


@pytest.mark.asyncio
async def test_analysis_validation_invalid_bounds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Latitude out of bounds
        resp = await ac.get("/api/v1/analysis/heatwave", params={"lat": 95.0, "lon": 77.2})
        assert resp.status_code == 400

        # Start year > end year
        resp2 = await ac.get(
            "/api/v1/analysis/heatwave",
            params={"lat": 28.6, "lon": 77.2, "start_year": 2020, "end_year": 2010},
        )
        assert resp2.status_code == 400

        # Span > 50 years (e.g. 1960 to 2023 = 64 years)
        resp3 = await ac.get(
            "/api/v1/analysis/heatwave",
            params={"lat": 28.6, "lon": 77.2, "start_year": 1960, "end_year": 2023},
        )
        assert resp3.status_code == 400

        # Percentile out of bounds
        resp4 = await ac.get(
            "/api/v1/analysis/heatwave",
            params={"lat": 28.6, "lon": 77.2, "percentile": 75.0},
        )
        assert resp4.status_code == 400


@pytest.mark.asyncio
async def test_analysis_heatwave_end_to_end_mocked(mock_open_meteo):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/analysis/heatwave",
            params={
                "lat": 28.6139,
                "lon": 77.2090,
                "start_year": 1995,
                "end_year": 2020,
                "percentile": 95.0,
                "min_days": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "region" in data
        assert data["region"]["grid_lat"] == 28.5
        assert data["region"]["grid_lon"] == 77.25

        assert "parameters" in data
        assert data["parameters"]["hazard_type"] == "heatwave"

        assert "baseline_info" in data
        assert "data_quality" in data
        assert "per_year_metrics" in data
        assert len(data["per_year_metrics"]) == (2020 - 1995 + 1)

        assert "rolling_averages" in data
        assert "trend_stats" in data
        assert "ols" in data["trend_stats"]
        assert "theil_sen" in data["trend_stats"]
        assert "mann_kendall" in data["trend_stats"]

        assert "insights" in data
        assert len(data["insights"]) >= 2

        assert "events_summary" in data


@pytest.mark.asyncio
async def test_analysis_events_pagination(mock_open_meteo):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/analysis/heatwave/events",
            params={
                "lat": 28.6139,
                "lon": 77.2090,
                "start_year": 1995,
                "end_year": 2020,
                "page": 1,
                "page_size": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        assert "events" in data
        assert len(data["events"]) <= 2


@pytest.mark.asyncio
async def test_export_csv_and_pdf(mock_open_meteo):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # CSV Export
        csv_resp = await ac.get(
            "/api/v1/export/csv",
            params={"lat": 28.6139, "lon": 77.2090, "start_year": 2000, "end_year": 2010},
        )
        assert csv_resp.status_code == 200
        assert csv_resp.headers["content-type"].startswith("text/csv")
        assert "total_heatwave_days" in csv_resp.text

        # PDF Export
        pdf_resp = await ac.get(
            "/api/v1/export/pdf",
            params={"lat": 28.6139, "lon": 77.2090, "start_year": 2000, "end_year": 2010},
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content.startswith(b"%PDF")

