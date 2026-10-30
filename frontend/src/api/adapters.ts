/**
 * The real API has no response models, so these raw shapes are written by hand from app/*.py.
 * Each adapter turns one raw response into the shape the UI uses (see types.ts).
 */
import type {
  Curve,
  Elasticity,
  FarePrediction,
  Flags,
  Pnl,
  Range,
  NearbyFare,
  Rival,
  Rivals,
  Suggestion,
  Totals,
} from './types';

type RawFlags = Record<string, boolean | undefined>;

function mapFlags(raw: RawFlags | undefined): Flags {
  const f = raw ?? {};
  return {
    cost_missing: f.cost_missing,
    no_history: f.no_history,
    rival_missing: f.rival_missing,
    floor_missing: f.floor_missing,
    low_confidence: f.insufficient_data || f.price_response_not_reliable || f.low_confidence,
  };
}

function rangeOf(
  low: number | null | undefined,
  mid: number | null | undefined,
  high: number | null | undefined,
): Range | null {
  return low == null || mid == null || high == null ? null : { low, mid, high };
}

interface RawRange {
  low: number | null;
  mid: number | null;
  high: number | null;
}
const fromRaw = (r: RawRange | null | undefined): Range | null => (r ? rangeOf(r.low, r.mid, r.high) : null);

export interface RawSuggestion {
  service_id: string;
  fare_on_sale: number | null;
  engine_fare: number | null;
  floor_in_use: string;
  floor_value: number | null;
  rules_version: number;
  predicted_fare: {
    low: number;
    mid: number;
    high: number;
    label: string;
  } | null;
  coach_type?: string | null;
  suggested_fare: number | null;
  blocked_reason: string | null;
  blocked_detail?: Suggestion['blocked_detail'];
  expected_seats?: RawRange;
  expected_revenue_low?: number;
  expected_revenue_mid?: number;
  expected_revenue_high?: number;
  expected_margin_low?: number;
  expected_margin_mid?: number;
  expected_margin_high?: number;
  change_vs_current?: { extra_seats: Range; margin_change: Range } | null;
  reasons: { code: string; text: string }[];
  flags: RawFlags;
  rating: Suggestion['rating'];
  rivals_either_side: Suggestion['rivals_either_side'];
}

export function adaptSuggestion(raw: RawSuggestion): Suggestion {
  return {
    suggestion_id: raw.service_id,
    service_id: raw.service_id,
    coach_type: raw.coach_type ?? null,
    suggested_fare: raw.suggested_fare,
    blocked_reason: raw.blocked_reason,
    blocked_detail: raw.blocked_detail ?? null,
    engine_fare: raw.engine_fare ?? raw.fare_on_sale,
    predicted_fare: raw.predicted_fare,
    floor: { type: raw.floor_in_use, value: raw.floor_value },
    expected_seats: fromRaw(raw.expected_seats),
    expected_revenue: rangeOf(raw.expected_revenue_low, raw.expected_revenue_mid, raw.expected_revenue_high),
    expected_margin: rangeOf(raw.expected_margin_low, raw.expected_margin_mid, raw.expected_margin_high),
    extra_seats: raw.change_vs_current?.extra_seats ?? null,
    margin_change: raw.change_vs_current?.margin_change ?? null,
    reasons: raw.reasons,
    flags: mapFlags(raw.flags),
    rules_version: raw.rules_version,
    rating: raw.rating,
    rivals_either_side: raw.rivals_either_side,
  };
}

export interface RawCurve {
  service_id: string;
  capacity?: number | null;
  days_to_go_at_snapshot: number | null;
  actual_seats_sold: number | null;
  curve_note?: string | null;
  actual?: { points: { days_to_go: number; seats_sold: number }[] };
  checkpoints?: {
    dtg_band: string;
    p10: number | null;
    p50: number | null;
    p90: number | null;
    status: string;
  }[];
  forecast_to_departure?: { seats: RawRange };
  flags?: RawFlags;
}

const BAND_MID_DTG: Record<string, number> = { '0-3': 1.5, '3-7': 5, '7-14': 10.5, '14+': 20 };

