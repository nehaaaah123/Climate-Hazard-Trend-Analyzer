import React, { useState } from 'react';
import { MapPin, Navigation } from 'lucide-react';

export default function RegionSelector({
  presets = [],
  selectedPreset,
  onSelectPreset,
  lat,
  lon,
  onLatChange,
  onLonChange,
  bbox,
  onBboxChange,
  isBboxMode,
  onToggleBboxMode,
}) {
  const [latError, setLatError] = useState('');
  const [lonError, setLonError] = useState('');

  // Validate latitude [-90, 90]
  const handleLatInput = (e) => {
    const val = e.target.value;
    onLatChange(val);
    const num = parseFloat(val);
    if (isNaN(num) || num < -90 || num > 90) {
      setLatError('Latitude must be between -90 and 90');
    } else {
      setLatError('');
    }
  };

  // Validate longitude [-180, 180]
  const handleLonInput = (e) => {
    const val = e.target.value;
    onLonChange(val);
    const num = parseFloat(val);
    if (isNaN(num) || num < -180 || num > 180) {
      setLonError('Longitude must be between -180 and 180');
    } else {
      setLonError('');
    }
  };

  const snappedLat = !isNaN(parseFloat(lat)) ? (Math.round(parseFloat(lat) / 0.25) * 0.25).toFixed(2) : '--';
  const snappedLon = !isNaN(parseFloat(lon)) ? (Math.round(parseFloat(lon) / 0.25) * 0.25).toFixed(2) : '--';

  return (
    <div style={{ display: 'contents' }}>
      <div className="form-group">
        <label className="form-label" htmlFor="preset-select">
          <MapPin size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
          Preset Region
        </label>
        <select
          id="preset-select"
          className="form-select"
          value={selectedPreset}
          onChange={(e) => onSelectPreset(e.target.value)}
        >
          <option value="custom">-- Custom Coordinates --</option>
          {presets.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}, {p.country} ({p.lat}°, {p.lon}°)
            </option>
          ))}
        </select>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
          <span className="form-hint">Or enter custom coordinates below</span>
          <button
            type="button"
            className="btn-secondary"
            style={{ padding: '2px 6px', fontSize: '0.72rem' }}
            onClick={onToggleBboxMode}
          >
            {isBboxMode ? 'Switch to Point' : 'Use Bounding Box'}
          </button>
        </div>
      </div>

      {!isBboxMode ? (
        <>
          <div className="form-group">
            <label className="form-label" htmlFor="input-lat">Latitude (°N)</label>
            <input
              id="input-lat"
              type="number"
              step="0.0001"
              min="-90"
              max="90"
              className="form-control"
              value={lat}
              onChange={handleLatInput}
              placeholder="e.g. 28.6139"
            />
            {latError ? (
              <span style={{ color: '#f87171', fontSize: '0.75rem' }}>{latError}</span>
            ) : (
              <span className="form-hint">Snaps to ERA5 grid: <strong>{snappedLat}°</strong></span>
            )}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="input-lon">Longitude (°E)</label>
            <input
              id="input-lon"
              type="number"
              step="0.0001"
              min="-180"
              max="180"
              className="form-control"
              value={lon}
              onChange={handleLonInput}
              placeholder="e.g. 77.2090"
            />
            {lonError ? (
              <span style={{ color: '#f87171', fontSize: '0.75rem' }}>{lonError}</span>
            ) : (
              <span className="form-hint">Snaps to ERA5 grid: <strong>{snappedLon}°</strong></span>
            )}
          </div>
        </>
      ) : (
        <div className="form-group" style={{ gridColumn: 'span 2' }}>
          <label className="form-label" htmlFor="input-bbox">Bounding Box (min_lat, min_lon, max_lat, max_lon)</label>
          <input
            id="input-bbox"
            type="text"
            className="form-control"
            value={bbox}
            onChange={(e) => onBboxChange(e.target.value)}
            placeholder="e.g. 28.0, 77.0, 29.0, 78.0"
          />
          <span className="form-hint" style={{ color: '#fbbf24' }}>
            Results will represent the centroid grid cell (max size: 10°x10°).
          </span>
        </div>
      )}
    </div>
  );
}
