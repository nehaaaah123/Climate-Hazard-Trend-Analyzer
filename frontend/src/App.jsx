import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import RegionSelector from './components/RegionSelector';
import LeafletMap from './components/LeafletMap';
import ParamControls from './components/ParamControls';
import SummaryCards from './components/SummaryCards';
import HeatwaveDaysChart from './components/Charts/HeatwaveDaysChart';
import EventCountChart from './components/Charts/EventCountChart';
import IntensityDurationChart from './components/Charts/IntensityDurationChart';
import EventsTable from './components/EventsTable';
import { fetchHeatwaveAnalysis, fetchRegions, getExportUrl } from './api/client';
import { AlertCircle, Clock, Info, Download, FileText } from 'lucide-react';

export default function App() {
  const [presets, setPresets] = useState([]);
  const [selectedPreset, setSelectedPreset] = useState('Delhi');
  const [lat, setLat] = useState('28.6139');
  const [lon, setLon] = useState('77.2090');
  const [bbox, setBbox] = useState('');
  const [isBboxMode, setIsBboxMode] = useState(false);

  const [hazard, setHazard] = useState('heatwave');
  const [startYear, setStartYear] = useState('1990');
  const [endYear, setEndYear] = useState('2023');
  const [percentile, setPercentile] = useState(95);
  const [minDays, setMinDays] = useState(3);

  const [analysisData, setAnalysisData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0);

  // 1. Fetch preset regions on initial load
  useEffect(() => {
    async function loadPresets() {
      try {
        const data = await fetchRegions();
        if (data.regions && data.regions.length > 0) {
          setPresets(data.regions);
        }
      } catch (err) {
        console.warn('Could not load dynamic preset regions, using defaults:', err);
      }
    }
    loadPresets();
  }, []);

  // 2. Handle preset selection
  const handleSelectPreset = (name) => {
    setSelectedPreset(name);
    if (name === 'custom') return;
    const found = presets.find((p) => p.name === name);
    if (found) {
      setLat(found.lat.toString());
      setLon(found.lon.toString());
      setIsBboxMode(false);
      setBbox('');
    }
  };

  // 3. Countdown timer for HTTP 429 rate limit
  useEffect(() => {
    if (rateLimitSeconds <= 0) return;
    const interval = setInterval(() => {
      setRateLimitSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [rateLimitSeconds]);

  // 4. Perform heatwave analysis query
  const runAnalysis = async () => {
    setIsLoading(true);
    setError(null);

    const params = {
      hazard_type: hazard,
      start_year: parseInt(startYear, 10),
      end_year: parseInt(endYear, 10),
      percentile: parseFloat(percentile),
      min_days: parseInt(minDays, 10),
    };

    if (isBboxMode) {
      if (!bbox.trim()) {
        setError('Please enter a bounding box in min_lat,min_lon,max_lat,max_lon format.');
        setIsLoading(false);
        return;
      }
      params.bbox = bbox.trim();
    } else {
      const latNum = parseFloat(lat);
      const lonNum = parseFloat(lon);
      if (isNaN(latNum) || isNaN(lonNum)) {
        setError('Please provide valid decimal latitude and longitude coordinates.');
        setIsLoading(false);
        return;
      }
      params.lat = latNum;
      params.lon = lonNum;
    }

    try {
      const result = await fetchHeatwaveAnalysis(params);
      setAnalysisData(result);
    } catch (err) {
      if (err.status === 429) {
        setRateLimitSeconds(parseInt(err.retryAfter, 10) || 60);
      }
      setError(err.message || 'An error occurred while fetching analysis.');
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-run analysis on initial mount once presets are loaded
  useEffect(() => {
    runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app-container">
      <Header />

      {/* Control Panel */}
      <section className="control-panel" aria-label="Analysis Controls">
        <div className="controls-grid">
          <RegionSelector
            presets={presets}
            selectedPreset={selectedPreset}
            onSelectPreset={handleSelectPreset}
            lat={lat}
            lon={lon}
            onLatChange={(v) => {
              setLat(v);
              setSelectedPreset('custom');
            }}
            onLonChange={(v) => {
              setLon(v);
              setSelectedPreset('custom');
            }}
            bbox={bbox}
            onBboxChange={setBbox}
            isBboxMode={isBboxMode}
            onToggleBboxMode={() => setIsBboxMode(!isBboxMode)}
          />

          <ParamControls
            hazard={hazard}
            onHazardChange={setHazard}
            startYear={startYear}
            onStartYearChange={setStartYear}
            endYear={endYear}
            onEndYearChange={setEndYear}
            percentile={percentile}
            onPercentileChange={setPercentile}
            minDays={minDays}
            onMinDaysChange={setMinDays}
            onRunAnalysis={runAnalysis}
            isLoading={isLoading || rateLimitSeconds > 0}
          />
        </div>

        {/* Bonus 1: Interactive Leaflet Map Selector */}
        {!isBboxMode && (
          <LeafletMap
            lat={lat}
            lon={lon}
            onSelectCoords={(selectedLat, selectedLon) => {
              setLat(selectedLat);
              setLon(selectedLon);
              setSelectedPreset('custom');
            }}
          />
        )}
      </section>

      {/* Export Toolbar (Bonus 2) */}
      {analysisData && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginBottom: '1.25rem' }}>
          <a
            href={getExportUrl('csv', {
              lat: isBboxMode ? undefined : parseFloat(lat),
              lon: isBboxMode ? undefined : parseFloat(lon),
              bbox: isBboxMode ? bbox : undefined,
              start_year: parseInt(startYear),
              end_year: parseInt(endYear),
              percentile,
              min_days: minDays,
              hazard_type: hazard,
            })}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none' }}
          >
            <Download size={14} /> Export CSV Data
          </a>
          <a
            href={getExportUrl('pdf', {
              lat: isBboxMode ? undefined : parseFloat(lat),
              lon: isBboxMode ? undefined : parseFloat(lon),
              bbox: isBboxMode ? bbox : undefined,
              start_year: parseInt(startYear),
              end_year: parseInt(endYear),
              percentile,
              min_days: minDays,
              hazard_type: hazard,
            })}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none', borderColor: '#ef4444' }}
          >
            <FileText size={14} color="#ef4444" /> Download PDF Report
          </a>
        </div>
      )}

      {/* Rate Limit Alert */}
      {rateLimitSeconds > 0 && (
        <div className="alert-box alert-warning">
          <Clock size={20} />
          <div>
            <strong>Rate Limit Applied (HTTP 429):</strong> Upstream Open-Meteo protection active.
            Please wait <strong>{rateLimitSeconds}s</strong> before issuing next request.
          </div>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="alert-box alert-danger">
          <AlertCircle size={20} />
          <div>
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Main Analysis Display */}
      {analysisData && (
        <>
          <SummaryCards analysisData={analysisData} />

          <div className="charts-section">
            <HeatwaveDaysChart
              metrics={analysisData.per_year_metrics}
              rollingAverages={analysisData.rolling_averages}
              trendStats={analysisData.trend_stats}
            />

            <EventCountChart
              metrics={analysisData.per_year_metrics}
              rollingAverages={analysisData.rolling_averages}
            />

            <IntensityDurationChart
              metrics={analysisData.per_year_metrics}
            />
          </div>

          <EventsTable eventsSummary={analysisData.events_summary} />
        </>
      )}

      {/* Empty State when no data */}
      {!analysisData && !isLoading && !error && (
        <div className="alert-box alert-warning" style={{ justifyContent: 'center' }}>
          <Info size={18} />
          <span>Select a region and click <strong>Analyze Trends</strong> to generate climatology metrics.</span>
        </div>
      )}

      <footer style={{ marginTop: '2rem', padding: '1rem 0', borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Climate Hazard Trend Analyzer &copy; {new Date().getFullYear()}</span>
        <span>Reanalysis Data Source: ECMWF ERA5 via Open-Meteo Historical Archive (0.25° grid)</span>
      </footer>
    </div>
  );
}
