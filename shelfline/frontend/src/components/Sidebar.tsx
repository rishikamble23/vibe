import { Activity, Bike, Boxes, HeartPulse, Hospital, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ViewKey } from '../data';

interface SidebarProps {
  activeView: ViewKey;
  onNavigate: (view: ViewKey) => void;
}

const items: { key: ViewKey; label: string; sub: string; icon: LucideIcon }[] = [
  { key: 'control', label: 'Control Room', sub: 'LIVE OPERATIONS', icon: Zap },
  { key: 'donor', label: 'Donor Portal', sub: 'INBOUND SUPPLY', icon: Boxes },
  { key: 'rider', label: 'Rider PWA', sub: 'FIELD DISPATCH', icon: Bike },
  { key: 'shelter', label: 'Shelter Tablet', sub: 'RECEIVING DESK', icon: Hospital },
];

export default function Sidebar({ activeView, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true"><span>S</span><i /></div>
        <div className="brand-copy"><strong>SHELFLINE</strong><span>FIELD OPERATIONS</span></div>
        <span className="version-badge">v2.4</span>
      </div>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {items.map(({ key, label, sub, icon: Icon }) => <button key={key} type="button" className={`nav-item ${activeView === key ? 'nav-active' : ''}`} onClick={() => onNavigate(key)} aria-current={activeView === key ? 'page' : undefined}><span className="nav-icon"><Icon size={18} strokeWidth={activeView === key ? 2.35 : 1.9} /></span><span className="nav-copy"><strong>{label}</strong><small>{sub}</small></span>{activeView === key && <span className="nav-active-indicator" />}</button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-lower">
        <div className="network-health"><span className="health-icon"><HeartPulse size={15} /></span><span className="health-copy"><strong>Dispatch health</strong><small>All systems nominal</small></span><span className="health-check"><Activity size={14} /></span></div>
        <div className="engine-pill"><span className="engine-dot" /><span>Engine active</span><span className="engine-divider" /><span className="engine-mode">P90 enforced</span></div>
        <div className="sidebar-foot"><span>© 2025 SHELFLINE</span><span>v2.4.0</span></div>
      </div>
    </aside>
  );
}
