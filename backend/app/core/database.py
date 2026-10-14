"""MongoDB client connection management and index initialization."""

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("climate_analyzer.database")


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(cls) -> None:
        """Establish MongoDB connection and create required indexes."""
        if cls.client is not None:
            return
        try:
            logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI} (db: {settings.MONGODB_DB_NAME})")
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=2500,
            )
            cls.db = cls.client[settings.MONGODB_DB_NAME]
            # Quick ping check (non-fatal if offline during local dev without docker)
            await cls.client.admin.command("ping")
            logger.info("MongoDB ping succeeded. Initializing indexes...")
            await cls.init_indexes()
        except Exception as exc:
            logger.warning(f"Could not connect to live MongoDB ({exc}). Running in-memory/mock fallback mode if testing.")
            cls.client = None
            cls.db = None

    @classmethod
    async def init_indexes(cls) -> None:
        """Create unique indexes on raw_daily and analysis_results collections."""
        if cls.db is None:
            return
        try:
            # 1. raw_daily: keyed by (grid_lat, grid_lon, year)
            await cls.db.raw_daily.create_index(
                [("grid_lat", 1), ("grid_lon", 1), ("year", 1)],
                unique=True,
                name="idx_raw_daily_unique_cell_year",
            )
            # 2. analysis_results: keyed by coordinates, query params, and baseline range
            await cls.db.analysis_results.create_index(
                [
                    ("grid_lat", 1),
                    ("grid_lon", 1),
                    ("start_year", 1),
                    ("end_year", 1),
                    ("percentile", 1),
                    ("min_days", 1),
                    ("baseline_start", 1),
                    ("baseline_end", 1),
                ],
                unique=True,
                name="idx_analysis_results_unique_query",
            )
            logger.info("MongoDB unique indexes successfully verified/created.")
        except Exception as exc:
            logger.warning(f"Failed to create MongoDB indexes: {exc}")

    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection pool."""
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed.")


def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Retrieve active database reference."""
    return DatabaseManager.db
