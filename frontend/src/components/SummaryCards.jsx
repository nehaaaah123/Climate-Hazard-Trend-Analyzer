import React from 'react';
import { TrendingUp, CheckCircle, AlertTriangle, MapPin, Database, Award } from 'lucide-react';

export default function SummaryCards({ analysisData }) {
  if (!analysisData) return null;

  const {
    region,
    parameters,
    data_quality,
    trend_stats,
    insights = [],
    cached,
    computed_at,
  } = analysisData;

  const ols = trend_stats?.ols || {};
  const ts = trend_stats?.theil_sen || {};
  const mk = trend_stats?.mann_kendall || {};

  const slopeStr = ols.slope_per_decade !== undefined
    ? `${ols.slope_per_decade > 0 ? '+' : ''}${ols.slope_per_decade.toFixed(2)} days/decade`
    : '--';

  const tsSlopeStr = ts.slope_per_decade !== undefined
    ? `${ts.slope_per_decade > 0 ? '+' : ''}${ts.slope_per_decade.toFixed(2)} days/decade`
    : '--';

  const isMkSig = mk.statistically_significant;

  return (
    <>
      <div className="summary-grid">
        {/* Card 1: Decadal Trend Slope */}
        <div className="summary-card card-trend">
          <div className="card-header-sm">
            <TrendingUp size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            Decadal Trend Rate
          </div>
          <div className="card-value-lg" style={{ color: ols.slope_per_decade > 0 ? '#ef4444' : '#38bdf8' }}>
            {slopeStr}
          </div>
          <div className="card-subtext">
            OLS Linear Regression (R² = {ols.r_squared !== undefined ? ols.r_squared.toFixed(3) : '--'}, p = {ols.p_value !== undefined ? ols.p_value.toFixed(4) : '--'})<br />
            Theil-Sen Robust Slope: <strong>{tsSlopeStr}</strong>
          </div>
        </div>

        {/* Card 2: Mann-Kendall Significance */}
        <div className="summary-card card-mk">
          <div className="card-header-sm">
            <Award size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            Mann-Kendall Trend Test
          </div>
          <div className="card-value-lg">
            {isMkSig ? (
              <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle size={24} /> Significant
              </span>
            ) : (
              <span style={{ color: '#94a3b8', fontSize: '1.4rem' }}>
                No Significant Trend
              </span>
            )}
          </div>
          <div className="card-subtext">
            Kendall's Tau: <strong>{mk.tau !== undefined ? mk.tau.toFixed(3) : '--'}</strong> | p-value: <strong>{mk.p_value !== undefined ? mk.p_value.toFixed(4) : '--'}</strong><br />
            Trend Direction: <strong style={{ textTransform: 'capitalize' }}>{mk.trend || 'no trend'}</strong>
          </div>
        </div>

        {/* Card 3: Data Quality & Exclusions */}
        <div className="summary-card card-quality">
          <div className="card-header-sm">
            <AlertTriangle size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            Data Quality & Completeness
          </div>
          <div className="card-value-lg" style={{ color: data_quality?.excluded_years?.length > 0 ? '#f59e0b' : '#10b981' }}>
            {data_quality?.valid_years} / {data_quality?.total_years} yrs
          </div>
          <div className="card-subtext">
            {data_quality?.excluded_years?.length > 0 ? (
              <span style={{ color: '#fbbf24' }}>
                {data_quality.excluded_years.length} year(s) excluded (&lt; 85% valid days): {data_quality.excluded_years.join(', ')}
              </span>
            ) : (
              <span>All requested years met the 85% completeness threshold.</span>
            )}
          </div>
        </div>

        {/* Card 4: Grid Cell & Cache Status */}
        <div className="summary-card card-region">
          <div className="card-header-sm">
            <MapPin size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            ERA5 Reanalysis Grid Cell
          </div>
          <div className="card-value-lg" style={{ fontSize: '1.4rem', color: '#f8fafc' }}>
            {region.grid_lat.toFixed(2)}°N, {region.grid_lon.toFixed(2)}°E
          </div>
          <div className="card-subtext" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
            <span>
              {region.is_bbox ? 'Bounding Box Centroid' : '0.25° Snapped Cell'}
            </span>
            <span className="badge-tag" style={{ color: cached ? '#10b981' : '#38bdf8' }}>
              <Database size={10} style={{ display: 'inline', marginRight: 3 }} />
              {cached ? 'Cache Hit' : 'Computed Fresh'}
            </span>
          </div>
        </div>
      </div>

      {/* Insights Section */}
      {insights.length > 0 && (
        <div className="insights-panel">
          <h2 className="insights-title">
            <Award size={18} color="#ef4444" />
            Key Findings & Statistical Insights
          </h2>
          <div>
            {insights.map((insight, idx) => {
              const isCaveat = insight.toLowerCase().startsWith('caveat:');
              return (
                <div key={idx} className={`insight-item ${isCaveat ? 'insight-caveat' : ''}`}>
                  {insight}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
