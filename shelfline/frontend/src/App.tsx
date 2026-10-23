import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, Bell, CheckCircle2, Clock3, HeartPulse, Package, Search, ShieldCheck, Sparkles, Truck, X } from 'lucide-react';
import type { Batch, Rider, Shelter, ViewKey } from './data';
import { formatSimClock, getBatchStatus, initialBatches, initialRiders, initialShelters } from './data';
import BatchTable from './components/BatchTable';
import MetricCard from './components/MetricCard';
import OperationalMap from './components/OperationalMap';
import Sidebar from './components/Sidebar';
import { DonorView, RiderView, ShelterView } from './views/OperationalViews';

const paths: Record<ViewKey, string> = { control: '/', donor: '/donor', rider: '/rider', shelter: '/shelter' };
type DeliveryActor = { type: 'rider' | 'shelter'; id: string };
const pageCopy: Record<ViewKey, { title: string; subtitle: string }> = {
  control: { title: 'Operations control room', subtitle: 'A clear view of every meal, mile, and minute.' },
  donor: { title: 'Donor portal', subtitle: 'Turn surplus food into a timely community resource.' },
  rider: { title: 'Rider PWA', subtitle: 'Field assignments, freshness windows, and live status.' },
  shelter: { title: 'Shelter tablet', subtitle: 'Receiving desk and inbound food manifest.' },
};

function viewFromPath(path: string): ViewKey {
  if (path === '/donor') return 'donor';
  if (path === '/rider') return 'rider';
  if (path === '/shelter') return 'shelter';
  return 'control';
}

