import React, { useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function IntensityDurationChart({ metrics = [] }) {
  const [metricMode, setMetricMode] = useState('intensity'); // 'intensity' or 'duration'

  if (!metrics || metrics.length === 0) return null;

  const years = metrics.map((m) => m.year);
  const intensities = metrics.map((m) => m.mean_intensity);
  const durations = metrics.map((m) => m.max_duration);

  const isIntensity = metricMode === 'intensity';

  const data = {
    labels: years,
    datasets: [
      {
        label: isIntensity ? 'Mean Anomaly Intensity (°C)' : 'Max Event Duration (Days)',
        data: isIntensity ? intensities : durations,
        borderColor: isIntensity ? '#f43f5e' : '#a855f7',
        backgroundColor: isIntensity ? 'rgba(244, 63, 94, 0.15)' : 'rgba(168, 85, 247, 0.15)',
        borderWidth: 2.5,
        fill: true,
        pointBackgroundColor: isIntensity ? '#f43f5e' : '#a855f7',
        pointRadius: 3,
        tension: 0.25,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#cbd5e1', font: { family: 'Inter', size: 12 }, usePointStyle: true },
      },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: '#334155',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', maxRotation: 45 },
      },
      y: {
        title: {
          display: true,
          text: isIntensity ? 'Mean Exceedance Anomaly (°C)' : 'Consecutive Days',
          color: '#94a3b8',
        },
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', beginAtZero: true },
      },
    },
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">
          {isIntensity ? 'Mean Heatwave Intensity Over Threshold' : 'Maximum Heatwave Duration per Year'}
        </h3>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            className={`btn-secondary ${isIntensity ? 'active' : ''}`}
            style={{
              backgroundColor: isIntensity ? '#f43f5e' : 'var(--bg-tertiary)',
              color: 'white',
              fontSize: '0.75rem',
            }}
            onClick={() => setMetricMode('intensity')}
          >
            Intensity (°C)
          </button>
          <button
            type="button"
            className={`btn-secondary ${!isIntensity ? 'active' : ''}`}
            style={{
              backgroundColor: !isIntensity ? '#a855f7' : 'var(--bg-tertiary)',
              color: 'white',
              fontSize: '0.75rem',
            }}
            onClick={() => setMetricMode('duration')}
          >
            Max Duration (Days)
          </button>
        </div>
      </div>
      <div className="chart-canvas-container">
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
