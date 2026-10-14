import React, { useState } from 'react';
import { Calendar, Flame, Clock, Thermometer } from 'lucide-react';

export default function EventsTable({ eventsSummary }) {
  if (!eventsSummary || !eventsSummary.top_events || eventsSummary.top_events.length === 0) {
    return null;
  }

  const { total_events, top_events } = eventsSummary;
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 5;

  const totalPages = Math.ceil(top_events.length / pageSize);
  const displayedEvents = top_events.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <div className="table-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <h3 className="chart-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Flame size={18} color="#ef4444" />
            Top Significant Heatwave Events
          </h3>
          <span className="card-subtext">
            Displaying the longest and most severe events out of {total_events} total events detected.
          </span>
        </div>
        <span className="badge-tag" style={{ color: '#ef4444' }}>
          {total_events} Total Events
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="custom-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Start Date</th>
              <th>End Date</th>
              <th>Duration</th>
              <th>Peak Temp</th>
              <th>Mean Anomaly</th>
              <th>Attribution Year</th>
            </tr>
          </thead>
          <tbody>
            {displayedEvents.map((ev, index) => (
              <tr key={ev.event_id || index}>
                <td style={{ color: '#94a3b8' }}>{(currentPage - 1) * pageSize + index + 1}</td>
                <td>
                  <Calendar size={13} style={{ display: 'inline', marginRight: 4, color: '#94a3b8' }} />
                  {ev.start_date}
                </td>
                <td>{ev.end_date}</td>
                <td>
                  <Clock size={13} style={{ display: 'inline', marginRight: 4, color: '#fbbf24' }} />
                  <strong>{ev.duration}</strong> days
                </td>
                <td>
                  <Thermometer size={13} style={{ display: 'inline', marginRight: 4, color: '#ef4444' }} />
                  <strong>{ev.peak_temp.toFixed(1)}</strong> °C
                </td>
                <td style={{ color: '#f43f5e' }}>
                  +{ev.mean_intensity.toFixed(2)} °C
                </td>
                <td>
                  <span className="badge-tag">{ev.start_year}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.5rem', marginTop: '1rem' }}>
          <button
            type="button"
            className="btn-secondary"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span className="form-hint" style={{ padding: '0 0.5rem' }}>
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            className="btn-secondary"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