export function adaptCurve(raw: RawCurve): Curve {
  const actual = (raw.actual?.points ?? []).map((p) => ({ dtg: p.days_to_go, seats: p.seats_sold }));
  const band = (raw.checkpoints ?? []).flatMap((c) =>
    c.status === 'ok' && c.p10 != null && c.p50 != null && c.p90 != null
      ? [{ dtg: BAND_MID_DTG[c.dtg_band] ?? 0, p10: c.p10, p50: c.p50, p90: c.p90 }]
      : [],
  );
  const end = fromRaw(raw.forecast_to_departure?.seats);
  const today = actual[0];
  const forecast = end
    ? [
        ...(today
          ? [{ dtg: today.dtg, seats: { low: today.seats, mid: today.seats, high: today.seats } }]
          : []),
        { dtg: 0, seats: end },
      ]
    : [];
  const flags = mapFlags(raw.flags);
  return {
    service_id: raw.service_id,
    capacity: raw.capacity ?? null,
    actual,
    band,
    forecast,
    today_dtg: raw.days_to_go_at_snapshot,
    curve_note: raw.curve_note ?? null,
    flags: { ...flags, no_history: band.length === 0 || flags.no_history },
  };
}

export interface RawElasticity {
  elasticity: RawRange | null;
  enough_data: boolean;
  reason: string | null;
  n_services: number;
  flags?: RawFlags;
}

export function adaptElasticity(raw: RawElasticity): Elasticity {
  return {
    elasticity: fromRaw(raw.elasticity),
    enough_data: raw.enough_data,
    reason: raw.reason,
    n_services: raw.n_services,
    flags: mapFlags(raw.flags),
  };
}

export interface RawRivals {
  service_id: string;
  our_fare_on_sale: number | null;
  rivals: Rival[];
  nearby_days: number;
  nearby_fares: NearbyFare[];
  route_rating: { avg: number | null; count: number | null };
  flags: RawFlags;
  note: string;
}

export function adaptRivals(raw: RawRivals): Rivals {
  return {
    service_id: raw.service_id,
    our_fare: raw.our_fare_on_sale,
    rivals: raw.rivals,
    nearby_days: raw.nearby_days,
    nearby_fares: raw.nearby_fares,
    rating: raw.route_rating,
    flags: mapFlags(raw.flags),
    note: raw.note,
  };
}

export interface RawPnl {
  service_id: string;
  route_id: string;
  departure_at: string;
  hours_to_departure: number;
  seats_sold: number;
  total_seats: number;
  revenue: number;
  cost_to_run: number | null;
  profit: number | null;
  margin_status: string;
  floor_in_use: string;
  checkpoint_status: string;
  expected_margin_low: number | null;
  expected_margin_mid: number | null;
  expected_margin_high: number | null;
}

export function adaptPnl(raw: RawPnl): Pnl {
  return {
    service_id: raw.service_id,
    route_id: raw.route_id,
    departure_at: raw.departure_at,
    hours_to_departure: raw.hours_to_departure,
    seats_sold: raw.seats_sold,
    total_seats: raw.total_seats,
    revenue: raw.revenue,
    cost_to_run: raw.cost_to_run,
    margin_now: raw.profit,
    expected_margin: rangeOf(raw.expected_margin_low, raw.expected_margin_mid, raw.expected_margin_high),
    floor_in_use: raw.floor_in_use,
    checkpoint_status: raw.checkpoint_status,
    flags: { cost_missing: raw.margin_status === 'cost missing', no_history: raw.checkpoint_status !== 'ok' },
  };
}

export interface RawTotals {
  group_by: string;
  rows: Record<string, string | number | null>[];
}

export function adaptTotals(raw: RawTotals): Totals {
  return {
    group_by: raw.group_by,
    rows: raw.rows.map((r) => ({
      group: String(r[raw.group_by] ?? '—'),
      services: Number(r.services),
      revenue: Number(r.revenue),
      cost_to_run: Number(r.cost_to_run),
      profit: Number(r.profit),
      margin_pct: r.margin_pct == null ? null : Number(r.margin_pct),
    })),
  };
}

export interface RawFarePrediction {
  fare_low: number | null;
  fare_mid: number | null;
  fare_high: number | null;
  model_version: string;
  insufficient_data: boolean;
  note: string;
}

export function adaptFarePrediction(raw: RawFarePrediction): FarePrediction | null {
  const fare = rangeOf(raw.fare_low, raw.fare_mid, raw.fare_high);
  return fare
    ? {
        fare,
        model_version: raw.model_version,
        insufficient_data: raw.insufficient_data,
        note: raw.note,
      }
    : null;
}
