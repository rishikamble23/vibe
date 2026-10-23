import { Activity } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { Batch, Rider, Shelter } from '../data';
import L from 'leaflet';

interface OperationalMapProps {
  batches: Batch[];
  riders: Rider[];
  shelters: Shelter[];
}

// Custom marker icons using inline SVG
const donorIcon = L.divIcon({
  className: 'custom-donor-icon',
  html: `<div class="marker-wrapper donor"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="2"><path d="M21 13.5V16a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 .583-1.418"/><path d="M21 8a2 2 0 0 0-1-1.732"/><path d="M3.876 8.429A2 2 0 0 1 5 7h14a2 2 0 0 1 1.124 1.43l-3.224 5.538"/><path d="M6 12H4"/><path d="M10 12h.01"/><path d="M14 12h.01"/><path d="M18 12h.01"/></svg></div>`,
  iconSize: [36, 36],
  iconAnchor: [18, 36],
});

const shelterIcon = L.divIcon({
  className: 'custom-shelter-icon',
  html: `<div class="marker-wrapper shelter"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></div>`,
  iconSize: [36, 36],
  iconAnchor: [18, 36],
});

const riderIcon = L.divIcon({
  className: 'custom-rider-icon',
  html: `<div class="marker-wrapper rider"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2"><path d="M17 18V6a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v12"/><path d="M3 18h18"/><path d="M9 12h6"/></svg></div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

// Real-world coordinates for demo locations (San Francisco Bay Area)
const DONOR_COORDS: Record<string, [number, number]> = {
  'FreshFoods Hub': [37.7749, -122.4194],
  'MedicalSupplies Co': [37.7849, -122.4094],
  'Community Pantry': [37.7649, -122.4294],
};

const SHELTER_COORDS: Record<string, [number, number]> = {
  'Northside Shelter': [37.7949, -122.4194],
  'Riverside Refuge': [37.7849, -122.4394],
  'East Ward Center': [37.7749, -122.4494],
};

const RIDER_START_COORDS: [number, number] = [37.7749, -122.4194];

export default function OperationalMap({ batches, riders, shelters }: OperationalMapProps) {
  const donorNames = [...new Set(batches.map((batch: Batch) => batch.donor))].slice(0, 3);
  const donorCounts = donorNames.map((name: string) => batches.filter((batch: Batch) => batch.donor === name).length);
  const activeRiders = riders.filter((rider: Rider) => rider.active);
  const openShelters = shelters.filter((shelter: Shelter) => shelter.open);

  // Build route polylines from donors to shelters via riders
  const routes: [number, number][][] = donorNames.map((donorName: string, idx: number): [number, number][] => {
    const donorCoord = DONOR_COORDS[donorName] || RIDER_START_COORDS;
    const shelterIdx = idx % openShelters.length;
    const shelterCoord = openShelters[shelterIdx] 
      ? SHELTER_COORDS[openShelters[shelterIdx].name] 
      : [37.7849, -122.4294];
    return [donorCoord, shelterCoord] as [number, number][];
  });

  // Center map on SF Bay Area
  const center: [number, number] = [37.7749, -122.4194];
  const zoom = 12;

  return (
    <section className="surface-card map-card" aria-labelledby="map-title">
      <div className="card-heading map-heading">
        <div>
          <div className="eyebrow"><span className="live-dot" /> NETWORK TOPOLOGY</div>
          <h2 id="map-title">Live operational map</h2>
          <p className="card-subtitle">Real-time donor → rider → shelter routes</p>
        </div>
        <button className="map-status" type="button" aria-label={`${donorNames.length + activeRiders.length + openShelters.length} network nodes active`}>
          <Activity size={14} />
          <span>{donorNames.length + activeRiders.length + openShelters.length} nodes live</span>
        </button>
      </div>
      <div className="map-container" role="img" aria-label="Interactive map showing donor warehouses, active rider routes, and food shelters">
        <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} className="leaflet-map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {/* Routes - animated polylines */}
          {routes.map((routeCoords: [number, number][], idx: number) => (
            <Polyline
              key={`route-${idx}`}
              positions={routeCoords}
              color={['#3b82f6', '#14b8a6', '#f59e0b'][idx % 3]}
              weight={3}
              opacity={0.8}
              dashArray="8, 8"
              className="route-line"
            >
              <Popup>
                Route {idx + 1}: {donorNames[idx]} → {openShelters[idx % openShelters.length]?.name || 'Shelter'}
              </Popup>
            </Polyline>
          ))}

          {/* Donor markers */}
          {donorNames.map((donorName: string, idx: number) => {
            const coord = DONOR_COORDS[donorName] || RIDER_START_COORDS;
            return (
              <Marker key={`donor-${idx}`} position={coord} icon={donorIcon}>
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title donor">{donorName}</div>
                    <div className="popup-detail">DONOR HUB</div>
                    <div className="popup-meta">{donorCounts[idx]} {donorCounts[idx] === 1 ? 'BATCH' : 'BATCHES'} pending</div>
                    <div className="popup-coords">{coord[0].toFixed(4)}, {coord[1].toFixed(4)}</div>
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {/* Shelter markers */}
          {openShelters.map((shelter: Shelter, idx: number) => {
            const coord = SHELTER_COORDS[shelter.name] || [37.7849, -122.4294];
            return (
              <Marker key={`shelter-${idx}`} position={coord} icon={shelterIcon}>
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title shelter">{shelter.name}</div>
                    <div className="popup-detail">SHELTER · {shelter.open ? 'OPEN' : 'CLOSED'}</div>
                    <div className="popup-meta">Capacity: {shelter.capacity}</div>
                    <div className="popup-coords">{coord[0].toFixed(4)}, {coord[1].toFixed(4)}</div>
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {/* Rider markers with pulsing animation */}
          {activeRiders.map((rider: Rider, idx: number) => {
            // Interpolate rider position along route
            const route = routes[idx % routes.length];
            const progress = (Date.now() / 30000) % 1; // 30 second cycle
            const lat = route[0][0] + (route[1][0] - route[0][0]) * progress;
            const lng = route[0][1] + (route[1][1] - route[0][1]) * progress;
            
            return (
              <Marker key={`rider-${rider.id}`} position={[lat, lng]} icon={riderIcon}>
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title rider">{rider.name}</div>
                    <div className="popup-detail">RIDER · {rider.status}</div>
                    <div className="popup-meta">Vehicle: {rider.vehicle}</div>
                    <div className="popup-coords">{lat.toFixed(4)}, {lng.toFixed(4)}</div>
                  </div>
                </Popup>
                {/* Pulsing circle around rider */}
                <CircleMarker
                  center={[lat, lng]}
                  radius={12}
                  color="#3b82f6"
                  fillColor="#3b82f6"
                  fillOpacity={0.15}
                  weight={2}
                  className="rider-pulse"
                />
              </Marker>
            );
          })}

          {/* Coverage circles for shelters */}
          {openShelters.map((shelter: Shelter, idx: number) => {
            const coord = SHELTER_COORDS[shelter.name] || [37.7849, -122.4294];
            return (
              <CircleMarker
                key={`coverage-${idx}`}
                center={coord}
                radius={800} // ~800 meters
                color="#14b8a6"
                fillColor="#14b8a6"
                fillOpacity={0.05}
                weight={1}
                dashArray="5, 5"
                className="coverage-circle"
              />
            );
          })}
        </MapContainer>
      </div>
      <div className="map-legend">
        <span><i className="legend-square donor-legend" /> Donor hub</span>
        <span><i className="legend-circle rider-legend" /> Rider in transit</span>
        <span><i className="legend-square shelter-legend" /> Shelter</span>
        <span className="legend-route"><i className="legend-route-line" /> Active route</span>
      </div>
    </section>
  );
}