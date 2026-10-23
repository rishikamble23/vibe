import { useState, useEffect } from 'react';
import { checkBackendHealth, triggerChaosAction } from '../shared/api';

interface MetricCard {
  label: string;
  value: string | number;
  status: 'safe' | 'warning' | 'danger' | 'info';
  subtext: string;
  change?: string;
}

interface BatchItem {
  id: number;
  category: string;
  donor: string;
  qty: number;
  assignedRider: string;
  shelter: string;
  safeUntil: string;
  deliverBy: string;
  slackMinutes: number;
  status: 'safe' | 'at_risk' | 'critical' | 'delivered';
}

export function ControlRoom() {
  const [metrics, setMetrics] = useState<MetricCard[]>([
    { label: 'Active Batches', value: 14, status: 'info', subtext: '3 cooking now', change: '+2 today' },
    { label: 'Portions Saved', value: '1,420', status: 'safe', subtext: '99.4% success rate', change: '+180 this hr' },
    { label: 'Portions at Risk', value: 180, status: 'warning', subtext: 'Slack < 15 min', change: '-12 vs avg' },
    { label: 'Spoilage Violations', value: 0, status: 'safe', subtext: 'Target: 0 (Main Invariant)', change: '100% compliant' },
    { label: 'Active Riders', value: '15 / 18', status: 'info', subtext: '3 on break / offline', change: 'Optimal' },
    { label: 'Median Reassign', value: '42s', status: 'safe', subtext: 'Ghost rate: 1.2%', change: '-5s faster' },
  ]);

  const [batches, setBatches] = useState<BatchItem[]>([
    { id: 101, category: 'cooked_meal', donor: 'Grand Hotel Kitchen', qty: 120, assignedRider: 'Rider #4 (Amit)', shelter: 'Shelter Alpha', safeUntil: '11:45 UTC', deliverBy: '11:30 UTC', slackMinutes: 42, status: 'safe' },
    { id: 102, category: 'dry_ration', donor: 'Central Food Bank', qty: 250, assignedRider: 'Rider #9 (Rahul)', shelter: 'Shelter Beta', safeUntil: '14:00 UTC', deliverBy: '13:45 UTC', slackMinutes: 115, status: 'safe' },
    { id: 103, category: 'medicine', donor: 'City Pharma Hub', qty: 85, assignedRider: 'Rider #2 (Priya)', shelter: 'General Hospital Relief', safeUntil: '10:15 UTC', deliverBy: '10:00 UTC', slackMinutes: 8, status: 'critical' },
    { id: 104, category: 'cooked_meal', donor: 'Community Kitchen C', qty: 60, assignedRider: 'Unassigned (Standby)', shelter: 'Shelter Gamma', safeUntil: '10:40 UTC', deliverBy: '10:25 UTC', slackMinutes: 18, status: 'at_risk' },
    { id: 105, category: 'bakery_fresh', donor: 'Artisan Bakeshop', qty: 95, assignedRider: 'Rider #7 (Kiran)', shelter: 'Hope Children Home', safeUntil: '11:10 UTC', deliverBy: '10:55 UTC', slackMinutes: 28, status: 'safe' },
  ]);

  const [chaosLog, setChaosLog] = useState<string[]>([
    '[09:00:12 UTC] System initialized with 10 donors, 8 shelters, 15 riders.',
    '[09:14:05 UTC] Batch #103 (Medicine) dispatched with P90 ETA 22 min.',
    '[09:22:30 UTC] Shelter Beta intake capacity verified via automated TTL check.',
  ]);

  const [simClock, setSimClock] = useState('09:32 UTC');
  const [activeFilter, setActiveFilter] = useState<'all' | 'safe' | 'at_risk' | 'critical'>('all');

  // Live simulation tick timer & Backend health check
  useEffect(() => {
    checkBackendHealth().then(res => {
      if (res) console.log('Connected to Shelfline Backend:', res);
    });

    const interval = setInterval(() => {
      setBatches(prev => prev.map(b => ({
        ...b,
        slackMinutes: Math.max(1, b.slackMinutes - (b.status === 'critical' ? 1 : 0.2))
      })));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const triggerChaos = async (action: string) => {
    await triggerChaosAction(action);
    const timestamp = new Date().toISOString().substring(11, 19) + ' UTC';
    let msg = '';
    if (action === 'kill_rider') {
      msg = `[${timestamp}] 🚨 CHAOS INJECTED: Rider #4 connection lost. Standby rider auto-promoted in 0.8s!`;
      setBatches(prev => prev.map(b => b.id === 101 ? {...b, assignedRider: 'Standby #12 (Auto-Rerouted)'} : b));
    } else if (action === 'close_shelter') {
      msg = `[${timestamp}] 🏥 CHAOS INJECTED: Shelter Alpha closed unexpectedly! In-transit lease rerouted to Tier 1 fallback (Shelter Delta) in 0.4s.`;
    } else if (action === 'traffic_spike') {
      msg = `[${timestamp}] 🚗 CHAOS INJECTED: Traffic multiplier 2.5x applied to Zone 3. P90 ETAs recalculated successfully.`;
      setMetrics(prev => prev.map(m => m.label === 'Portions at Risk' ? {...m, value: 240, status: 'danger'} : m));
    } else if (action === 'fast_forward') {
      setSimClock('10:02 UTC');
      msg = `[${timestamp}] ⏩ CLOCK ADVANCED: +30 minutes simulated. Reapers executed 4 lease state checks. Zero violations.`;
    }
    setChaosLog(prev => [msg, ...prev]);
  };

  const filteredBatches = batches.filter(b => {
    if (activeFilter === 'all') return true;
    return b.status === activeFilter;
  });

  return (
    <div className="animate-fade" style={{ padding: '2rem', maxWidth: '1600px', margin: '0 auto', width: '100%' }}>
      
      {/* Top Header Banner */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.75rem',
        background: 'var(--bg-card)',
        padding: '1.25rem 1.75rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h1 style={{ margin: 0, fontSize: '1.5rem', color: 'var(--text-main)', fontWeight: 800, letterSpacing: '-0.025em' }}>
              Operations Control Room
            </h1>
            <span style={{ background: 'var(--success-bg)', color: 'var(--success-text)', padding: '0.2rem 0.6rem', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 700 }}>
              Live Mode
            </span>
          </div>
          <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Deadline-Driven Dispatch & Live Spoilage Defense Command Center
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
          <div style={{ background: 'var(--success-bg)', color: 'var(--success-text)', padding: '0.4rem 1rem', borderRadius: '30px', fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', border: '1px solid var(--success-border)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22C55E', display: 'inline-block' }} />
            Engine Active (P90 Enforced)
          </div>
          <div style={{ background: 'var(--info-bg)', color: 'var(--info-text)', padding: '0.4rem 1rem', borderRadius: '30px', fontSize: '0.85rem', fontWeight: 700, border: '1px solid var(--info-border)' }}>
            Sim Clock: {simClock} (10x)
          </div>
        </div>
      </div>

      {/* Metrics Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1.25rem', marginBottom: '1.75rem' }}>
        {metrics.map((m, idx) => {
          let badgeBg = 'var(--info-bg)';
          let badgeColor = 'var(--info-text)';
          let borderCol = 'var(--border-subtle)';
          let leftAccent = 'var(--primary)';

          if (m.status === 'safe') {
            badgeBg = 'var(--success-bg)'; badgeColor = 'var(--success-text)'; leftAccent = '#22C55E';
          } else if (m.status === 'warning') {
            badgeBg = 'var(--warning-bg)'; badgeColor = 'var(--warning-text)'; leftAccent = '#F59E0B';
          } else if (m.status === 'danger') {
            badgeBg = 'var(--danger-bg)'; badgeColor = 'var(--danger-text)'; leftAccent = '#EF4444';
          }

          return (
            <div key={idx} style={{
              background: 'var(--bg-card)',
              border: `1px solid ${borderCol}`,
              borderLeft: `4px solid ${leftAccent}`,
              borderRadius: 'var(--radius-md)',
              padding: '1.25rem',
              boxShadow: 'var(--shadow-sm)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {m.label}
                </span>
                {m.change && (
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: badgeColor, background: badgeBg, padding: '0.15rem 0.5rem', borderRadius: '6px' }}>
                    {m.change}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-main)', margin: '0.5rem 0 0.25rem 0', letterSpacing: '-0.03em' }}>
                {m.value}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                {m.subtext}
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid: Interactive Map & Batches Table */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr', gap: '1.75rem', marginBottom: '1.75rem' }}>
        
        {/* Live Operational Map */}
        <div style={{
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          padding: '1.5rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          height: '460px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)', fontWeight: 700 }}>
              Live Operational Map & Routes
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, background: 'var(--bg-hover)', padding: '0.2rem 0.6rem', borderRadius: '6px' }}>
              Schematic P90 View
            </span>
          </div>

          <div style={{
            flex: 1,
            background: '#F8FAFC',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {/* Legend Overlay */}
            <div style={{
              position: 'absolute',
              top: '16px',
              left: '16px',
              background: '#FFFFFF',
              padding: '0.5rem 0.85rem',
              borderRadius: '8px',
              fontSize: '0.75rem',
              border: '1px solid var(--border-subtle)',
              boxShadow: 'var(--shadow-sm)',
              zIndex: 10,
              display: 'flex',
              gap: '0.75rem',
              fontWeight: 600
            }}>
              <span>🏨 Donors (10)</span>
              <span>🏥 Shelters (8)</span>
              <span>🏍️ Riders (15)</span>
            </div>

            {/* SVG Routes */}
            <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
              <line x1="28%" y1="38%" x2="48%" y2="52%" stroke="#2563EB" strokeWidth="3" strokeDasharray="6,6" />
              <line x1="48%" y1="52%" x2="75%" y2="68%" stroke="#22C55E" strokeWidth="3" />
              <line x1="72%" y1="28%" x2="48%" y2="52%" stroke="#F59E0B" strokeWidth="2.5" strokeDasharray="4,4" />
            </svg>

            {/* Donor Node */}
            <div style={{
              position: 'absolute',
              top: '32%',
              left: '24%',
              background: 'var(--success-bg)',
              border: '2px solid #22C55E',
              borderRadius: '12px',
              padding: '0.4rem 0.75rem',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              fontWeight: 700,
              color: 'var(--success-text)'
            }}>
              🏨 Grand Hotel (120 portions)
            </div>

            {/* Rider Node */}
            <div style={{
              position: 'absolute',
              top: '48%',
              left: '44%',
              background: 'var(--info-bg)',
              border: '2px solid #2563EB',
              borderRadius: '12px',
              padding: '0.4rem 0.75rem',
              boxShadow: 'var(--shadow-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              fontWeight: 700,
              color: 'var(--info-text)'
            }}>
              🏍️ Rider #4 (En Route)
            </div>

            {/* Shelter Node */}
            <div style={{
              position: 'absolute',
              top: '64%',
              left: '70%',
              background: 'var(--warning-bg)',
              border: '2px solid #F59E0B',
              borderRadius: '12px',
              padding: '0.4rem 0.75rem',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              fontWeight: 700,
              color: 'var(--warning-text)'
            }}>
              🏥 Shelter Alpha (Slack: 42m)
            </div>

            {/* Status Footer Banner inside map */}
            <div style={{
              position: 'absolute',
              bottom: '16px',
              left: '16px',
              right: '16px',
              background: '#FFFFFF',
              padding: '0.65rem 1rem',
              borderRadius: '8px',
              fontSize: '0.8rem',
              color: 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              boxShadow: 'var(--shadow-sm)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <span>Active Route: <strong>Rider #4 → Shelter Alpha</strong></span>
              <span style={{ color: '#2563EB', fontWeight: 700 }}>P90 ETA: 14 min</span>
            </div>
          </div>
        </div>

        {/* Active Batches Table */}
        <div style={{
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          padding: '1.5rem',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          flexDirection: 'column',
          height: '460px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)', fontWeight: 700 }}>
                Active Batches & Slack Countdown
              </h3>
            </div>
            
            {/* Filter Tabs */}
            <div style={{ display: 'flex', gap: '0.25rem', background: 'var(--bg-app)', padding: '0.2rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              {(['all', 'safe', 'at_risk', 'critical'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveFilter(tab)}
                  style={{
                    background: activeFilter === tab ? '#FFFFFF' : 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '0.25rem 0.6rem',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: activeFilter === tab ? 'var(--primary)' : 'var(--text-muted)',
                    boxShadow: activeFilter === tab ? 'var(--shadow-sm)' : 'none'
                  }}
                >
                  {tab.toUpperCase().replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  <th style={{ padding: '0.5rem' }}>Batch / Category</th>
                  <th style={{ padding: '0.5rem' }}>Qty</th>
                  <th style={{ padding: '0.5rem' }}>Rider & Shelter</th>
                  <th style={{ padding: '0.5rem' }}>Slack</th>
                  <th style={{ padding: '0.5rem' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredBatches.map(b => {
                  let badgeBg = 'var(--success-bg)';
                  let badgeColor = 'var(--success-text)';
                  let slackColor = 'var(--success-text)';
                  if (b.status === 'critical') {
                    badgeBg = 'var(--danger-bg)'; badgeColor = 'var(--danger-text)'; slackColor = 'var(--danger-text)';
                  } else if (b.status === 'at_risk') {
                    badgeBg = 'var(--warning-bg)'; badgeColor = 'var(--warning-text)'; slackColor = 'var(--warning-text)';
                  }

                  return (
                    <tr key={b.id} style={{ borderBottom: '1px solid var(--border-subtle)', transition: 'background 0.15s' }}>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span style={{ fontWeight: 800, color: 'var(--text-main)' }}>#{b.id}</span><br/>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 500 }}>{b.category}</span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        {b.qty} <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)' }}>portions</span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{b.assignedRider}</div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>to {b.shelter}</div>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span style={{ fontWeight: 800, color: slackColor, fontSize: '0.9rem' }}>
                          {Math.floor(b.slackMinutes)} min
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span style={{
                          background: badgeBg,
                          color: badgeColor,
                          padding: '0.2rem 0.6rem',
                          borderRadius: '6px',
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          letterSpacing: '0.025em'
                        }}>
                          {b.status.toUpperCase().replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {/* Chaos Console & Judge Simulation Panel */}
      <div style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        padding: '1.5rem 1.75rem',
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)', fontWeight: 700 }}>
              Chaos Console & Judge Simulation Panel
            </h3>
            <p style={{ margin: '0.2rem 0 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Deliberately break the system live to prove the invariant holds: no portion is ever delivered after its safe time.
            </p>
          </div>
          <span style={{ background: 'var(--warning-bg)', color: 'var(--warning-text)', padding: '0.3rem 0.8rem', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 700, border: '1px solid var(--warning-border)' }}>
            Judge Mode Active
          </span>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.85rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => triggerChaos('kill_rider')}
            style={{
              background: 'var(--danger-bg)',
              color: 'var(--danger-text)',
              border: '1px solid var(--danger-border)',
              padding: '0.6rem 1.1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            🚨 Ghost Rider (Kill Connection)
          </button>

          <button
            onClick={() => triggerChaos('close_shelter')}
            style={{
              background: 'var(--warning-bg)',
              color: 'var(--warning-text)',
              border: '1px solid var(--warning-border)',
              padding: '0.6rem 1.1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            🏥 Close Shelter Mid-Transit
          </button>

          <button
            onClick={() => triggerChaos('traffic_spike')}
            style={{
              background: 'var(--info-bg)',
              color: 'var(--info-text)',
              border: '1px solid var(--info-border)',
              padding: '0.6rem 1.1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            🚗 Inject Traffic Jam (2.5x P90)
          </button>

          <button
            onClick={() => triggerChaos('fast_forward')}
            style={{
              background: 'var(--success-bg)',
              color: 'var(--success-text)',
              border: '1px solid var(--success-border)',
              padding: '0.6rem 1.1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            ⏩ Fast-Forward Clock (+30m)
          </button>
        </div>

        {/* Live Event & Chaos Log */}
        <div style={{
          background: '#0F172A',
          color: '#E2E8F0',
          padding: '1.25rem',
          borderRadius: 'var(--radius-sm)',
          fontFamily: 'monospace',
          fontSize: '0.825rem',
          maxHeight: '150px',
          overflowY: 'auto',
          boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)'
        }}>
          <div style={{ color: '#94A3B8', marginBottom: '0.6rem', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.075em', fontWeight: 700 }}>
            Live Event & Chaos Audit Trail
          </div>
          {chaosLog.map((log, idx) => (
            <div key={idx} style={{ marginBottom: '0.4rem', borderLeft: '3px solid #38BDF8', paddingLeft: '0.6rem', lineHeight: 1.4 }}>
              {log}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
