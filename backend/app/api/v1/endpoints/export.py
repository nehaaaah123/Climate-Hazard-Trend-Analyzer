"""Export endpoints for CSV and PDF reports."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, Response
from app.api.v1.endpoints.analysis import execute_heatwave_analysis, validate_analysis_query
from app.core.config import settings
from app.core.limiter import limiter
from app.services.export_service import generate_csv_export, generate_pdf_export

router = APIRouter()


@router.get("/csv")
@limiter.limit(settings.RATE_LIMIT_EXPORT)
async def export_csv(
    request: Request,
    validated: Dict[str, Any] = Depends(validate_analysis_query),
):
    """Generates and downloads a clean CSV data export."""
    analysis_resp, _ = await execute_heatwave_analysis(validated)
    csv_content = generate_csv_export(analysis_resp)

    filename = f"heatwave_analysis_{analysis_resp.region.grid_lat}_{analysis_resp.region.grid_lon}_{analysis_resp.parameters.start_year}_{analysis_resp.parameters.end_year}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
@limiter.limit(settings.RATE_LIMIT_EXPORT)
async def export_pdf(
    request: Request,
    validated: Dict[str, Any] = Depends(validate_analysis_query),
):
    """Generates and downloads a server-rendered PDF report with figures and insights."""
    analysis_resp, _ = await execute_heatwave_analysis(validated)
    pdf_bytes = generate_pdf_export(analysis_resp)

    filename = f"heatwave_report_{analysis_resp.region.grid_lat}_{analysis_resp.region.grid_lon}_{analysis_resp.parameters.start_year}_{analysis_resp.parameters.end_year}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
