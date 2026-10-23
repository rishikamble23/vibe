import { useEffect, useRef } from 'react';
import { Activity, AlertTriangle, ArrowRight, FastForward, Radio, RadioTower, ShieldAlert, TrafficCone, UserX } from 'lucide-react';
import type { AuditEvent } from '../data';

interface ChaosConsoleProps {
  events: AuditEvent[];
  onGhostRider: () => void;
  onCloseShelter: () => void;
  onTrafficSpike: () => void;
  onFastForward: () => void;
}

export default function ChaosConsole({ events, onGhostRider, onCloseShelter, onTrafficSpike, onFastForward }: ChaosConsoleProps) {
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = 0;
  }, [events.length]);

  const actions = [
    { label: 'Ghost rider', detail: 'Simulate rider offline', icon: UserX, className: 'action-ghost', run: onGhostRider },
    { label: 'Close shelter', detail: 'Remove a receiving node', icon: ShieldAlert, className: 'action-shelter', run: onCloseShelter },
    { label: 'Traffic spike', detail: 'Add congestion to routes', icon: TrafficCone, className: 'action-traffic', run: onTrafficSpike },
    { label: 'Fast-forward', detail: 'Advance simulation 15 min', icon: FastForward, className: 'action-fast', run: onFastForward },
  ];

  return (
    <section className="surface-card chaos-card" aria-labelledby="chaos-title">
      <div className="card-heading chaos-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-square" /> JUDGE SIMULATION</div>
          <h2 id="chaos-title">Chaos console</h2>
          <p className="card-subtitle">Stress-test dispatch resilience in real time</p>
        </div>
        <span className="simulation-mode"><Radio size={13} /> SIMULATION MODE</span>
      </div>
      <div className="chaos-content">
        <div className="chaos-actions" aria-label="Simulation actions">
          {actions.map(({ label, detail, icon: Icon, className, run }) => <button key={label} type="button" className={`chaos-action ${className}`} onClick={run}><span className="action-icon"><Icon size={16} /></span><span className="action-text"><strong>{label}</strong><small>{detail}</small></span><ArrowRight size={14} className="action-arrow" /></button>)}
        </div>
        <div className="audit-terminal" aria-label="Live audit event log">
          <div className="terminal-bar"><div className="terminal-lights"><i /><i /><i /></div><span className="terminal-title"><RadioTower size={12} /> LIVE AUDIT STREAM</span><span className="terminal-enforced"><Activity size={11} /> P90 ENFORCED</span></div>
          <div className="terminal-log" ref={logRef} aria-live="polite" aria-relevant="additions text">
            {events.map((event) => <div className={`log-line log-${event.level}`} key={event.id}><span className="log-time">{event.time}</span><span className="log-mark">{event.level === 'success' ? '✓' : event.level === 'warning' ? '!' : event.level === 'critical' ? '×' : '›'}</span><span className="log-message">{event.message}</span></div>)}
            {events.length === 0 && <div className="terminal-empty"><AlertTriangle size={14} />Awaiting simulation events…</div>}
            <div className="terminal-cursor-line"><span className="terminal-prompt">shelfline&gt;</span><span className="terminal-cursor" /></div>
          </div>
          <div className="terminal-footer"><span><span className="terminal-green-dot" /> STREAM CONNECTED</span><span>{events.length} events captured</span></div>
        </div>
      </div>
    </section>
  );
}
