import { useState } from 'react';

interface Job {
  id: number;
  donor: string;
  shelter: string;
  category: string;
  qty: number;
  slackMinutes: number;
  status: 'assigned' | 'accepted' | 'arrived' | 'picked_up' | 'near_shelter' | 'delivered';
  safeUntil: string;
}

export function RiderPWA() {
  const [isOnline, setIsOnline] = useState(true);
  const [jobs, setJobs] = useState<Job[]>([
    { id: 101, donor: 'Grand Hotel Kitchen', shelter: 'Shelter Alpha', category: 'Cooked Meals', qty: 120, slackMinutes: 42, status: 'assigned', safeUntil: '11:45 UTC' },
    { id: 104, donor: 'Community Kitchen C', shelter: 'Shelter Gamma', category: 'Cooked Meals', qty: 60, slackMinutes: 18, status: 'accepted', safeUntil: '10:40 UTC' },
  ]);

  const advanceStatus = (id: number) => {
    const states: Job['status'][] = ['assigned', 'accepted', 'arrived', 'picked_up', 'near_shelter', 'delivered'];
    setJobs(prev => prev.map(j => {
      if (j.id === id) {
        const currentIndex = states.indexOf(j.status);
        const nextStatus = states[currentIndex + 1] || 'delivered';
        return { ...j, status: nextStatus };
      }
      return j;
    }));
  };

  return (
    <div className="animate-fade" style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
      
      {/* Header & Status Toggle */}
      <div style={{
        background: 'var(--bg-card)',
        padding: '1.5rem 2rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem'
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
            Rider PWA (Mobile View)
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Rider #4 (Amit) • Active Shift • Offline-First Queue Ready
          </p>
        </div>

        <button
          onClick={() => setIsOnline(!isOnline)}
          style={{
            background: isOnline ? 'var(--success-bg)' : 'var(--danger-bg)',
            color: isOnline ? 'var(--success-text)' : 'var(--danger-text)',
            border: `1px solid ${isOnline ? 'var(--success-border)' : 'var(--danger-border)'}`,
            padding: '0.6rem 1.25rem',
            borderRadius: '30px',
            fontWeight: 700,
            fontSize: '0.9rem',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          {isOnline ? '🟢 Online & Ready' : '🔴 Offline / Break'}
        </button>
      </div>

      {/* Active Jobs List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
          Assigned Dispatch Jobs ({jobs.length})
        </h2>

        {jobs.map(job => (
          <div key={job.id} style={{
            background: 'var(--bg-card)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-sm)',
            borderLeft: job.slackMinutes < 20 ? '4px solid #EF4444' : '4px solid #22C55E'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Batch #{job.id} • {job.category}
                </span>
                <h3 style={{ margin: '0.25rem 0 0 0', fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  {job.qty} portions from {job.donor}
                </h3>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: job.slackMinutes < 20 ? '#EF4444' : '#166534' }}>
                  {job.slackMinutes} min slack
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Safe until {job.safeUntil}
                </div>
              </div>
            </div>

            <div style={{ background: 'var(--bg-app)', padding: '0.85rem 1rem', borderRadius: '8px', marginBottom: '1.25rem', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
              <span>Destination: <strong>{job.shelter}</strong></span>
              <span>Current Status: <strong style={{ color: 'var(--primary)' }}>{job.status.toUpperCase()}</strong></span>
            </div>

            {/* Action Buttons Workflow */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {job.status !== 'delivered' ? (
                <button
                  onClick={() => advanceStatus(job.id)}
                  style={{
                    flex: 1,
                    background: 'var(--primary)',
                    color: '#FFFFFF',
                    border: 'none',
                    padding: '0.75rem 1.25rem',
                    borderRadius: 'var(--radius-sm)',
                    fontWeight: 700,
                    fontSize: '0.9rem',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  Advance Step: {
                    job.status === 'assigned' ? 'Accept Job' :
                    job.status === 'accepted' ? 'Arrived at Donor (OTP)' :
                    job.status === 'arrived' ? 'Picked Up Batch' :
                    job.status === 'picked_up' ? 'Near Shelter' : 'Confirm Delivery'
                  } ➔
                </button>
              ) : (
                <div style={{ background: 'var(--success-bg)', color: 'var(--success-text)', padding: '0.75rem 1.25rem', borderRadius: 'var(--radius-sm)', fontWeight: 700, width: '100%', textAlign: 'center' }}>
                  ✅ Successfully Delivered & Verified
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
