import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarController,
  LineController,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default function HeatwaveDaysChart({ metrics = [], rollingAverages = {}, trendStats = {} }) {
  if (!metrics || metrics.length === 0) return null;

  const years = metrics.map((m) => m.year);
  const days = metrics.map((m) => m.total_heatwave_days);

  // Map rolling averages
  const rollingMap = new Map();
  if (rollingAverages?.series) {
    rollingAverages.series.forEach((pt) => {
      rollingMap.set(pt.year, pt.heatwave_days_rolling_avg);
    });
  }
  const rollingData = years.map((yr) => rollingMap.get(yr) ?? null);

  // Calculate OLS linear regression line points: y = (slope_per_decade/10)*x + intercept
  let regressionData = [];
  const ols = trendStats?.ols;
  if (ols && ols.slope_per_decade !== undefined && ols.intercept !== undefined) {
    const slopePerYear = ols.slope_per_decade / 10.0;
    regressionData = years.map((yr) => {
      const val = slopePerYear * yr + ols.intercept;
      return Math.max(0, parseFloat(val.toFixed(2)));
    });
  }

  const data = {
    labels: years,
    datasets: [
      {
        type: 'bar',
        label: 'Annual Heatwave Days',
        data: days,
        backgroundColor: 'rgba(239, 68, 68, 0.75)',
        borderColor: '#ef4444',
        borderWidth: 1,
        borderRadius: 4,
        order: 3,
      },
      {
        type: 'line',
        label: '5-Yr Rolling Average',
        data: rollingData,
        borderColor: '#38bdf8',
        backgroundColor: '#38bdf8',
        borderWidth: 2.5,
        pointRadius: 2,
        tension: 0.3,
        order: 2,
      },
      {
        type: 'line',
        label: `OLS Trend Line (${ols?.slope_per_decade > 0 ? '+' : ''}${ols?.slope_per_decade?.toFixed(2)} d/dec)`,
        data: regressionData,
        borderColor: '#fbbf24',
        backgroundColor: '#fbbf24',
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 0,
        order: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#cbd5e1',
          font: { family: 'Inter', size: 12 },
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: '#1e293b',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: '#334155',
        borderWidth: 1,
        padding: 10,
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
          text: 'Total Heatwave Days / Year',
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
        <h3 className="chart-title">Heatwave Days per Year & Decadal Trend Overlay</h3>
        <span className="badge-tag" style={{ color: '#fbbf24' }}>Bar + Rolling Avg + OLS</span>
      </div>
      <div className="chart-canvas-container">
        <Chart type="bar" data={data} options={options} />
      </div>
    </div>
  );
}
