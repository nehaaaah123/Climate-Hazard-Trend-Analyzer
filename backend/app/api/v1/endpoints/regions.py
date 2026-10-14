"""Preset regions endpoint."""

from fastapi import APIRouter
from app.models.schemas import RegionPreset, RegionsResponse

router = APIRouter()

PRESET_REGIONS = [
    RegionPreset(
        name="Delhi",
        country="India",
        lat=28.6139,
        lon=77.2090,
        description="National Capital Territory of India; experiences severe pre-monsoon heatwaves.",
    ),
    RegionPreset(
        name="Mumbai",
        country="India",
        lat=19.0760,
        lon=72.8777,
        description="Coastal megacity in western India with humid subtropical heat characteristics.",
    ),
    RegionPreset(
        name="Chennai",
        country="India",
        lat=13.0827,
        lon=80.2707,
        description="Southern coastal metropolis on the Bay of Bengal; vulnerable to high heat indices.",
    ),
    RegionPreset(
        name="Kolkata",
        country="India",
        lat=22.5726,
        lon=88.3639,
        description="Eastern Indian metropolis in the Ganges delta; frequent high humidity heatwaves.",
    ),
    RegionPreset(
        name="Phoenix",
        country="United States",
        lat=33.4484,
        lon=-112.0740,
        description="Sonoran Desert urban center known for prolonged extreme summer heat anomalies.",
    ),
    RegionPreset(
        name="London",
        country="United Kingdom",
        lat=51.5074,
        lon=-0.1278,
        description="Temperate maritime urban area increasingly recording unprecedented 40°C+ summer peaks.",
    ),
    RegionPreset(
        name="Madrid",
        country="Spain",
        lat=40.4168,
        lon=-3.7038,
        description="Inland Iberian peninsula capital experiencing intensified Mediterranean heatwaves.",
    ),
    RegionPreset(
        name="Cairo",
        country="Egypt",
        lat=30.0444,
        lon=31.2357,
        description="Nile valley metropolis with extreme arid subtropical summer heat.",
    ),
    RegionPreset(
        name="Tokyo",
        country="Japan",
        lat=35.6762,
        lon=139.6503,
        description="Pacific coastal metropolis with severe combined heat and humidity episodes.",
    ),
    RegionPreset(
        name="Sydney",
        country="Australia",
        lat=-33.8688,
        lon=151.2093,
        description="Southern hemisphere coastal metropolis subject to continental hot westerly bursts.",
    ),
]


@router.get("", response_model=RegionsResponse)
async def get_preset_regions() -> RegionsResponse:
    """Returns curated preset cities with verified coordinates and regional descriptions."""
    return RegionsResponse(regions=PRESET_REGIONS)
