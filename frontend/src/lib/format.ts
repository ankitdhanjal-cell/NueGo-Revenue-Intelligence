import type { Range, Rating } from '../api/types';

export type RangeFormat = 'inr' | 'seats' | 'pct' | 'ratio';

const inr0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** The only money formatter: ₹1,23,456.50. Missing values give an em dash, never ₹0. */
export function formatINR(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  const v = Math.round(value * 100) / 100;
  return (Number.isInteger(v) ? inr0 : inr2).format(v);
}

export function formatSeats(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  const v = Math.round(value * 10) / 10;
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${(Math.round(value * 10) / 10).toString()}%`;
}

/** "4.2 (1,234 ratings)", or an em dash when there is no rating. */
export function formatRating(r: Rating): string {
  if (r.avg == null) return '—';
  return r.count == null
    ? r.avg.toFixed(1)
    : `${r.avg.toFixed(1)} (${r.count.toLocaleString('en-IN')} ratings)`;
}

function formatRatio(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return (Math.round(value * 100) / 100).toFixed(2);
}

const formatters: Record<RangeFormat, (v: number | null | undefined) => string> = {
  inr: formatINR,
  seats: formatSeats,
  pct: formatPct,
  ratio: formatRatio,
};

/** "mid (low–high)". There is no way to format a range without its bounds. */
export function formatRange(range: Range, kind: RangeFormat): string {
  const f = formatters[kind];
  const dash = range.low < 0 || range.high < 0 ? ' – ' : '–'; // spaces keep "-₹5 – -₹2" readable
  return `${f(range.mid)} (${f(range.low)}${dash}${f(range.high)})`;
}

/** "2 d 4 h" from one day out, "3 h 20 m" inside the last day. */
export function formatTimeToGo(hours: number): string {
  if (Number.isNaN(hours)) return '—';
  if (hours <= 0) return 'Departed';
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days} d ${Math.floor(hours - days * 24)} h`;
  }
  const h = Math.floor(hours);
  return `${h} h ${Math.floor((hours - h) * 60)} m`;
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
}
