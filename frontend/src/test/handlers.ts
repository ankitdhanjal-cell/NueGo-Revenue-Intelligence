import { http, HttpResponse } from 'msw';
import type { Decision, DeskService } from '../api/types';

/** Test-only API stand-in with a few hand-written services. Nothing here ships with the app. */
const B = '/api/v1';

const base: DeskService = {
  service_id: 'S-SLOW',
  route_label: 'Delhi → Shimla',
  corridor_id: 'R003',
  corridor_label: 'Delhi → Shimla',
  departure_at: '2023-01-25T08:10:00',
  as_of: '2023-01-23T17:45:00',
  hours_to_departure: 38.4,
  coach_type: 'AC Sleeper',
  seats_sold: 6,
  capacity: 40,
  checkpoint: { low: 8.6, mid: 18.2, high: 27.8 },
  gap_to_checkpoint: -12.2,
  fare_on_sale: 385,
  revenue: 2310,
  cost_to_run: 15132,
  margin_now: -12822,
  status: 'behind',
  flags: {},
  rank: 1,
  score_parts: { score: 0.42, behind_part: 0.15, margin_part: 0.7 },
  cancelled: false,
};

const SERVICES: DeskService[] = [
  base,
  { ...base, service_id: 'S-OK', route_label: 'Delhi → Jaipur', status: 'on_pace', rank: 2, seats_sold: 17 },
  {
    ...base,
    service_id: 'S-NOCOST',
    route_label: 'Delhi → Dehradun',
    cost_to_run: null,
    margin_now: null,
    rank: null,
    score_parts: null,
    flags: { cost_missing: true },
  },
];
const CANCELLED: DeskService = {
  ...base,
  service_id: 'S-GONE',
  route_label: 'Delhi → Rishikesh',
  cancelled: true,
  rank: null,
  status: null,
};

export const state = { decisions: [] as Decision[], owners: {} as Record<string, string> };
export const reset = () => {
  state.decisions = [];
  state.owners = {};
};

const suggestion = (id: string) =>
  id === 'S-NOCOST'
    ? {
        service_id: id,
        fare_on_sale: 385,
        engine_fare: 385,
        floor_in_use: 'average',
        floor_value: null,
        rules_version: 1,
        predicted_fare: { low: 330, mid: 400, high: 470, label: 'linear regression prediction' },
        suggested_fare: null,
        blocked_reason: 'COST_MISSING',
        reasons: [],
        flags: { cost_missing: true },
        rating: { avg: null, count: null },
        rivals_either_side: { before: null, after: null },
      }
    : {
        service_id: id,
        fare_on_sale: 385,
        engine_fare: 385,
        floor_in_use: 'average',
        floor_value: 350,
        rules_version: 1,
        predicted_fare: { low: 330, mid: 400, high: 470, label: 'linear regression prediction' },
        suggested_fare: 400,
        blocked_reason: null,
        expected_seats: { low: 10, mid: 15, high: 20 },
        expected_revenue_low: 4000,
        expected_revenue_mid: 6000,
        expected_revenue_high: 8000,
        expected_margin_low: -11132,
        expected_margin_mid: -9132,
        expected_margin_high: -7132,
        change_vs_current: null,
        reasons: [{ code: 'BOOKING_PACE', text: '10 seats behind checkpoint' }],
        flags: {},
        rating: { avg: 4.2, count: 900 },
        rivals_either_side: {
          before: {
            operator: 'FlixBus',
            departure_at: '2023-01-25T07:50:00',
            minutes_from_ours: -20,
            fare: 360,
            gap_to_ours: 25,
            captured_at: '2023-01-23T10:30:00',
          },
          after: null,
        },
      };

const owner = (route_id: string, owner_id: string | null) => ({
  route_id,
  route_label: 'Delhi → Shimla',
  owner_id,
  owner_name: owner_id ? (owner_id === 'admin' ? 'Admin' : 'Pricing analyst 1') : null,
  assigned_by: owner_id ? 'admin' : null,
  assigned_at: owner_id ? '2026-10-28T10:00:00' : null,
});

