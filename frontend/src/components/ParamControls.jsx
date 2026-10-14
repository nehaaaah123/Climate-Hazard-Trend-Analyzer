import React, { useState } from 'react';
import { Sliders, ChevronDown, ChevronUp, Play, Calendar } from 'lucide-react';

export default function ParamControls({
  hazard,
  onHazardChange,
  startYear,
  onStartYearChange,
  endYear,
  onEndYearChange,
  percentile,
  onPercentileChange,
  minDays,
  onMinDaysChange,
  onRunAnalysis,
  isLoading,
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const currentYear = new Date().getFullYear();
  const maxYear = currentYear - 1;

  const yearSpan = (parseInt(endYear) || 0) - (parseInt(startYear) || 0) + 1;
  const isSpanInvalid = yearSpan < 1 || yearSpan > 50;

  return (
    <>
      <div className="form-group">
        <label className="form-label" htmlFor="hazard-select">Climate Hazard</label>
        <select
          id="hazard-select"
          className="form-select"
          value={hazard}
          onChange={(e) => onHazardChange(e.target.value)}
        >
          <option value="heatwave">Heatwave (Historical Daily Tmax)</option>
          <option value="drought" disabled>Drought (SPEI) — Coming Soon</option>
          <option value="rainfall" disabled>Extreme Rainfall (R95p) — Coming Soon</option>
          <option value="wildfire" disabled>Fire Weather Index (FWI) — Coming Soon</option>
        </select>
        <span className="form-hint">ERA5 2m maximum temperature anomaly</span>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="start-year">
          <Calendar size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
          Start Year
        </label>
        <input
          id="start-year"
          type="number"
          min="1950"
          max={endYear || maxYear}
          className="form-control"
          value={startYear}
          onChange={(e) => onStartYearChange(e.target.value)}
        />
        <span className="form-hint">Min: 1950</span>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="end-year">
          <Calendar size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
          End Year
        </label>
        <input
          id="end-year"
          type="number"
          min={startYear || 1950}
          max={maxYear}
          className="form-control"
          value={endYear}
          onChange={(e) => onEndYearChange(e.target.value)}
        />
        <span className="form-hint">
          Span: <strong>{yearSpan} yrs</strong> {isSpanInvalid && <span style={{ color: '#f87171' }}>(Max 50)</span>}
        </span>
      </div>

      <div className="form-group">
        <button
          type="button"
          className="btn-primary"
          onClick={onRunAnalysis}
          disabled={isLoading || isSpanInvalid}
          aria-label="Analyze Climate Trends"
        >
          {isLoading ? (
            <>
              <div className="loading-spinner" />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Play size={16} fill="currentColor" />
              <span>Analyze Trends</span>
            </>
          )}
        </button>
      </div>

      <div style={{ gridColumn: '1 / -1' }}>
        <button
          type="button"
          className="accordion-toggle"
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
        >
          <Sliders size={14} />
          <span>Advanced Detection Parameters</span>
          {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showAdvanced && (
          <div className="accordion-body">
            <div className="form-group">
              <label className="form-label" htmlFor="percentile-input">
                Threshold Percentile: <strong>{percentile}th</strong>
              </label>
              <input
                id="percentile-input"
                type="range"
                min="85"
                max="99"
                step="1"
                className="form-control"
                style={{ padding: '0.2rem' }}
                value={percentile}
                onChange={(e) => onPercentileChange(parseFloat(e.target.value))}
              />
              <span className="form-hint">Day-of-year 15-day centered window (85%–99%)</span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="mindays-input">
                Min Consecutive Days: <strong>{minDays} days</strong>
              </label>
              <input
                id="mindays-input"
                type="range"
                min="2"
                max="7"
                step="1"
                className="form-control"
                style={{ padding: '0.2rem' }}
                value={minDays}
                onChange={(e) => onMinDaysChange(parseInt(e.target.value))}
              />
              <span className="form-hint">Event definition minimum run length (2–7 days)</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
