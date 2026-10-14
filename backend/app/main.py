"""FastAPI Application entrypoint with security middlewares, rate limiting, and lifespans."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import DatabaseManager
from app.core.errors import register_error_handlers
from app.core.limiter import limiter
from app.core.logging import setup_logging

# Initialize structured logging
setup_logging()
logger = logging.getLogger("climate_analyzer.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database connection pool."""
    logger.info("Starting up Climate Hazard Trend Analyzer Backend...")
    await DatabaseManager.connect()
    yield
    logger.info("Shutting down backend and closing database connections...")
    await DatabaseManager.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Climate Hazard Trend Analyzer: ERA5 historical daily temperature and heatwave climatology API.",
    version="1.0.0",
    lifespan=lifespan,
)

# 1. Attach rate limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return structured 429 response with Retry-After header."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "RateLimitExceeded",
            "message": "Too many requests. Please slow down and try again later.",
            "details": {"retry_after": "60s"},
        },
        headers={"Retry-After": "60"},
    )


# 2. Register domain & validation error handlers
register_error_handlers(app)

# 3. Add GZip Middleware (compress payloads > 1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 5. Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["System"])
async def health_check():
    """System health verification endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
