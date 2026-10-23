import { useState, type FormEvent } from 'react';
import { ArrowRight, Bike, Boxes, Building2, Check, CheckCircle2, Clock3, HeartHandshake, MapPin, Package, Plus, ShieldCheck, Wifi, WifiOff } from 'lucide-react';
import type { Batch, BatchStatus, Rider, Shelter } from '../data';
import { formatSlack, getBatchStatus } from '../data';

interface DonorViewProps {
  batches: Batch[];
  shelters: Shelter[];
  onCreate: (batch: Omit<Batch, 'id'>) => void;
}

export function DonorView({ batches, shelters, onCreate }: DonorViewProps) {
  const [donor, setDonor] = useState('Harbor Market');
  const [food, setFood] = useState('Fresh produce');
  const [destinationId, setDestinationId] = useState(shelters[0]?.id ?? 'SH-01');
  const [portions, setPortions] = useState(240);
  const [slackMinutes, setSlackMinutes] = useState(60);
  const destination = shelters.find((item) => item.id === destinationId);
  const reservedPortions = batches.filter((batch) => batch.destinationId === destinationId).reduce((total, batch) => total + batch.portions, 0);
  const availablePortions = Math.max(0, (destination?.capacity ?? 0) - (destination?.received ?? 0) - reservedPortions);
  const portionsValid = Number.isFinite(portions) && portions >= 1 && portions <= availablePortions;
  const donors = ['Harbor Market', 'Civic Kitchen', 'Metro Foods'];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!destination?.open || !portionsValid) return;
    const category = food.toLowerCase().includes('dairy') || food.toLowerCase().includes('chilled') ? 'Chilled' : food.toLowerCase().includes('bakery') ? 'Bakery' : food.toLowerCase().includes('meal') ? 'Prepared' : 'Produce';
    onCreate({ food, category, donor, destination: destination.name, destinationId, portions, slackSeconds: slackMinutes * 60, riderId: null });
  }

  return (
    <div className="portal-layout">
      <section className="surface-card portal-intro">
        <div className="portal-intro-copy"><span className="portal-kicker"><HeartHandshake size={14} /> DONOR PARTNERSHIP</span><h2>Good food, <span>good timing.</span></h2><p>Register surplus food for a nearby shelter. SHELFLINE will match it with a rider before its freshness window closes.</p><div className="portal-proof"><span><CheckCircle2 size={15} /> P90 freshness monitoring</span><span><CheckCircle2 size={15} /> Live dispatch matching</span></div></div>
        <div className="donor-illustration" aria-hidden="true"><div className="illustration-ring ring-one" /><div className="illustration-ring ring-two" /><div className="illustration-box"><Boxes size={39} /></div><span className="illustration-spark spark-one">✦</span><span className="illustration-spark spark-two">✳</span><span className="illustration-plate"><Check size={13} /></span></div>
      </section>
      <section className="surface-card donation-form-card">
        <div className="card-heading"><div><div className="eyebrow">NEW DONATION</div><h2>Register a batch</h2><p className="card-subtitle">Tell us what’s ready for pickup</p></div><span className="form-step">01 <i /> 02</span></div>
        <form className="donation-form" onSubmit={submit}>
          <div className="form-grid">
            <label className="field-label">Donor location<select value={donor} onChange={(event) => setDonor(event.target.value)}>{donors.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label className="field-label">Food type<select value={food} onChange={(event) => setFood(event.target.value)}>{['Fresh produce', 'Prepared meals', 'Dairy & chilled goods', 'Bakery surplus', 'Produce boxes'].map((name) => <option key={name}>{name}</option>)}</select></label>
            <label className="field-label">Receiving shelter<select value={destinationId} onChange={(event) => setDestinationId(event.target.value)}>{shelters.map((shelter) => <option key={shelter.id} value={shelter.id} disabled={!shelter.open}>{shelter.name}{!shelter.open ? ' (closed)' : ''}</option>)}</select></label>
            <label className="field-label">Portions ready<input min="1" max={availablePortions} type="number" value={portions || ''} onChange={(event) => setPortions(event.target.value ? event.target.valueAsNumber : 0)} /><small className={`field-help ${portions > availablePortions ? 'field-help-warning' : ''}`}>{availablePortions.toLocaleString()} portions of capacity available</small></label>
            <label className="field-label field-wide">Freshness window <span className="field-value">{slackMinutes} min</span><input className="range-input" type="range" min="15" max="120" step="5" value={slackMinutes} onChange={(event) => setSlackMinutes(Number(event.target.value))} /><span className="range-labels"><span>15 min</span><span>2 hours</span></span></label>
          </div>
          <div className="form-footer"><span><ShieldCheck size={15} /> Time-sensitive handling is enabled</span><button className="primary-button" type="submit" disabled={!destination?.open || !portionsValid}><Plus size={16} /> Add to dispatch <ArrowRight size={15} /></button></div>
        </form>
      </section>
      <section className="surface-card donor-network-card">
        <div className="card-heading"><div><div className="eyebrow">YOUR NETWORK</div><h2>Partner locations</h2></div><span className="network-counter"><span className="live-dot" /> 3 connected</span></div>
        <div className="partner-list">{donors.map((name, index) => { const count = batches.filter((batch) => batch.donor === name).length; return <div className="partner-row" key={name}><span className={`partner-logo partner-logo-${index}`}><Building2 size={17} /></span><span className="partner-name"><strong>{name}</strong><small>{['Harbor District', 'Civic Center', 'Market Street'][index]}</small></span><span className="partner-batches">{count} {count === 1 ? 'active batch' : 'active batches'}</span><span className="partner-online"><i /> Connected</span></div>; })}</div>
      </section>
    </div>
  );
}

