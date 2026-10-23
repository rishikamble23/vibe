export type BatchStatus = 'Safe' | 'At Risk' | 'Critical';
export type ViewKey = 'control' | 'donor' | 'rider' | 'shelter';

export interface Batch {
  id: string;
  food: string;
  category: string;
  donor: string;
  destination: string;
  destinationId: string;
  portions: number;
  slackSeconds: number;
  riderId: string | null;
}

export interface Rider {
  id: string;
  name: string;
  initials: string;
  vehicle: string;
  status: 'On route' | 'Standby' | 'Offline';
  eta: number;
  active: boolean;
  location: string;
}

export interface Shelter {
  id: string;
  name: string;
  neighborhood: string;
  capacity: number;
  received: number;
  open: boolean;
}

export interface AuditEvent {
  id: number;
  time: string;
  message: string;
  level: 'system' | 'success' | 'warning' | 'critical';
}

export const initialBatches: Batch[] = [
  { id: 'SL-2048', food: 'Fresh produce', category: 'Produce', donor: 'Harbor Market', destination: 'Northside Shelter', destinationId: 'SH-01', portions: 420, slackSeconds: 51 * 60 + 24, riderId: 'RD-01' },
  { id: 'SL-2047', food: 'Prepared meals', category: 'Prepared', donor: 'Civic Kitchen', destination: 'Riverside Community', destinationId: 'SH-02', portions: 280, slackSeconds: 34 * 60 + 12, riderId: 'RD-02' },
  { id: 'SL-2046', food: 'Dairy & chilled goods', category: 'Chilled', donor: 'Metro Foods', destination: 'East Ward Center', destinationId: 'SH-03', portions: 360, slackSeconds: 27 * 60 + 41, riderId: 'RD-03' },
  { id: 'SL-2045', food: 'Bakery surplus', category: 'Bakery', donor: 'Little Grain Co.', destination: 'Northside Shelter', destinationId: 'SH-01', portions: 190, slackSeconds: 19 * 60 + 8, riderId: 'RD-01' },
  { id: 'SL-2044', food: 'Produce boxes', category: 'Produce', donor: 'Harbor Market', destination: 'Riverside Community', destinationId: 'SH-02', portions: 315, slackSeconds: 13 * 60 + 52, riderId: null },
];

export const initialRiders: Rider[] = [
  { id: 'RD-01', name: 'Maya Chen', initials: 'MC', vehicle: 'E-bike · 04', status: 'On route', eta: 8, active: true, location: 'Harbor District' },
  { id: 'RD-02', name: 'Luis Ortega', initials: 'LO', vehicle: 'Cargo bike · 12', status: 'On route', eta: 12, active: true, location: 'Civic Center' },
  { id: 'RD-03', name: 'Ari Johnson', initials: 'AJ', vehicle: 'E-bike · 09', status: 'Standby', eta: 4, active: true, location: 'East Ward' },
];

export const initialShelters: Shelter[] = [
  { id: 'SH-01', name: 'Northside Shelter', neighborhood: 'North Quarter', capacity: 1500, received: 420, open: true },
  { id: 'SH-02', name: 'Riverside Community', neighborhood: 'River District', capacity: 1400, received: 280, open: true },
  { id: 'SH-03', name: 'East Ward Center', neighborhood: 'East Ward', capacity: 1200, received: 360, open: true },
];

export const initialAudit: AuditEvent[] = [
  { id: 3, time: '09:32:04', message: 'P90 engine heartbeat confirmed · all routes monitored', level: 'system' },
  { id: 2, time: '09:32:01', message: 'Batch SL-2048 assigned to rider RD-01', level: 'success' },
  { id: 1, time: '09:31:58', message: 'Dispatch simulation initialized · 5 active batches', level: 'system' },
];

export function getBatchStatus(batch: Batch, shelters: Shelter[]): BatchStatus {
  const destinationOpen = shelters.find((shelter) => shelter.id === batch.destinationId)?.open ?? true;
  if (!destinationOpen || batch.slackSeconds <= 16 * 60) return 'Critical';
  if (batch.slackSeconds <= 35 * 60) return 'At Risk';
  return 'Safe';
}

export function formatSlack(seconds: number): string {
  const absoluteSeconds = Math.abs(seconds);
  const minutes = Math.floor(absoluteSeconds / 60);
  const remainder = absoluteSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
}

export function formatSimClock(offsetMinutes: number): string {
  const totalMinutes = (9 * 60 + 32 + offsetMinutes) % (24 * 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} UTC`;
}
