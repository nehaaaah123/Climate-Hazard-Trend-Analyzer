"""Export service for CSV and PDF reports."""

import io
from datetime import datetime
from typing import Tuple
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive background backend
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.schemas import AnalysisResponse


def generate_csv_export(analysis: AnalysisResponse) -> str:
    """Generates clean CSV text containing yearly metrics and trend summary."""
    output = io.StringIO()

    # Section 1: Metadata Header
    output.write("# Climate Hazard Trend Analyzer - Heatwave Analysis Export\n")
    output.write(f"# Generated: {analysis.computed_at}\n")
    output.write(f"# Region Grid Coordinates: {analysis.region.grid_lat}N, {analysis.region.grid_lon}E\n")
    output.write(f"# Analysis Period: {analysis.parameters.start_year} - {analysis.parameters.end_year}\n")
    output.write(f"# Baseline Climatology Period: {analysis.baseline_info.reference_period}\n")
    output.write(f"# Percentile Threshold: {analysis.parameters.percentile}th\n")
    output.write(f"# Min Consecutive Days: {analysis.parameters.min_days} days\n")
    output.write(f"# OLS Slope Per Decade: {analysis.trend_stats.ols.slope_per_decade} days/decade (p={analysis.trend_stats.ols.p_value})\n")
    output.write(f"# Theil-Sen Slope Per Decade: {analysis.trend_stats.theil_sen.slope_per_decade} days/decade\n")
    output.write(f"# Mann-Kendall Tau: {analysis.trend_stats.mann_kendall.tau} (p={analysis.trend_stats.mann_kendall.p_value}, trend={analysis.trend_stats.mann_kendall.trend})\n")
    output.write("#\n")

    # Section 2: Yearly Metrics Data
    rows = []
    for m in analysis.per_year_metrics:
        # Check rolling avg if present
        rolling_pt = next((pt for pt in analysis.rolling_averages.series if pt.year == m.year), None)
        rolling_days = rolling_pt.heatwave_days_rolling_avg if rolling_pt else ""
        rolling_events = rolling_pt.event_count_rolling_avg if rolling_pt else ""

        rows.append({
            "year": m.year,
            "total_heatwave_days": m.total_heatwave_days,
            "event_count": m.event_count,
            "max_duration_days": m.max_duration,
            "mean_intensity_deg_c": m.mean_intensity,
            "peak_temp_deg_c": m.peak_temp,
            "heatwave_days_5yr_rolling_avg": rolling_days,
            "event_count_5yr_rolling_avg": rolling_events,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
    return output.getvalue()


def generate_pdf_export(analysis: AnalysisResponse) -> bytes:
    """Generates server-side PDF report containing summary stats, rendered matplotlib chart, and insights."""
    # 1. Render Matplotlib Chart to In-Memory Buffer
    plt.figure(figsize=(7.5, 3.2), dpi=200)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    years = [m.year for m in analysis.per_year_metrics]
    days = [m.total_heatwave_days for m in analysis.per_year_metrics]

    plt.bar(years, days, color="#ef4444", alpha=0.7, label="Annual Heatwave Days", width=0.6)

    # 5-yr rolling average
    rolling_pts = {pt.year: pt.heatwave_days_rolling_avg for pt in analysis.rolling_averages.series}
    rolling_y = [rolling_pts.get(yr) for yr in years]
    plt.plot(years, rolling_y, color="#0284c7", linewidth=2, label="5-Yr Rolling Avg")

    # OLS trend line
    ols = analysis.trend_stats.ols
    if ols and len(years) > 1:
        slope_yr = ols.slope_per_decade / 10.0
        reg_y = [max(0, slope_yr * yr + ols.intercept) for yr in years]
        plt.plot(years, reg_y, color="#f59e0b", linestyle="--", linewidth=1.8, label=f"OLS Trend ({ols.slope_per_decade:+.2f} d/dec)")

    plt.title(f"Heatwave Days Trend ({analysis.region.grid_lat}°N, {analysis.region.grid_lon}°E)", fontsize=11, fontweight="bold", pad=8)
    plt.xlabel("Year", fontsize=9)
    plt.ylabel("Days per Year", fontsize=9)
    plt.legend(loc="upper left", fontsize=8)
    plt.tight_layout()

    chart_buf = io.BytesIO()
    plt.savefig(chart_buf, format="png")
    plt.close()
    chart_buf.seek(0)

    # 2. Build PDF Document with ReportLab
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    sub_style = ParagraphStyle(
        "ReportSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4,
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("Climate Hazard Trend Report: Heatwave Climatology", title_style))
    story.append(Paragraph(
        f"Location: <b>{analysis.region.grid_lat}°N, {analysis.region.grid_lon}°E</b> (ERA5 0.25° grid) | "
        f"Period: <b>{analysis.parameters.start_year}–{analysis.parameters.end_year}</b> | "
        f"Generated: {analysis.computed_at[:10]}",
        sub_style,
    ))

    # Summary Statistics Table
    ols = analysis.trend_stats.ols
    ts = analysis.trend_stats.theil_sen
    mk = analysis.trend_stats.mann_kendall

    table_data = [
        ["Decadal Trend Rate (OLS)", f"{ols.slope_per_decade:+.2f} days/decade (p={ols.p_value:.4f}, R²={ols.r_squared:.3f})"],
        ["Theil-Sen Robust Slope", f"{ts.slope_per_decade:+.2f} days/decade"],
        ["Mann-Kendall Test", f"Tau = {mk.tau:.3f}, p = {mk.p_value:.4f} ({mk.trend.upper()})"],
        ["Statistical Significance", "YES (p < 0.05)" if mk.statistically_significant else "NO (p >= 0.05)"],
        ["Data Completeness", f"{analysis.data_quality.valid_years} / {analysis.data_quality.total_years} valid years (85% threshold)"],
    ]
    t = Table(table_data, colWidths=[180, 360])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Server-Side Matplotlib Chart
    story.append(RLImage(chart_buf, width=540, height=230))
    story.append(Spacer(1, 10))

    # Insights & Caveats Section
    story.append(Paragraph("Key Findings & Scientific Insights", section_style))
    for insight in analysis.insights:
        story.append(Paragraph(f"• {insight}", body_style))

    # Top Heatwave Events Table
    if analysis.events_summary.top_events:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Top Severe Heatwave Events", section_style))
        ev_data = [["Rank", "Start Date", "End Date", "Duration", "Peak Temp", "Mean Anomaly"]]
        for idx, ev in enumerate(analysis.events_summary.top_events[:5]):
            ev_data.append([
                str(idx + 1),
                ev.start_date,
                ev.end_date,
                f"{ev.duration} days",
                f"{ev.peak_temp:.1f} °C",
                f"+{ev.mean_intensity:.2f} °C",
            ])
        ev_table = Table(ev_data, colWidths=[40, 100, 100, 80, 100, 120])
        ev_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(ev_table)

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
