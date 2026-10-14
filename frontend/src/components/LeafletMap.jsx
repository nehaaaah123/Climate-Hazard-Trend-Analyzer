import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Map as MapIcon, ChevronDown, ChevronUp } from 'lucide-react';

// Custom red Leaflet pin icon using inline SVG
const pinIcon = new L.DivIcon({
  className: 'custom-leaflet-icon',
  html: `<div style="
    background: #ef4444;
    width: 24px;
    height: 24px;
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    border: 2px solid white;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
  "></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 24],
  popupAnchor: [0, -24],
});

function MapRecenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center && !isNaN(center[0]) && !isNaN(center[1])) {
      map.setView(center, map.getZoom());
    }
  }, [center, map]);
  return null;
}

function LocationMarker({ onLocationSelect, currentPos, snappedPos }) {
  useMapEvents({
    click(e) {
      onLocationSelect(e.latlng.lat, e.latlng.lng);
    },
  });

  return currentPos ? (
    <Marker position={currentPos} icon={pinIcon}>
      <Popup>
        <div style={{ fontSize: '12px', color: '#1e293b' }}>
          <strong>Selected Location:</strong><br />
          Lat: {currentPos[0].toFixed(4)}°N<br />
          Lon: {currentPos[1].toFixed(4)}°E<br />
          <hr style={{ margin: '4px 0' }} />
          <strong>Snapped ERA5 Cell:</strong><br />
          {snappedPos ? `${snappedPos[0]}°N, ${snappedPos[1]}°E` : '--'}
        </div>
      </Popup>
    </Marker>
  ) : null;
}

export default function LeafletMap({ lat, lon, onSelectCoords }) {
  const [isOpen, setIsOpen] = useState(false);

  const latNum = parseFloat(lat);
  const lonNum = parseFloat(lon);
  const isValid = !isNaN(latNum) && !isNaN(lonNum);

  const center = isValid ? [latNum, lonNum] : [28.6139, 77.2090];
  const snappedPos = isValid
    ? [(Math.round(latNum / 0.25) * 0.25).toFixed(2), (Math.round(lonNum / 0.25) * 0.25).toFixed(2)]
    : null;

  return (
    <div style={{ marginTop: '0.75rem', width: '100%' }}>
      <button
        type="button"
        className="btn-secondary"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          width: '100%',
          justifyContent: 'center',
          padding: '0.5rem',
        }}
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <MapIcon size={14} />
        <span>{isOpen ? 'Hide Interactive Region Map' : 'Select Region on Interactive Map'}</span>
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {isOpen && (
        <div
          style={{
            marginTop: '0.75rem',
            height: '280px',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
            border: '1px solid var(--border-color)',
          }}
        >
          <MapContainer
            center={center}
            zoom={4}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapRecenter center={center} />
            <LocationMarker
              currentPos={isValid ? [latNum, lonNum] : null}
              snappedPos={snappedPos}
              onLocationSelect={(clickedLat, clickedLon) => {
                onSelectCoords(clickedLat.toFixed(4), clickedLon.toFixed(4));
              }}
            />
          </MapContainer>
        </div>
      )}
    </div>
  );
}
