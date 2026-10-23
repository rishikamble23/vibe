import { Activity, Building2, MapPin, Navigation, Warehouse } from 'lucide-react';
import type { Batch, Rider, Shelter } from '../data';

interface OperationalMapProps {
  batches: Batch[];
  riders: Rider[];
  shelters: Shelter[];
}

const riderCoordinates = [
  { left: '42%', top: '31%' },
  { left: '48%', top: '62%' },
  { left: '34%', top: '72%' },
];

export default function OperationalMap({ batches, riders, shelters }: OperationalMapProps) {
  const donorNames = [...new Set(batches.map((batch) => batch.donor))].slice(0, 2);
  const donorCounts = donorNames.map((name) => batches.filter((batch) => batch.donor === name).length);
  const routeCount = donorNames.length + riders.filter((rider) => rider.active).length + shelters.filter((shelter) => shelter.open).length;
  return (
    <section className="surface-card map-card" aria-labelledby="map-title">
      <div className="card-heading map-heading">
        <div>
          <div className="eyebrow"><span className="live-dot" /> NETWORK TOPOLOGY</div>
          <h2 id="map-title">Live operational map</h2>
          <p className="card-subtitle">Donors, riders and receiving shelters</p>
        </div>
        <button className="map-status" type="button" aria-label={`${routeCount} network nodes active`}><Activity size={14} /><span>{routeCount} nodes live</span></button>
      </div>
      <div className="map-plot" role="img" aria-label="Schematic of donor warehouses connected by active rider routes to food shelters">
        <div className="map-grid-lines" />
        <svg className="route-svg" viewBox="0 0 1000 480" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="route-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#8ba9d6" /></marker>
          </defs>
          <path className="route-line route-blue" d="M155 110 C310 110 330 155 445 155 S600 128 805 116" markerEnd="url(#route-arrow)" />
          <path className="route-line route-teal" d="M155 280 C310 280 320 185 445 155 S625 265 805 275" markerEnd="url(#route-arrow)" />
          <path className="route-line route-amber" d="M155 280 C285 360 360 345 480 330 S650 385 805 388" markerEnd="url(#route-arrow)" />
          <path className="route-line route-muted" d="M155 110 C270 170 285 270 445 330" />
        </svg>
        <div className="map-region region-one">NORTH QUARTER</div>
        <div className="map-region region-two">RIVER DISTRICT</div>
        <div className="map-region region-three">EAST WARD</div>
        {donorNames[0] && <div className="map-node donor-node donor-one"><span className="map-node-icon donor-icon"><Warehouse size={16} /></span><span className="map-node-copy"><strong>{donorNames[0]}</strong><small>DONOR · {donorCounts[0]} {donorCounts[0] === 1 ? 'BATCH' : 'BATCHES'}</small></span><span className="node-signal" /></div>}
        {donorNames[1] && <div className="map-node donor-node donor-two"><span className="map-node-icon donor-icon donor-icon-purple"><Building2 size={16} /></span><span className="map-node-copy"><strong>{donorNames[1]}</strong><small>DONOR · {donorCounts[1]} {donorCounts[1] === 1 ? 'BATCH' : 'BATCHES'}</small></span><span className="node-signal" /></div>}
        {riders.map((rider, index) => rider.active && <div key={rider.id} className={`map-rider ${index === 0 ? 'rider-blue' : index === 1 ? 'rider-teal' : 'rider-amber'}`} style={riderCoordinates[index]} title={`${rider.name} · ${rider.status}`}><Navigation size={14} /><span>{rider.initials}</span></div>)}
        <div className="map-node shelter-node shelter-one"><span className={`map-node-icon shelter-icon ${!shelters[0]?.open ? 'node-offline' : ''}`}><Building2 size={16} /></span><span className="map-node-copy"><strong>Northside</strong><small>{shelters[0]?.open ? 'SHELTER · OPEN' : 'SHELTER · CLOSED'}</small></span><MapPin className="map-pin" size={13} /></div>
        <div className="map-node shelter-node shelter-two"><span className={`map-node-icon shelter-icon shelter-icon-teal ${!shelters[1]?.open ? 'node-offline' : ''}`}><Building2 size={16} /></span><span className="map-node-copy"><strong>Riverside</strong><small>{shelters[1]?.open ? 'SHELTER · OPEN' : 'SHELTER · CLOSED'}</small></span><MapPin className="map-pin" size={13} /></div>
        <div className="map-node shelter-node shelter-three"><span className={`map-node-icon shelter-icon shelter-icon-amber ${!shelters[2]?.open ? 'node-offline' : ''}`}><Building2 size={16} /></span><span className="map-node-copy"><strong>East Ward</strong><small>{shelters[2]?.open ? 'SHELTER · OPEN' : 'SHELTER · CLOSED'}</small></span><MapPin className="map-pin" size={13} /></div>
        <div className="map-scale"><span /><span>1.2 mi</span></div>
      </div>
      <div className="map-legend"><span><i className="legend-square donor-legend" />Donor hub</span><span><i className="legend-circle rider-legend" />Rider in transit</span><span><i className="legend-square shelter-legend" />Shelter</span><span className="legend-route"><i />Active route</span></div>
    </section>
  );
}
