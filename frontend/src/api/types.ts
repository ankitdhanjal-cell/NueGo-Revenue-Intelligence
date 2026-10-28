/** Shapes the UI works with. The adapters turn the real API's flat fields into these. */
export interface Range {
  low: number;
  mid: number;
  high: number;
}

export type FlagName =
  'cost_missing' | 'no_history' | 'low_confidence' | 'rival_missing' | 'floor_missing' | 'sold_out';
export type Flags = Partial<Record<FlagName, boolean>>;
export type Status = 'behind' | 'on_pace' | 'ahead';
export type Role = 'analyst' | 'admin';

export interface User {
  id: string;
  name: string;
  role: Role;
}

export interface Reason {
  code: string;
  text: string;
}

export interface DeskSummary {
  services: number;
  behind_checkpoint: number;
  in_loss: number;
  suggestions_waiting: number;
}

export interface DeskService {
  service_id: string;
  route_label: string;
  corridor_id: string;
  corridor_label: string;
  departure_at: string;
  as_of: string;
  hours_to_departure: number | null;
  coach_type: string | null;
  seats_sold: number;
  capacity: number;
  checkpoint: Range | null;
  gap_to_checkpoint: number | null;
  fare_on_sale: number | null;
  revenue: number | null;
  cost_to_run: number | null;
  margin_now: number | null;
  status: Status | null;
  flags: Flags;
  rank: number | null;
  score_parts: { score: number; behind_part: number; margin_part: number } | null;
  cancelled: boolean;
}

export interface DeskPage {
  items: DeskService[];
  cancelled: DeskService[];
  page: number;
  page_size: number;
  total: number;
}

export interface DeskFilters {
  window: 'today' | 'tomorrow' | 'next30' | 'earlier';
  corridor_id: string;
  page: number;
}

export interface RouteInfo {
  id: string;
  label: string;
  capacity: number;
}

export interface BlockedDetail {
  floor_value: number | null;
  highest_fare_allowed_ignoring_floor: number | null;
  fare_steps_broken_by_rule: Record<string, number>;
}

export interface Suggestion {
  suggestion_id: string;
  service_id: string;
  coach_type: string | null;
  suggested_fare: number | null;
  blocked_reason: string | null;
  blocked_detail: BlockedDetail | null;
  engine_fare: number | null;
  predicted_fare: (Range & { label: string; competitor_rows_used?: number }) | null;
  floor: { type: string; value: number | null } | null;
  expected_seats: Range | null;
  expected_revenue: Range | null;
  expected_margin: Range | null;
  extra_seats: Range | null;
  margin_change: Range | null;
  reasons: Reason[];
  flags: Flags;
  rules_version: number;
  rating: Rating;
  rivals_either_side: { before: Rival | null; after: Rival | null };
}

export interface Rating {
  avg: number | null;
  count: number | null;
}

export interface WhatIfRow {
  fare: number;
  seats: Range;
  revenue: Range;
  margin: Range | null;
  blocked_by: string[];
  is_current: boolean;
  is_suggested: boolean;
}

export interface WhatIf {
  service_id: string;
  rows: WhatIfRow[];
  flags: Flags & { price_response_not_reliable?: boolean };
}

export type DecisionAction = 'approve' | 'change' | 'reject' | 'wrong';

export interface DecisionIn {
  action: DecisionAction;
  fare?: number;
  reason?: string;
  category?: string;
}

export interface Decision {
  id: string;
  service_id: string;
  user: string;
  at: string;
  action: DecisionAction;
  fare: number | null;
  reason: string | null;
  category: string | null;
  engine_fare: number | null;
  our_fare: number | null;
  outcome: { final_seats: number; revenue: number } | null;
  rules_version: number | null;
  model_version: string | null;
  predicted_fare: number | null;
  floor_value: number | null;
}

export interface Owner {
  route_id: string;
  route_label: string;
  owner_id: string | null;
  owner_name: string | null;
  assigned_by: string | null;
  assigned_at: string | null;
}

export interface Warning {
  id: string;
  service_id: string;
  corridor_id: string;
  owner_id: string | null;
  route_label: string;
  seat_gap: number;
  checkpoint: Range;
  raised_at: string;
  departure_at: string;
}

export interface CurvePoint {
  dtg: number;
  seats: number;
}
export interface BandPoint {
  dtg: number;
  p10: number;
  p50: number;
  p90: number;
}
export interface ForecastPoint {
  dtg: number;
  seats: Range;
}
export interface Curve {
  service_id: string;
  capacity: number | null;
  actual: CurvePoint[];
  band: BandPoint[];
  forecast: ForecastPoint[];
  today_dtg: number | null;
  curve_note: string | null;
  flags: Flags;
}

export interface Elasticity {
  elasticity: Range | null;
  enough_data: boolean;
  reason: string | null;
  n_services: number;
  flags: Flags;
}

export interface Rival {
  label: string;
  departure_at: string;
  minutes_from_ours: number;
  fare: number;
  gap_to_ours: number | null;
}
export interface Rivals {
  service_id: string;
  rivals: Rival[];
  rating: Rating;
  flags: Flags;
}

export interface PipelineStatus {
  last_run: { finished_at: string; status: 'ok' | 'failed'; error: string | null } | null;
}

export interface Trend {
  weekday: string;
  points: { departure_at: string; load_pct: number; revenue: number; margin: number | null }[];
}

export interface Pnl {
  service_id: string;
  route_id: string;
  departure_at: string;
  hours_to_departure: number;
  seats_sold: number;
  total_seats: number;
  revenue: number;
  cost_to_run: number | null;
  margin_now: number | null;
  expected_margin: Range | null;
  floor_in_use: string;
  checkpoint_status: string;
  flags: Flags;
}

export interface TotalsRow {
  group: string;
  services: number;
  revenue: number;
  cost_to_run: number;
  profit: number;
  margin_pct: number | null;
}
export interface Totals {
  group_by: string;
  rows: TotalsRow[];
}

export interface Rules {
  version: number;
  floor_switch_hours: number;
  ceiling: number;
  state_cap: number | null;
  max_change_pct: number;
  min_minutes_between_changes: number;
  seats_weight: number;
  fare_steps: number[];
  updated_by: string | null;
  updated_at: string;
}
export type RulesInput = Omit<Rules, 'version' | 'updated_at'>;

export interface FarePrediction {
  fare: Range;
  model_version: string;
  insufficient_data: boolean;
  competitor_rows_used: number;
  assumptions: string | null;
  note: string;
}
export interface FarePredictInput {
  route_id: string;
  departure_at: string;
  available_seats: number;
  ac: 0 | 1;
  sleeper: 0 | 1;
}
