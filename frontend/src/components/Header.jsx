import React from 'react';
import { Flame, Database, ShieldCheck } from 'lucide-react';

export default function Header() {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-icon">
          <Flame size={24} />
        </div>
        <div>
          <h1 className="brand-title">Climate Hazard Trend Analyzer</h1>
          <p className="brand-subtitle">ERA5 High-Resolution Climatology & Heatwave Trends</p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <span className="badge-tag" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Database size={12} /> Open-Meteo ERA5
        </span>
        <span className="badge-tag" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ShieldCheck size={12} /> 1991–2020 Baseline
        </span>
      </div>
    </header>
  );
}