export const handlers = [
  http.get(`${B}/users`, () =>
    HttpResponse.json({
      items: [
        { id: 'analyst-1', name: 'Pricing analyst 1', role: 'analyst' },
        { id: 'admin', name: 'Admin', role: 'admin' },
      ],
    }),
  ),
  http.get(`${B}/pipeline/status`, () =>
    HttpResponse.json({ last_run: { finished_at: '2026-10-28T06:00:00', status: 'ok', error: null } }),
  ),
  http.get(`${B}/routes`, () =>
    HttpResponse.json({ items: [{ id: 'R003', label: 'Delhi → Shimla', capacity: 40 }] }),
  ),
  http.get(`${B}/desk/summary`, () =>
    HttpResponse.json({ services: 3, behind_checkpoint: 1, in_loss: 2, suggestions_waiting: 2 }),
  ),
  http.get(`${B}/desk/services`, ({ request }) => {
    const empty = new URL(request.url).searchParams.get('window') === 'today';
    return HttpResponse.json({
      items: empty ? [] : SERVICES,
      cancelled: empty ? [] : [CANCELLED],
      page: 1,
      page_size: 50,
      total: empty ? 0 : SERVICES.length,
    });
  }),
  http.get(`${B}/owners`, () => HttpResponse.json({ items: [owner('R003', state.owners.R003 ?? null)] })),
  http.put(`${B}/owners/:id`, async ({ params, request }) => {
    const body = (await request.json()) as { user_id: string | null };
    const id = String(params.id);
    if (body.user_id) state.owners[id] = body.user_id;
    else delete state.owners[id];
    return HttpResponse.json(owner(id, body.user_id));
  }),
  http.get(`${B}/warnings`, ({ request }) => {
    const wanted = new URL(request.url).searchParams.get('owner_id');
    const mine = !wanted || state.owners.R003 === wanted;
    return HttpResponse.json({
      items: !mine
        ? []
        : [
            {
              id: 'w-1',
              service_id: 'S-SLOW',
              corridor_id: 'R003',
              owner_id: state.owners.R003 ?? null,
              route_label: 'Delhi → Shimla · 08:10',
              seat_gap: -12.2,
              checkpoint: { low: 8.6, mid: 18.2, high: 27.8 },
              raised_at: '2023-01-23T17:45:00',
              departure_at: '2023-01-25T08:10:00',
            },
          ],
    });
  }),
  http.get(`${B}/services/:id/suggestion`, ({ params }) => HttpResponse.json(suggestion(String(params.id)))),
  http.get(`${B}/services/:id/whatif`, () =>
    HttpResponse.json({
      service_id: 'S-SLOW',
      flags: { price_response_not_reliable: true },
      rows: [
        {
          fare: 350,
          seats: { low: 5, mid: 10, high: 15 },
          revenue: { low: 1750, mid: 3500, high: 5250 },
          margin: null,
          blocked_by: ['BELOW_FLOOR'],
          is_current: false,
          is_suggested: false,
        },
        {
          fare: 400,
          seats: { low: 10, mid: 15, high: 20 },
          revenue: { low: 4000, mid: 6000, high: 8000 },
          margin: null,
          blocked_by: [],
          is_current: true,
          is_suggested: true,
        },
      ],
    }),
  ),
  http.get(`${B}/rivals/services/:id`, ({ params }) =>
    HttpResponse.json({
      service_id: params.id,
      our_fare_on_sale: 875,
      rivals: [],
      nearby_days: 3,
      nearby_fares: [
        {
          operator: 'HRTC',
          departure_at: '2026-11-08 21:00:00',
          minutes_from_ours: -1515,
          fare: 820,
          gap_to_ours: 55,
          captured_at: '2026-11-06 10:30:00',
          captured_after_prediction_time: true,
        },
      ],
      route_rating: { avg: 4.2, count: 940 },
      flags: { rival_missing: true },
      note: 'No rival departs within 30 minutes of ours. The nearest rival departure on this route is 3 h 20 min away. Nothing is estimated.',
    }),
  ),
  http.get(`${B}/pnl/services/:id/trend`, () =>
    HttpResponse.json({
      weekday: 'Wednesday',
      points: [{ departure_at: '2022-12-28T08:10:00', load_pct: 62.5, revenue: 9625, margin: -1200 }],
    }),
  ),
  http.get(`${B}/pnl/services/:id`, ({ params }) =>
    HttpResponse.json({
      service_id: params.id,
      route_id: 'R003',
      departure_at: '2023-01-25T08:10:00',
      hours_to_departure: 38.4,
      seats_sold: 6,
      total_seats: 40,
      revenue: 2310,
      cost_to_run: 15132,
      profit: -12822,
      margin_status: 'ok',
      floor_in_use: 'average',
      checkpoint_status: 'ok',
      expected_margin_low: -9000,
      expected_margin_mid: -8000,
      expected_margin_high: -7000,
    }),
  ),
  http.get(`${B}/forecast/services/:id/curve`, ({ params }) =>
    HttpResponse.json({
      service_id: params.id,
      capacity: 40,
      days_to_go_at_snapshot: 1.6,
      actual_seats_sold: 6,
      actual: { points: [{ days_to_go: 1.6, seats_sold: 6 }] },
      checkpoints: [],
      forecast_to_departure: { seats: { low: 8.6, mid: 18.2, high: 27.8 } },
      flags: { no_history: true },
    }),
  ),
  http.get(`${B}/decisions`, ({ request }) => {
    const id = new URL(request.url).searchParams.get('service_id');
    return HttpResponse.json({ items: state.decisions.filter((d) => !id || d.service_id === id) });
  }),
  http.post(`${B}/fare/predict`, async ({ request }) => {
    const body = (await request.json()) as { holiday_score: number };
    const mid = 500 + 140 * body.holiday_score;
    return HttpResponse.json({
      route_id: 'R003',
      model_version: 'linear regression fare model v2',
      fare_low: mid - 46,
      fare_mid: mid,
      fare_high: mid + 46,
      gap_to_engine: null,
      holiday_score: body.holiday_score,
      insufficient_data: false,
      note: 'Reference only.',
    });
  }),
  http.post(`${B}/suggestions/:id/decision`, async ({ params, request }) => {
    const id = String(params.id);
    const prior = state.decisions.find((d) => d.service_id === id);
    if (prior)
      return HttpResponse.json(
        { detail: `Already decided by ${prior.user} on 25 Jan 2023, 08:10 AM.` },
        { status: 409 },
      );
    const body = (await request.json()) as { action: Decision['action']; fare?: number; reason?: string };
    const d: Decision = {
      id: String(state.decisions.length + 1),
      service_id: id,
      user: 'Pricing analyst 1',
      at: '2023-01-25T08:10:00',
      action: body.action,
      fare: body.fare ?? null,
      reason: body.reason ?? null,
      category: null,
      engine_fare: 385,
      our_fare: 400,
      outcome: null,
      rules_version: 1,
      model_version: 'linear regression fare model',
      predicted_fare: 400,
      floor_value: 350,
    };
    state.decisions.unshift(d);
    return HttpResponse.json(d, { status: 201 });
  }),
];
