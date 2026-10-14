"""Open-Meteo API ingestion service with grid snapping, retry logic, and MongoDB caching."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
import httpx
import numpy as np
import pandas as pd
from app.core.config import settings
from app.core.database import get_database
from app.core.errors import InvalidRegionError, OpenMeteoError
from app.models.schemas import RegionInfo, snap_coordinate

logger = logging.getLogger("climate_analyzer.open_meteo")


def resolve_coordinates(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    bbox: Optional[str] = None,
) -> Tuple[RegionInfo, float, float]:
    """
    Parses lat/lon or bbox string 'min_lat,min_lon,max_lat,max_lon'.
    Validates limits, snaps coordinates to 0.25° grid, and returns (RegionInfo, grid_lat, grid_lon).
    """
    if bbox and isinstance(bbox, str) and bbox.strip():
        try:
            parts = [float(p.strip()) for p in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox must contain exactly 4 comma-separated numbers.")
            min_lat, min_lon, max_lat, max_lon = parts
        except Exception as e:
            raise InvalidRegionError(f"Invalid bbox format: {e}. Expected 'min_lat,min_lon,max_lat,max_lon'")

        # Range checks
        if not (-90.0 <= min_lat <= max_lat <= 90.0) or not (-180.0 <= min_lon <= max_lon <= 180.0):
            raise InvalidRegionError("Bounding box coordinates out of geographic bounds [-90,90] / [-180,180].")

        # Size check
        lat_size = max_lat - min_lat
        lon_size = max_lon - min_lon
        if lat_size > settings.MAX_BBOX_SIZE or lon_size > settings.MAX_BBOX_SIZE:
            raise InvalidRegionError(
                f"Bounding box {lat_size:.2f}x{lon_size:.2f}° exceeds maximum allowed {settings.MAX_BBOX_SIZE}°."
            )

        # Centroid calculation
        centroid_lat = (min_lat + max_lat) / 2.0
        centroid_lon = (min_lon + max_lon) / 2.0
        grid_lat = snap_coordinate(centroid_lat, settings.GRID_SIZE)
        grid_lon = snap_coordinate(centroid_lon, settings.GRID_SIZE)

        bbox_warning = (
            f"Bounding box request ({min_lat},{min_lon} to {max_lat},{max_lon}): "
            f"analysis results represent the centroid grid cell ({grid_lat}°, {grid_lon}°)."
        )

        region = RegionInfo(
            input_lat=round(centroid_lat, 4),
            input_lon=round(centroid_lon, 4),
            grid_lat=grid_lat,
            grid_lon=grid_lon,
            snapped=True,
            is_bbox=True,
            bbox=[min_lat, min_lon, max_lat, max_lon],
            warning=bbox_warning,
        )
        return region, grid_lat, grid_lon

    if lat is None or lon is None:
        raise InvalidRegionError("Either 'lat' and 'lon' or 'bbox' must be provided.")

    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise InvalidRegionError("Latitude must be in [-90, 90] and longitude in [-180, 180].")

    grid_lat = snap_coordinate(lat, settings.GRID_SIZE)
    grid_lon = snap_coordinate(lon, settings.GRID_SIZE)

    region = RegionInfo(
        input_lat=lat,
        input_lon=lon,
        grid_lat=grid_lat,
        grid_lon=grid_lon,
        snapped=True,
        is_bbox=False,
        bbox=None,
        warning=None,
    )
    return region, grid_lat, grid_lon


def should_refresh_record(record: Dict[str, Any], current_year: int) -> bool:
    """
    Cache policy:
    - Past years (< current_year): permanent, never refresh.
    - Current year (== current_year): refetch if fetched_at is older than 24h.
    """
    record_year = record.get("year")
    if record_year is None:
        return True

    if record_year < current_year:
        return False

    fetched_at = record.get("fetched_at")
    if not fetched_at:
        return True

    if isinstance(fetched_at, str):
        try:
            fetched_at = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError:
            return True

    # Ensure timezone aware UTC
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - fetched_at).total_seconds() / 3600.0
    return age_hours >= settings.RAW_DAILY_CURRENT_YEAR_TTL_HOURS


async def fetch_open_meteo_chunk(
    grid_lat: float,
    grid_lon: float,
    start_date: str,
    end_date: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Fetches historical daily max temperature with exponential backoff for 429/5xx.
    Strictly builds params from validated numbers.
    """
    params = {
        "latitude": f"{grid_lat:.4f}",
        "longitude": f"{grid_lon:.4f}",
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max",
        "timezone": "auto",
    }

    should_close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=settings.OPEN_METEO_TIMEOUT_SECONDS)
        should_close_client = True

    max_retries = settings.OPEN_METEO_MAX_RETRIES
    backoff = 1.0

    try:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(settings.OPEN_METEO_BASE_URL, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if "daily" not in data or "temperature_2m_max" not in data["daily"]:
                        raise OpenMeteoError(
                            "Upstream Open-Meteo returned payload missing daily.temperature_2m_max",
                            details={"response": data},
                        )
                    return data

                if response.status_code in [429, 500, 502, 503, 504]:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                    logger.warning(
                        f"Open-Meteo returned HTTP {response.status_code} on attempt {attempt}/{max_retries}. Backing off {sleep_time}s..."
                    )
                    await asyncio.sleep(sleep_time)
                    backoff *= 2.0
                    continue

                # Client error (e.g. 400)
                raise OpenMeteoError(
                    f"Open-Meteo API returned error {response.status_code}: {response.text}",
                    status_code=502,
                )
            except httpx.RequestError as exc:
                if attempt == max_retries:
                    raise OpenMeteoError(f"Network error contacting Open-Meteo API: {exc}")
                logger.warning(f"Network error on attempt {attempt}/{max_retries}: {exc}. Retrying...")
                await asyncio.sleep(backoff)
                backoff *= 2.0

        raise OpenMeteoError(f"Exhausted {max_retries} retries connecting to Open-Meteo API.")
    finally:
        if should_close_client:
            await client.aclose()


def group_contiguous_years(years: List[int]) -> List[Tuple[int, int]]:
    """Group sorted years into contiguous [start_year, end_year] spans."""
    if not years:
        return []
    sorted_yrs = sorted(list(set(years)))
    spans = []
    start = sorted_yrs[0]
    prev = sorted_yrs[0]

    for yr in sorted_yrs[1:]:
        if yr == prev + 1:
            prev = yr
        else:
            spans.append((start, prev))
            start = yr
            prev = yr
    spans.append((start, prev))
    return spans


async def get_temperature_series(
    grid_lat: float,
    grid_lon: float,
    required_years: List[int],
    http_client: Optional[httpx.AsyncClient] = None,
) -> Tuple[pd.DataFrame, str]:
    """
    Fetches daily max temperatures for the given years from MongoDB cache or Open-Meteo.
    Only missing or stale years are queried upstream.
    Returns (pd.DataFrame with 'date' and 'tmax', unit_string).
    """
    db = get_database()
    current_year = datetime.now(timezone.utc).year
    cached_records: Dict[int, Dict[str, Any]] = {}
    missing_years: Set[int] = set()

    # 1. Check MongoDB cache if database is available
    if db is not None:
        try:
            cursor = db.raw_daily.find(
                {
                    "grid_lat": grid_lat,
                    "grid_lon": grid_lon,
                    "year": {"$in": required_years},
                }
            )
            async for doc in cursor:
                yr = doc["year"]
                if not should_refresh_record(doc, current_year):
                    cached_records[yr] = doc
        except Exception as e:
            logger.warning(f"Error reading raw_daily from MongoDB: {e}. Falling back to upstream fetch.")

    for yr in required_years:
        if yr not in cached_records:
            missing_years.add(yr)

    # 2. Fetch missing years in batched contiguous ranges
    if missing_years:
        logger.info(f"Fetching {len(missing_years)} missing year(s) for ({grid_lat}, {grid_lon}) from Open-Meteo: {sorted(list(missing_years))}")
        spans = group_contiguous_years(list(missing_years))
        for span_start, span_end in spans:
            start_date = f"{span_start}-01-01"
            # If current year, fetch up to yesterday or current date
            if span_end >= current_year:
                end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            else:
                end_date = f"{span_end}-12-31"

            raw_data = await fetch_open_meteo_chunk(
                grid_lat=grid_lat,
                grid_lon=grid_lon,
                start_date=start_date,
                end_date=end_date,
                client=http_client,
            )

            daily = raw_data["daily"]
            time_list = daily.get("time", [])
            tmax_list = daily.get("temperature_2m_max", [])
            unit = raw_data.get("daily_units", {}).get("temperature_2m_max", "°C")

            # Partition into individual years and update cache
            df_batch = pd.DataFrame({"date": time_list, "tmax": tmax_list})
            df_batch["date"] = pd.to_datetime(df_batch["date"])
            df_batch["year"] = df_batch["date"].dt.year

            for yr, group in df_batch.groupby("year"):
                dates_str = group["date"].dt.strftime("%Y-%m-%d").tolist()
                tmax_vals = [None if np.isnan(v) else float(v) for v in group["tmax"].tolist()]
                record = {
                    "grid_lat": grid_lat,
                    "grid_lon": grid_lon,
                    "year": int(yr),
                    "dates": dates_str,
                    "tmax": tmax_vals,
                    "unit": unit,
                    "fetched_at": datetime.now(timezone.utc),
                    "is_current_year": (int(yr) == current_year),
                }
                cached_records[int(yr)] = record

                if db is not None:
                    try:
                        await db.raw_daily.update_one(
                            {"grid_lat": grid_lat, "grid_lon": grid_lon, "year": int(yr)},
                            {"$set": record},
                            upsert=True,
                        )
                    except Exception as exc:
                        logger.warning(f"Failed to upsert raw_daily into MongoDB: {exc}")

    # 3. Assemble combined DataFrame
    all_dates: List[str] = []
    all_tmax: List[Optional[float]] = []
    unit_str = "°C"

    for yr in sorted(required_years):
        rec = cached_records.get(yr)
        if rec:
            unit_str = rec.get("unit", unit_str)
            all_dates.extend(rec.get("dates", []))
            all_tmax.extend(rec.get("tmax", []))

    df_out = pd.DataFrame({"date": pd.to_datetime(all_dates), "tmax": all_tmax})
    return df_out, unit_str
