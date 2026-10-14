"""API v1 router aggregator."""

from fastapi import APIRouter
from app.api.v1.endpoints import analysis, export, regions

api_router = APIRouter()
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(regions.router, prefix="/regions", tags=["Regions"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])
