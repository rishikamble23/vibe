import { useState } from 'react';

export function ShelterTablet() {
  const [needCount] = useState(250);
  const [receivedCount, setReceivedCount] = useState(185);
  const [capabilities, setCapabilities] = useState({
    refrigeration: true,
    cookedMeals: true,
    medicalStorage: false,
    hotWater: true
  });

  const [auditLog, setAuditLog] = useState<string[]>([
    '[09:10 UTC] Shelter Alpha capacity verified via automated TTL check.',
    '[09:25 UTC] Received Batch #101 (120 portions) confirmed with OTP.'
  ]);

  const addReceivedOutside = () => {
    setReceivedCount(prev => prev + 50);
    setAuditLog(prev => [`[${new Date().toLocaleTimeString()} UTC] Walk-in / outside donation of 50 portions logged.`, ...prev]);
  };

  return (
    <div className="animate-fade" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
      
      {/* Header */}
      <div style={{
        background: 'var(--bg-card)',
        padding: '1.5rem 2rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.75rem'
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
            Shelter Tablet Console
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Shelter Alpha • Need/Received Counters & Capability Toggles
          </p>
        </div>
        <span style={{ background: 'var(--success-bg)', color: 'var(--success-text)', padding: '0.4rem 1rem', borderRadius: '30px', fontSize: '0.85rem', fontWeight: 700, border: '1px solid var(--success-border)' }}>
          Verified Online
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.75rem', marginBottom: '1.75rem' }}>
        
        {/* Counters Box */}
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ margin: '0 0 1.25rem 0', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Intake & Need Counters
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ background: 'var(--bg-app)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', textAlign: 'center' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Target Need</div>
              <div style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--text-main)', margin: '0.5rem 0' }}>{needCount}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Portions required today</div>
            </div>

            <div style={{ background: 'var(--success-bg)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--success-border)', textAlign: 'center' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--success-text)', fontWeight: 700, textTransform: 'uppercase' }}>Received Today</div>
              <div style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--success-text)', margin: '0.5rem 0' }}>{receivedCount}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--success-text)' }}>Verified & ingested</div>
            </div>
          </div>

          <button
            onClick={addReceivedOutside}
            style={{
              width: '100%',
              background: 'var(--primary)',
              color: '#FFFFFF',
              border: 'none',
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 700,
              fontSize: '0.9rem',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            + Log Received Outside Donation (50 Portions)
          </button>
        </div>

        {/* Capability Toggles */}
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ margin: '0 0 1.25rem 0', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Shelter Capabilities & TTL Status
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {Object.entries(capabilities).map(([key, val]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', background: 'var(--bg-app)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', textTransform: 'capitalize' }}>
                  {key.replace(/([A-Z])/g, ' $1')}
                </span>
                <button
                  onClick={() => setCapabilities(prev => ({ ...prev, [key]: !val }))}
                  style={{
                    background: val ? 'var(--success-bg)' : 'var(--danger-bg)',
                    color: val ? 'var(--success-text)' : 'var(--danger-text)',
                    border: `1px solid ${val ? 'var(--success-border)' : 'var(--danger-border)'}`,
                    padding: '0.35rem 0.85rem',
                    borderRadius: '6px',
                    fontWeight: 700,
                    fontSize: '0.8rem'
                  }}
                >
                  {val ? 'ACTIVE' : 'DISABLED'}
                </button>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Audit Log */}
      <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
        <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
          Shelter Verification & Audit Trail
        </h3>
        <div style={{ background: '#0F172A', color: '#E2E8F0', padding: '1rem', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
          {auditLog.map((log, idx) => (
            <div key={idx} style={{ marginBottom: '0.35rem', borderLeft: '3px solid #22C55E', paddingLeft: '0.5rem' }}>
              {log}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
