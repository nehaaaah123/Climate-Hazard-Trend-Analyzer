"""Generic and domain-specific error handlers."""

import logging
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("climate_analyzer.errors")


class ClimateAnalyzerException(Exception):
    """Base domain exception."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class InvalidRegionError(ClimateAnalyzerException):
    """Raised when coordinates or bounding box are invalid."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class OpenMeteoError(ClimateAnalyzerException):
    """Raised when upstream Open-Meteo API fails or returns invalid response."""

    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY, details: Dict[str, Any] = None):
        super().__init__(message, status_code=status_code, details=details)


class DataQualityError(ClimateAnalyzerException):
    """Raised when data quality issues prevent analysis."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform JSON error handlers on the FastAPI application."""

    @app.exception_handler(ClimateAnalyzerException)
    async def domain_exception_handler(request: Request, exc: ClimateAnalyzerException) -> JSONResponse:
        logger.warning(f"Domain exception on {request.url.path}: {exc.message} (details: {exc.details})")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info(f"Validation error on {request.url.path}: {exc.errors()}")
        clean_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            clean_errors.append({"field": loc, "issue": err.get("msg")})
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "ValidationError",
                "message": "Invalid request parameters.",
                "details": {"validation_errors": clean_errors},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.info(f"HTTP exception {exc.status_code} on {request.url.path}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": str(exc.detail),
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Structured log with full stack trace internally, but safe generic message to client
        logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected server error occurred. Please try again later.",
                "details": {},
            },
        )