interface RiderViewProps {
  riders: Rider[];
  batches: Batch[];
  onToggle: (rider: Rider) => void;
  onDeliver: (batch: Batch, riderId: string) => void;
}

export function RiderView({ riders, batches, onToggle, onDeliver }: RiderViewProps) {
  const [selectedId, setSelectedId] = useState(riders[0]?.id ?? '');
  const selected = riders.find((rider) => rider.id === selectedId) ?? riders[0];
  const tasks = batches.filter((batch) => batch.riderId === selected?.id);
  return (
    <div className="field-layout">
      <section className="rider-welcome"><div className="rider-welcome-copy"><span className="portal-kicker"><Bike size={14} /> FIELD DISPATCH</span><h2>Every minute<br />moves <span>good forward.</span></h2><p>Rider status and delivery queue are synced to the P90 dispatch engine.</p><span className="rider-sync"><Wifi size={14} /> Sync active · updated just now</span></div><div className="rider-route-art" aria-hidden="true"><svg viewBox="0 0 300 130"><path d="M20 96 C70 95 65 28 118 45 S170 112 210 72 243 20 284 25" fill="none" stroke="#80a9f5" strokeWidth="2" strokeDasharray="5 7"/><circle cx="20" cy="96" r="5" fill="#2563eb"/><circle cx="118" cy="45" r="5" fill="#13a889"/><circle cx="210" cy="72" r="5" fill="#f3a627"/><circle cx="284" cy="25" r="5" fill="#2563eb"/></svg><div className="rider-route-pin"><Bike size={21} /></div><span className="route-art-caption">ROUTE NETWORK ACTIVE</span></div></section>
      <section className="field-section"><div className="section-title-row"><div><div className="eyebrow">ON THE GROUND</div><h2>Rider roster <span className="heading-count">{riders.filter((rider) => rider.active).length} active</span></h2></div><span className="field-date"><Clock3 size={14} /> Sim shift · 09:32 UTC</span></div><div className="rider-roster">{riders.map((rider) => <article key={rider.id} className={`surface-card rider-card ${selected?.id === rider.id ? 'rider-card-selected' : ''}`}><button className="rider-card-select" type="button" onClick={() => setSelectedId(rider.id)} aria-pressed={selected?.id === rider.id}><span className={`rider-avatar avatar-${rider.id.slice(-1)}`}>{rider.initials}</span><span className="rider-card-name"><strong>{rider.name}</strong><small>{rider.vehicle}</small></span><span className={`rider-status ${rider.active ? rider.status === 'Standby' ? 'rider-standby' : 'rider-on-route' : 'rider-offline'}`}><i />{rider.active ? rider.status : 'Offline'}</span></button><div className="rider-card-meta"><span><MapPin size={13} /> {rider.location}</span><span><Clock3 size={13} /> {rider.eta} min ETA</span></div><button type="button" className={`rider-toggle ${rider.active ? '' : 'toggle-resume'}`} onClick={() => onToggle(rider)}>{rider.active ? <><WifiOff size={14} /> Pause rider</> : <><Wifi size={14} /> Restore rider</>}</button></article>)}</div></section>
      <section className="surface-card rider-queue-card"><div className="card-heading"><div><div className="eyebrow"><span className="live-dot" /> ASSIGNED TO {selected?.name.toUpperCase() ?? 'RIDER'}</div><h2>Current delivery queue</h2><p className="card-subtitle">Active assignments prioritized by spoilage slack</p></div><span className="queue-count"><Package size={14} /> {tasks.length} tasks</span></div><div className="rider-task-list">{tasks.length ? tasks.map((batch) => <RiderTask key={batch.id} batch={batch} riderId={selected?.id ?? ''} disabled={!selected?.active} onDeliver={onDeliver} />) : <div className="queue-empty"><CheckCircle2 size={20} /><span><strong>No active assignments</strong><small>New dispatches will appear here automatically.</small></span></div>}</div></section>
    </div>
  );
}

function RiderTask({ batch, riderId, disabled, onDeliver }: { batch: Batch; riderId: string; disabled: boolean; onDeliver: (batch: Batch, riderId: string) => void }) {
  return <div className="rider-task"><span className="task-marker"><Package size={17} /></span><span className="task-copy"><strong>{batch.id} · {batch.food}</strong><small><MapPin size={12} /> {batch.destination} · {batch.portions.toLocaleString()} portions</small></span><span className="task-slack"><Clock3 size={13} /> {formatSlack(batch.slackSeconds)}</span><button type="button" className="task-complete" disabled={disabled} onClick={() => onDeliver(batch, riderId)} aria-label={`Confirm delivery ${batch.id}`} title={disabled ? 'Restore this rider before confirming' : 'Confirm delivery'}><Check size={15} /></button></div>;
}

