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

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarController,
  LineController,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default function EventCountChart({ metrics = [], rollingAverages = {} }) {
  if (!metrics || metrics.length === 0) return null;

  const years = metrics.map((m) => m.year);
  const counts = metrics.map((m) => m.event_count);

  const rollingMap = new Map();
  if (rollingAverages?.series) {
    rollingAverages.series.forEach((pt) => {
      rollingMap.set(pt.year, pt.event_count_rolling_avg);
    });
  }
  const rollingCounts = years.map((yr) => rollingMap.get(yr) ?? null);

  const data = {
    labels: years,
    datasets: [
      {
        type: 'bar',
        label: 'Annual Event Count',
        data: counts,
        backgroundColor: 'rgba(249, 115, 22, 0.75)',
        borderColor: '#f97316',
        borderWidth: 1,
        borderRadius: 4,
        order: 2,
      },
      {
        type: 'line',
        label: '5-Yr Rolling Avg Frequency',
        data: rollingCounts,
        borderColor: '#38bdf8',
        backgroundColor: '#38bdf8',
        borderWidth: 2,
        pointRadius: 2,
        tension: 0.25,
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
          text: 'Number of Heatwave Events',
          color: '#94a3b8',
        },
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', stepSize: 1, beginAtZero: true },
      },
    },
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Annual Heatwave Event Frequency</h3>
        <span className="badge-tag" style={{ color: '#f97316' }}>Discrete Events</span>
      </div>
      <div className="chart-canvas-container">
        <Chart type="bar" data={data} options={options} />
      </div>
    </div>
  );
}
