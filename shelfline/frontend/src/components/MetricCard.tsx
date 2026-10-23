import type { LucideIcon } from 'lucide-react';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  detail: string;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'flat';
  icon: LucideIcon;
  accent: 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'teal';
  quiet?: boolean;
}

export default function MetricCard({ label, value, detail, trend, trendDirection = 'up', icon: Icon, accent, quiet = false }: MetricCardProps) {
  return (
    <article className={`metric-card metric-${accent} ${quiet ? 'metric-quiet' : ''}`}>
      <div className="metric-topline"><span className="metric-label">{label}</span><span className="metric-icon"><Icon size={17} /></span></div>
      <div className="metric-value-row"><strong className="metric-value">{value}</strong>{trend && <span className={`metric-trend trend-${trendDirection}`}>{trendDirection === 'down' ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}{trend}</span>}</div>
      <div className="metric-detail">{detail}</div>
      <span className="metric-accent" />
    </article>
  );
}