interface ShelterViewProps {
  shelters: Shelter[];
  batches: Batch[];
  onToggle: (shelter: Shelter) => void;
  onReceive: (batch: Batch, shelterId: string) => void;
}

export function ShelterView({ shelters, batches, onToggle, onReceive }: ShelterViewProps) {
  const [selectedId, setSelectedId] = useState(shelters[0]?.id ?? '');
  const selected = shelters.find((shelter) => shelter.id === selectedId) ?? shelters[0];
  const incoming = batches.filter((batch) => batch.destinationId === selected?.id);
  return (
    <div className="shelter-layout">
      <section className="shelter-welcome"><div><span className="portal-kicker"><Building2 size={14} /> RECEIVING DESK</span><h2>Good food is<br />on the <span>way.</span></h2><p>Live inbound manifest for partner shelters. Confirm arrivals to close the dispatch loop.</p></div><div className="shelter-welcome-mark"><span><Building2 size={33} /></span><small>COMMUNITY<br />RECEIVING</small></div></section>
      <div className="shelter-workspace"><section className="surface-card shelter-list-card"><div className="card-heading"><div><div className="eyebrow">CONNECTED LOCATIONS</div><h2>Shelter network</h2><p className="card-subtitle">Select a receiving desk</p></div></div><div className="shelter-list">{shelters.map((shelter) => { const count = batches.filter((batch) => batch.destinationId === shelter.id).length; return <button key={shelter.id} type="button" className={`shelter-select-row ${selected?.id === shelter.id ? 'selected' : ''}`} onClick={() => setSelectedId(shelter.id)}><span className="shelter-row-icon"><Building2 size={17} /></span><span className="shelter-row-copy"><strong>{shelter.name}</strong><small>{shelter.neighborhood}</small></span><span className={`shelter-open-dot ${shelter.open ? '' : 'closed'}`} /><span className="shelter-row-count">{count}</span></button>; })}</div></section>
        {selected && <section className="surface-card shelter-detail-card"><div className="shelter-detail-head"><div><div className="eyebrow">SHELTER TABLET · {selected.id}</div><h2>{selected.name}</h2><p className="card-subtitle"><MapPin size={13} /> {selected.neighborhood}</p></div><span className={`shelter-status-large ${selected.open ? '' : 'shelter-status-closed'}`}><i />{selected.open ? 'Receiving' : 'Closed'}</span></div>
          <div className="capacity-card"><div className="capacity-label"><span>Daily intake capacity</span><strong>{Math.round((selected.received / selected.capacity) * 100)}% utilized</strong></div><div className="capacity-track"><span style={{ width: `${Math.min(100, (selected.received / selected.capacity) * 100)}%` }} /></div><div className="capacity-numbers"><span>{selected.received.toLocaleString()} portions received</span><span>{selected.capacity.toLocaleString()} max</span></div></div>
          <div className="inbound-header"><div><h3>Inbound manifest</h3><p>{incoming.length} active {incoming.length === 1 ? 'delivery' : 'deliveries'}</p></div><span className="manifest-status"><span className="live-dot" /> LIVE</span></div>
          <div className="manifest-list">{incoming.length ? incoming.map((batch) => <ManifestRow key={batch.id} batch={batch} shelter={selected} onReceive={onReceive} />) : <div className="queue-empty"><CheckCircle2 size={20} /><span><strong>No inbound food right now</strong><small>Newly assigned deliveries will appear in this manifest.</small></span></div>}</div>
          <button className={`shelter-toggle-button ${selected.open ? 'close-receiving' : ''}`} type="button" onClick={() => onToggle(selected)}>{selected.open ? <><ShieldCheck size={15} /> Pause receiving for this shelter</> : <><CheckCircle2 size={15} /> Reopen receiving</>}</button>
        </section>}
      </div>
    </div>
  );
}

function ManifestRow({ batch, shelter, onReceive }: { batch: Batch; shelter: Shelter; onReceive: (batch: Batch, shelterId: string) => void }) {
  const status: BatchStatus = shelter.open ? getBatchStatus(batch, [shelter]) : 'Critical';
  return <div className="manifest-row"><span className="manifest-package"><Package size={16} /></span><span className="manifest-copy"><strong>{batch.food}</strong><small>{batch.id} · {batch.portions.toLocaleString()} portions · {batch.donor}</small></span><span className={`status-badge badge-${status.toLowerCase().replace(' ', '-')}`}>{status}</span><button type="button" className="manifest-receive" onClick={() => onReceive(batch, shelter.id)} disabled={!shelter.open} title="Confirm received" aria-label={`Confirm ${batch.id} received`}><Check size={15} /></button></div>;
}
