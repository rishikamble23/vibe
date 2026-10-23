import { useMemo, useState } from 'react';
import { ArrowRight, Check, ChevronDown, Clock3, Filter, Package, UserRound } from 'lucide-react';
import type { Batch, BatchStatus, Rider, Shelter } from '../data';
import { formatSlack, getBatchStatus } from '../data';

type FilterKey = 'All' | BatchStatus;

interface BatchTableProps {
  batches: Batch[];
  riders: Rider[];
  shelters: Shelter[];
  search: string;
  onDeliver: (batch: Batch) => void;
}

const filters: FilterKey[] = ['All', 'Safe', 'At Risk', 'Critical'];

export default function BatchTable({ batches, riders, shelters, search, onDeliver }: BatchTableProps) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>('All');
  const [sortBySlack, setSortBySlack] = useState(true);

  const visibleBatches = useMemo(() => {
    const query = search.trim().toLowerCase();
    return batches
      .filter((batch) => activeFilter === 'All' || getBatchStatus(batch, shelters) === activeFilter)
      .filter((batch) => !query || `${batch.id} ${batch.food} ${batch.donor} ${batch.destination}`.toLowerCase().includes(query))
      .sort((a, b) => sortBySlack ? a.slackSeconds - b.slackSeconds : b.slackSeconds - a.slackSeconds);
  }, [activeFilter, batches, search, shelters, sortBySlack]);

  return (
    <section className="surface-card batch-card" aria-labelledby="active-batches-title">
      <div className="card-heading batch-heading">
        <div>
          <div className="eyebrow"><span className="live-dot" /> LIVE DISPATCH</div>
          <h2 id="active-batches-title">Active batches <span className="heading-count">{batches.length}</span></h2>
          <p className="card-subtitle">Deadline slack across active food runs</p>
        </div>
        <button className="quiet-icon-button sort-button" type="button" title="Reverse slack order" aria-label="Reverse slack order" onClick={() => setSortBySlack((current) => !current)}>
          <Filter size={16} />
        </button>
      </div>
      <div className="batch-toolbar">
        <div className="filter-tabs" role="tablist" aria-label="Filter batches by spoilage risk">
          {filters.map((filter) => (
            <button key={filter} className={`filter-tab ${activeFilter === filter ? 'selected' : ''}`} type="button" role="tab" aria-selected={activeFilter === filter} onClick={() => setActiveFilter(filter)}>
              {filter}
              {filter === 'Critical' && batches.some((batch) => getBatchStatus(batch, shelters) === 'Critical') && <span className="filter-alert-dot" />}
            </button>
          ))}
        </div>
        <span className="table-count">{visibleBatches.length} shown</span>
      </div>
      <div className="table-scroll">
        <table className="batch-table">
          <thead>
            <tr>
              <th scope="col">Batch / origin</th>
              <th scope="col">Destination</th>
              <th scope="col">Rider</th>
              <th scope="col"><button className="th-sort" type="button" onClick={() => setSortBySlack((current) => !current)}>Slack <ChevronDown size={13} /></button></th>
              <th scope="col"><span className="sr-only">Confirm</span></th>
            </tr>
          </thead>
          <tbody>
            {visibleBatches.map((batch) => {
              const status = getBatchStatus(batch, shelters);
              const rider = riders.find((item) => item.id === batch.riderId);
              const shelter = shelters.find((item) => item.id === batch.destinationId);
              const late = batch.slackSeconds <= 0;
              return (
                <tr key={batch.id}>
                  <td>
                    <div className="batch-main"><span className={`batch-glyph ${status.toLowerCase().replace(' ', '-')}`}><Package size={15} /></span><div><span className="batch-id">{batch.id}</span><span className="batch-meta">{batch.food} · {batch.portions.toLocaleString()} portions</span></div></div>
                    <div className="mobile-row-sub">{batch.donor}</div>
                  </td>
                  <td>
                    <span className="destination-name">{batch.destination}</span>
                    <span className={`status-badge ${shelter?.open === false ? 'badge-critical' : `badge-${status.toLowerCase().replace(' ', '-')}`}`}>{shelter?.open === false ? 'Shelter closed' : status}</span>
                  </td>
                  <td>
                    {rider ? <span className="rider-chip"><span className="mini-avatar">{rider.initials}</span>{rider.name.split(' ')[0]}</span> : <span className="unassigned"><UserRound size={13} /> Unassigned</span>}
                  </td>
                  <td>
                    <span className={`slack-value ${late || status === 'Critical' ? 'slack-critical' : status === 'At Risk' ? 'slack-warning' : ''}`}>{late ? `−${formatSlack(batch.slackSeconds)}` : formatSlack(batch.slackSeconds)}</span>
                    <span className="slack-caption"><Clock3 size={11} /> {late ? 'over deadline' : 'to spoilage'}</span>
                  </td>
                  <td><button className="deliver-button" type="button" onClick={() => onDeliver(batch)} aria-label={`Confirm delivery of ${batch.id}`} title="Confirm delivery"><Check size={15} /></button></td>
                </tr>
              );
            })}
            {visibleBatches.length === 0 && <tr><td colSpan={5} className="empty-table"><Package size={20} /><span>No batches match this filter.</span><button type="button" onClick={() => setActiveFilter('All')}>Show all</button></td></tr>}
          </tbody>
        </table>
      </div>
      <div className="table-footnote"><span className="footnote-dot" /> Slack time updates live <span className="footnote-divider">·</span> P90 spoilage protection enforced <ArrowRight size={13} /></div>
    </section>
  );
}