export default function App() {
  const [view, setView] = useState<ViewKey>(() => viewFromPath(window.location.pathname));
  const [batches, setBatches] = useState<Batch[]>(initialBatches);
  const [riders, setRiders] = useState<Rider[]>(initialRiders);
  const [shelters, setShelters] = useState<Shelter[]>(initialShelters);
  const [clockOffset] = useState(0);
  const [portionsSaved, setPortionsSaved] = useState(12840);
  const [medianReassign] = useState(4.2);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [toast, setToast] = useState('');
  const nextBatchRef = useRef(2049);
  const toastTimerRef = useRef<number | undefined>(undefined);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const navigate = useCallback((next: ViewKey) => {
    if (window.location.pathname !== paths[next]) window.history.pushState({}, '', paths[next]);
    setView(next);
    setSearch('');
    setSearchOpen(false);
  }, []);

  useEffect(() => {
    const onPopState = () => setView(viewFromPath(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    document.title = `SHELFLINE — ${view === 'control' ? 'Control Room' : view === 'donor' ? 'Donor Portal' : view === 'rider' ? 'Rider PWA' : 'Shelter Tablet'}`;
  }, [view]);

  useEffect(() => {
    const timer = window.setInterval(() => setBatches((current) => current.map((batch) => ({ ...batch, slackSeconds: batch.slackSeconds - 1 }))), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => () => window.clearTimeout(toastTimerRef.current), []);

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(''), 3200);
  }, []);

  const violations = batches.filter((batch) => batch.slackSeconds <= 0).length;
  const riskPortions = batches.filter((batch) => getBatchStatus(batch, shelters) !== 'Safe').reduce((total, batch) => total + batch.portions, 0);
  const currentPage = pageCopy[view];
  const clock = formatSimClock(clockOffset);

  const confirmDelivery = useCallback((batch: Batch, actor?: DeliveryActor) => {
    const destination = shelters.find((shelter) => shelter.id === batch.destinationId);
    if (destination && !destination.open) {
      showToast(`${destination.name} is closed — reopen receiving before confirming.`);
      return;
    }
    if (actor?.type === 'rider' && (!riders.some((rider) => rider.id === actor.id && rider.active) || batch.riderId !== actor.id)) {
      showToast('This delivery is not assigned to the selected active rider.');
      return;
    }
    if (actor?.type === 'shelter' && actor.id !== batch.destinationId) {
      showToast('This delivery is addressed to a different shelter.');
      return;
    }
    if (destination && destination.received + batch.portions > destination.capacity) {
      showToast(`${destination.name} has insufficient remaining intake capacity.`);
      return;
    }
    setBatches((current) => current.filter((item) => item.id !== batch.id));
    setPortionsSaved((current) => current + batch.portions);
    setShelters((current) => current.map((shelter) => shelter.id === batch.destinationId ? { ...shelter, received: shelter.received + batch.portions } : shelter));
    showToast(`${batch.portions.toLocaleString()} portions confirmed delivered.`);
  }, [riders, shelters, showToast]);

  const createBatch = useCallback((batch: Omit<Batch, 'id'>) => {
    const destination = shelters.find((shelter) => shelter.id === batch.destinationId);
    const reserved = batches.filter((item) => item.destinationId === batch.destinationId).reduce((total, item) => total + item.portions, 0);
    const available = (destination?.capacity ?? 0) - (destination?.received ?? 0) - reserved;
    if (!destination?.open || !Number.isFinite(batch.portions) || batch.portions < 1 || batch.portions > available) {
      showToast(destination?.open ? `Only ${Math.max(0, available).toLocaleString()} portions of capacity remain at ${destination.name}.` : 'Choose an open shelter before registering a donation.');
      return;
    }
    const id = `SL-${nextBatchRef.current++}`;
    setBatches((current) => [{ ...batch, id }, ...current]);
    showToast(`${id} added to live dispatch.`);
  }, [batches, shelters, showToast]);

  const toggleRider = useCallback((target: Rider) => {
    const active = !target.active;
    setRiders((current) => current.map((rider) => rider.id === target.id ? { ...rider, active, status: active ? 'Standby' : 'Offline' } : rider));
    showToast(`${target.name} ${active ? 'restored to dispatch' : 'paused from dispatch'}.`);
  }, [showToast]);

  const toggleShelter = useCallback((target: Shelter) => {
    const open = !target.open;
    setShelters((current) => current.map((shelter) => shelter.id === target.id ? { ...shelter, open } : shelter));
    if (open) setBatches((current) => current.map((batch) => batch.destinationId === target.id ? { ...batch, slackSeconds: batch.slackSeconds + 8 * 60 } : batch));
    showToast(`${target.name} receiving ${open ? 'reopened' : 'paused'}.`);
  }, [showToast]);

  const metrics = useMemo(() => [
    { label: 'Active batches', value: batches.length, detail: 'Across 3 partner shelters', trend: '+2 today', trendDirection: 'up' as const, icon: Package, accent: 'blue' as const },
    { label: 'Portions saved', value: portionsSaved.toLocaleString(), detail: 'Meals kept in circulation', trend: '+18% vs. yesterday', trendDirection: 'up' as const, icon: HeartPulse, accent: 'green' as const },
    { label: 'Portions at risk', value: riskPortions.toLocaleString(), detail: 'In batches needing attention', trend: riskPortions ? 'Needs attention' : 'All on track', trendDirection: riskPortions ? 'up' as const : 'down' as const, icon: AlertTriangle, accent: 'amber' as const },
    { label: 'Spoilage violations', value: violations, detail: 'P90 threshold breaches', trend: violations ? 'Action required' : 'Within threshold', trendDirection: violations ? 'up' as const : 'down' as const, icon: ShieldCheck, accent: violations ? 'red' as const : 'green' as const, quiet: !violations },
    { label: 'Active riders', value: riders.filter((rider) => rider.active).length, detail: 'Riders connected to dispatch', trend: `${shelters.filter((shelter) => shelter.open).length} zones covered`, trendDirection: 'up' as const, icon: Truck, accent: 'violet' as const },
    { label: 'Median reassign', value: `${medianReassign.toFixed(1)}m`, detail: 'Average recovery time', trend: '−0.8m this shift', trendDirection: 'down' as const, icon: Activity, accent: 'teal' as const },
  ], [batches.length, portionsSaved, riskPortions, violations, riders, shelters, medianReassign]);

  useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus();
  }, [searchOpen]);

  return (
    <div className="app-shell">
      <Sidebar activeView={view} onNavigate={navigate} />
      <main className="main-panel">
        <header className="page-header">
          <div className="page-title-block"><span className="page-kicker">SHELFLINE <span>/</span> {view === 'control' ? 'OPERATIONS' : view === 'donor' ? 'SUPPLY NETWORK' : view === 'rider' ? 'FIELD OPERATIONS' : 'RECEIVING'}</span><h1>{currentPage.title}</h1><p>{currentPage.subtitle}</p></div>
          <div className="header-tools">
            <div className="header-statuses"><span className="header-engine"><span className="engine-dot" /> Engine active</span><span className="header-clock"><Clock3 size={14} /> Sim clock <strong>{clock}</strong></span></div>
            <div className="header-actions">
              {searchOpen ? <label className="global-search"><Search size={15} /><input ref={searchInputRef} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search batches…" aria-label="Search batches" /><button type="button" onClick={() => { setSearch(''); setSearchOpen(false); }} aria-label="Close search"><X size={14} /></button></label> : <button className="header-icon-button" type="button" title="Search active batches" aria-label="Search active batches" onClick={() => setSearchOpen(true)}><Search size={17} /></button>}
              <div className="notification-wrap"><button className={`header-icon-button ${notificationOpen ? 'header-icon-selected' : ''}`} type="button" title="Notifications" aria-label="Notifications" aria-expanded={notificationOpen} onClick={() => setNotificationOpen((current) => !current)}><Bell size={17} />{riskPortions > 0 && <i className="notification-dot" />}</button>{notificationOpen && <div className="notification-popover"><div className="popover-head"><span><Bell size={14} /> Dispatch alerts</span><button type="button" aria-label="Close notifications" onClick={() => setNotificationOpen(false)}><X size={14} /></button></div><div className="popover-alert"><span className="popover-alert-icon"><AlertTriangle size={14} /></span><span><strong>{batches.filter((batch) => getBatchStatus(batch, shelters) !== 'Safe').length} batches need attention</strong><small>{riskPortions.toLocaleString()} portions are at risk</small></span></div><div className="popover-foot"><CheckCircle2 size={13} /> All alerts are up to date</div></div>}</div>
            </div>
          </div>
        </header>
        {view === 'control' && <div className="dashboard-content">
          <section className="metrics-grid" aria-label="Live operation metrics">{metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}</section>
          <section className="operations-grid" aria-label="Live dispatch details"><OperationalMap batches={batches} riders={riders} shelters={shelters} /><BatchTable batches={batches} riders={riders} shelters={shelters} search={search} onDeliver={confirmDelivery} /></section>
          <div className="page-footnote"><span><Sparkles size={14} /> Every portion matters.</span><span>SHELFLINE CONTROL PLANE <i /> DATA REFRESHES LIVE</span></div>
        </div>}
        {view === 'donor' && <div className="view-content"><DonorView batches={batches} shelters={shelters} onCreate={createBatch} /></div>}
        {view === 'rider' && <div className="view-content"><RiderView riders={riders} batches={batches} onToggle={toggleRider} onDeliver={(batch, riderId) => confirmDelivery(batch, { type: 'rider', id: riderId })} /></div>}
        {view === 'shelter' && <div className="view-content"><ShelterView shelters={shelters} batches={batches} onToggle={toggleShelter} onReceive={(batch, shelterId) => confirmDelivery(batch, { type: 'shelter', id: shelterId })} /></div>}
        {toast && <div className="toast-message" role="status"><CheckCircle2 size={16} /><span>{toast}</span><button type="button" aria-label="Dismiss message" onClick={() => setToast('')}><X size={14} /></button></div>}
      </main>
    </div>
  );
}