"""Statistical insight generation with honest communication and scientific caveats."""

from typing import List, Optional
import numpy as np
from app.models.schemas import TrendStats, YearlyMetrics


def generate_honest_insights(
    yearly_metrics: List[YearlyMetrics],
    trend_stats: TrendStats,
    start_year: int,
    end_year: int,
    excluded_years: Optional[List[int]] = None,
    grid_lat: Optional[float] = None,
    grid_lon: Optional[float] = None,
) -> List[str]:
    """
    Generates honest, statistically grounded insights:
    1. Only claims 'increased' or 'decreased' if Mann-Kendall p < 0.05; otherwise states 'no statistically significant trend'.
    2. Compares first-decade vs last-decade averages, gracefully handling zero baselines without stating 'infinite %'.
    3. Adds scientific caveats for ranges < 20 years, excluded low-quality years, and single ERA5 cell representation.
    """
    insights: List[str] = []
    excluded_set = set(excluded_years or [])
    valid_metrics = [m for m in yearly_metrics if m.year not in excluded_set]

    total_valid_years = len(valid_metrics)
    time_span = end_year - start_year + 1

    # --- Insight 1: Mann-Kendall & Linear Trend Evaluation ---
    mk = trend_stats.mann_kendall
    ols = trend_stats.ols
    ts = trend_stats.theil_sen

    if mk.statistically_significant:
        direction = "upward" if ols.slope_per_decade > 0 else "downward"
        sign_str = "+" if ols.slope_per_decade > 0 else ""
        insights.append(
            f"Annual heatwave days exhibit a statistically significant {direction} trend of "
            f"{sign_str}{ols.slope_per_decade:.2f} days per decade between {start_year} and {end_year} "
            f"(Mann-Kendall p = {mk.p_value:.4f}, tau = {mk.tau:.3f}; Theil-Sen robust slope = {sign_str}{ts.slope_per_decade:.2f} days/decade)."
        )
    else:
        sign_str = "+" if ols.slope_per_decade > 0 else ""
        insights.append(
            f"No statistically significant trend detected in annual heatwave days over {start_year}–{end_year} "
            f"(Mann-Kendall p = {mk.p_value:.4f} \u2265 0.05; OLS slope = {sign_str}{ols.slope_per_decade:.2f} days/decade, R\u00b2 = {ols.r_squared:.3f})."
        )

    # --- Insight 2: First-decade vs Last-decade Decadal Comparison ---
    if total_valid_years >= 14:
        # 10-year or equal half comparison
        k = 10 if total_valid_years >= 20 else total_valid_years // 2
        first_slice = valid_metrics[:k]
        last_slice = valid_metrics[-k:]

        d1_start, d1_end = first_slice[0].year, first_slice[-1].year
        d2_start, d2_end = last_slice[0].year, last_slice[-1].year

        mean_first = float(np.mean([m.total_heatwave_days for m in first_slice]))
        mean_last = float(np.mean([m.total_heatwave_days for m in last_slice]))

        if mean_first == 0.0 and mean_last == 0.0:
            insights.append(
                f"Average annual heatwave days remained at 0 in both the baseline decade ({d1_start}–{d1_end}) "
                f"and the recent decade ({d2_start}–{d2_end})."
            )
        elif mean_first == 0.0 and mean_last > 0.0:
            # Zero baseline handled safely: no division by zero or infinite % claim
            insights.append(
                f"Average annual heatwave days increased from none (0.0 days/year) in the initial decade ({d1_start}–{d1_end}) "
                f"to {mean_last:.1f} days/year in the recent decade ({d2_start}–{d2_end})."
            )
        else:
            pct_change = ((mean_last - mean_first) / mean_first) * 100.0
            sign_pct = "+" if pct_change > 0 else ""
            insights.append(
                f"Average annual heatwave days shifted from {mean_first:.1f} days/year ({d1_start}–{d1_end}) "
                f"to {mean_last:.1f} days/year ({d2_start}–{d2_end}) ({sign_pct}{pct_change:.1f}% change)."
            )

    # --- Insight 3: Scientific Caveats ---
    if time_span < 20:
        insights.append(
            f"Caveat: The requested analysis period ({time_span} years) is shorter than the standard 20–30 year "
            f"climatological baseline window. Trends over short time spans are sensitive to natural interannual variability."
        )

    if excluded_years and len(excluded_years) > 0:
        insights.append(
            f"Caveat: {len(excluded_years)} year(s) were excluded from trend calculations due to insufficient data completeness "
            f"(< 85% valid days): {excluded_years}."
        )

    cell_coord = f"({grid_lat:.2f}°, {grid_lon:.2f}°)" if (grid_lat is not None and grid_lon is not None) else "this grid point"
    insights.append(
        f"Caveat: Reanalysis data represents a single 0.25° ERA5 grid cell {cell_coord}. "
        f"Microclimate factors such as urban heat island (UHI) intensity or complex topography may differ from gridded reanalysis."
    )

    return insights
