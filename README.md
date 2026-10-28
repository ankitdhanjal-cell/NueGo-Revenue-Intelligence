# NueGo Revenue Intelligence (POC): Module A, fare and seat prediction

Person 1 scope: Module A service P&L, reference fare prediction, expected seats sold.
Nothing here suggests or changes a fare, and nothing is written to an external system.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d                     # Postgres (pi_beta) + pgAdmin on :8090; reads .env
python -m scripts.load_raw_csv           # raw CSVs -> raw_route_details, raw_competitor_data
python -m scripts.build_clean_tables     # -> services, competitor_fares
python -m scripts.compute_fare_predictions
python -m scripts.compute_forecasts      # must run before compute_pnl
python -m scripts.compute_pnl
uvicorn app.main:app --reload            # docs at http://localhost:8000/docs
python -m pytest -q
```
Models served: `models/nuego_fare_model.pkl`, `models/nuego_seats_sold_model.pkl` (team Decision Trees, used as-is).
Their AC/Sleeper inputs come from `data/processed/nuego_train_241_ac_sleeper.csv`; services without a
match get no prediction. Settings in `.env`: `TRIPS_PER_ROUTE_MONTH` (default 30, an assumption),
`RANK_W_BEHIND`, `RANK_W_MARGIN` (default 0.5 each), `FLOOR_SWITCH_HOURS` (default 24, an assumption: hours before departure when the marginal floor takes over).

## API
| Endpoint | Returns |
|---|---|
| `GET /pnl/services/{id}` | revenue, cost to run, margin now, average floor (cost ÷ expected seats, low/mid/high), marginal floor ("cost missing"), `floor_in_use` + switch point, checkpoint status, expected margin low/mid/high |
| `GET /pnl/totals?group_by=corridor\|date` | totals (cancelled left out); coach_type / channel -> 422, not in data |
| `GET /pnl/cancelled` | cancelled services, listed separately |
| `GET /pnl/ranking?limit=` | attention ranking with visible score parts and excluded services |
| `GET /pnl/services/{id}/trend` | same route + weekday, previous 8 weeks, or "no history" |
| `GET /services/{id}/fare-prediction` | reference fare low/mid/high, model version, gap to engine fare |
| `POST /fare/predict` | same for a new request (`route_id, departure_at, available_seats, ac, sleeper, as_of`) |
| `GET /forecast/services/{id}/curve` | expected seats sold low/mid/high, gap, behind-checkpoint flag |

```bash
curl localhost:8000/pnl/services/BKG2023011
curl "localhost:8000/pnl/ranking?limit=5"
curl localhost:8000/services/BKG2023011/fare-prediction
curl localhost:8000/forecast/services/BKG2023011/curve
curl -X POST localhost:8000/fare/predict -H 'content-type: application/json' \
  -d '{"route_id":"R001","departure_at":"2026-03-01T08:00","available_seats":20,"ac":1,"sleeper":0,"engine_fare":500}'
```

## Models and ranges
No model is trained here: the two team pickles are used as they are. The low/high range is the
80th percentile of the pickle's own errors on the data (`range_basis` says so). Those errors are
in-sample, so the range is optimistic. A one-off check that refit the same trees on older rows and
tested on the newest 20% gave: fare MAE 85 INR vs 91 INR route-median baseline (about +-125 INR
range, newer fares ~77 INR above prediction); seats MAE 7.05 vs 7.24 route-mean baseline (about
+-12.8 seats). So expect the models to be only slightly better than a simple average.

## Known limits
- Only 15 of 245 services have a competitor fare captured before their booking time (+-3 days, same route) -> most fare predictions are flagged `insufficient_data`.
- One snapshot per service and no link between seats sold and days-to-go -> no booking-curve shape is returned (`curve: null`); observed pooled points are returned instead.
- Crew cost is a route-level monthly figure, split by scheduled hours over an assumed 30 trips/month.
- Marginal floor needs channel commission, which is not in the data -> "cost missing". Energy and channel are also absent, so totals by channel / coach type are unavailable.
- Expected margin uses the seat forecast as a stand-in for Module B.
- Coach type for 5 services (original sample rows) is unknown and never guessed.


---

# Module B (Person 2): price response and fare suggestions

Advice only. A fare is never changed and nothing is written to any external system.
Module B reads Module A's tables (`pnl_services`, `seat_forecasts`, `fare_predictions`, `services`,
`competitor_fares`) and adds one table, `pricing_rules`. No Module A table or column was changed.

## Run order (additions)
```bash
python -m scripts.seed_rules      # optional: creates pricing_rules + default row (GET /rules also does it)
python -m pytest -q               # 120 tests; Module B tests use a throwaway SQLite database where they write
```

## Module B endpoints
| Endpoint | Returns |
|---|---|
| `GET /rules` | active pricing rules and allowed fare steps (newest version, read from the DB on every request) |
| `PUT /rules` | saves a NEW version (old rows kept); 422 on bad input. Applies on the next request, no restart |
| `GET /rivals/services/{id}?as_of=` | rival departures within +-30 min as "Rival A", "Rival B"...; fare, gap to ours, route rating. `as_of` defaults to the booking time |
| `GET /pricing/elasticity?route_id=&slot=&dtg_band=&day_type=` | slope of seats vs fare (low/mid/high) or "not enough data", with `enough_data` and `reason` |
| `GET /forecast/services/{id}/curve` | Module A's fields unchanged, plus `capacity`, `actual`, `band` (p10/p50/p90), `band_status`, `checkpoints`, `forecast_to_departure`, `flags` |
| `GET /services/{id}/suggestion?minutes_since_last_change=` | suggested fare from the allowed steps, seats / revenue / margin ranges, 1 to 3 reasons, floor, engine fare, flags |

```bash
curl localhost:8000/rules
curl -X PUT localhost:8000/rules -H 'content-type: application/json' -d '{"floor_switch_hours":24,"ceiling":1200,
  "state_cap":null,"max_change_pct":15,"min_minutes_between_changes":240,"seats_weight":0,"fare_steps":[300,310,320],"updated_by":"ops"}'
curl localhost:8000/rivals/services/BKG2023011
curl "localhost:8000/pricing/elasticity?route_id=R001&dtg_band=7-14"
curl localhost:8000/services/BKG2023013/suggestion
```

## Rules (`pricing_rules`)
One row per version: `floor_switch_hours`, `ceiling`, `state_cap` (null = none), `max_change_pct`,
`min_minutes_between_changes`, `seats_weight` (INR value of one extra expected seat), `fare_steps`, `updated_by`, `updated_at`.
**`floor_switch_hours` now lives here.** `app/config.py` `FLOOR_SWITCH_HOURS` is only the seed for the first row;
Module A should read `rules.active_rules(engine)["floor_switch_hours"]` and the env setting can then be removed.
The default values (ceiling 1500, no state cap, 15 %, 240 minutes, seats weight 0, steps every INR 10 from 200 to 1500)
are **assumptions** (`DEFAULT_RULES` in `app/config.py`). Rule check: `rules.check_fare(fare, RuleContext)` returns codes
`NOT_A_FARE_STEP, BELOW_FLOOR, ABOVE_CEILING, ABOVE_STATE_CAP, STEP_TOO_LARGE, TOO_SOON` (pure, reusable).

## How the suggestion is made
1. No suggestion (with `blocked_reason`): `CANCELLED`, `COST_MISSING`, `NO_FLOOR`, `NO_SEAT_FORECAST`, `NO_ALLOWED_FARE`.
   `NO_ALLOWED_FARE` carries `blocked_detail` (the floor, the highest fare the other rules allow, rules broken per step).
2. Floor: `floor_in_use` is the average floor (mid) until `hours_to_departure <= floor_switch_hours`, then the marginal floor.
   The marginal floor is null today (no channel commission), so near departure it **falls back to the average floor (mid)**
   and sets `flags.floor_missing`. The floor is never skipped. No floor at all = no suggestion.
3. Candidates = fare steps that pass every rule. Seats at each candidate come from the team seat model (`seat_model.predict`).
4. **Price response guard.** The team seat model says MORE fare means MORE seats (fare follows demand in this data), so it cannot
   rank fares. Fares are ranked by score (margin mid + seats_weight x seats mid) only when expected seats fall as the fare rises
   (`price_response: "used"`). Otherwise (`"not_reliable"`, or `"not_assessed"` with one candidate) the allowed fare closest to
   the current one is suggested (ties go to the lower), `change_vs_current` is null and no gain is claimed.
5. Ranges: `expected_seats`, `expected_revenue_*`, `expected_margin_*` (low/mid/high, same names as `pnl_services`).
   `change_vs_current` uses interval subtraction, so it is wider than either range.
6. The reference fare (`fare_predictions`) is shown as `reference_fare`, labelled, and never used.
7. Prediction time = the booking snapshot (`services.booking_time`); rival rows captured later are ignored.

## Reasons (fixed list in `app/reasons.py`)
`BOOKING_PACE` (seats sold below p10 / above p90 of similar past services, or the on-pace / no-history text),
`RIVAL_GAP` (fare >10 % from the median rival fare), `FESTIVAL` (holiday_score >= 0.5), `COST_FLOOR` (the floor is what
limited the fare), `RATING` (rating >= 4.3 and above rivals, or <= 3.8 and below). In that priority, at most 3, text from templates.


## Results on the current data (245 services)
Suggestions: 49 made (44 `not_reliable`, 3 `used`, 2 `not_assessed`), 172 `NO_ALLOWED_FARE`, 21 cancelled, 3 `NO_FLOOR`.
Rivals: only 4 of 245 services have a rival captured before booking time. Elasticity: the observed slope is **positive**
(for example R001 +2.2), reported as `enough_data: false, reason: fare_follows_demand`; narrower segments have < 30 services.
Booking curve: seats sold vs days-to-go correlation is 0.09 and the band means are not monotonic, so `curve` stays null.

## Known limits and assumptions (Module B)
- The average floor (cost / expected seats) is above the fare on sale for 79 % of services and beyond the 15 % step limit for
  75 %. With the floor and the step limit both enforced, those services get `NO_ALLOWED_FARE`. That is correct behaviour.
- No fare-change history exists, so "shortest time between changes" is only checked if `minutes_since_last_change` is passed
  (`flags.last_change_unknown` otherwise).
- No service is within 24 h of departure in the data, so the marginal floor is never the one in use today.
- `PUT /rules` has **no authentication** (the repo has none). Add auth before exposing it.
- Thresholds that are assumptions: `MIN_ELASTICITY_SERVICES` 30, `MIN_ELASTICITY_FARES` 5, `MIN_BAND_SERVICES` 4 (`app/config.py`).
- Slot / day type are derived: morning 05-12, afternoon 12-17, evening 17-20, else night; holiday if holiday_score >= 0.5, else weekend / weekday.

## Open questions for GreenCell
1. Real ceiling, state cap, largest change per step, minimum time between changes, and the fare step list.
2. Is the cost floor (average cost / expected seats) the right basis? It sits above the sale fare for most services.
3. Channel commission data (for the marginal floor) and the fare-change log (for the time rule).
4. Which floor switch point (hours before departure) applies.
5. A fare experiment or longer history, so price response can be estimated rather than seen as a correlation.
6. Who may call `PUT /rules`.


---

## Update: price from the notebook model, real desk data, no mock data

**Price.** The suggested fare now comes from the decision tree in `notebooks/decision_tree.ipynb` (`app/fare_notebook.py`,
model `models/nuego_fare_model.pkl`). Competitor inputs follow the notebook: min / median / mean competitor fare for the route over
ALL competitor rows (the notebook's route-level fallback; its AC/Sleeper-level file `competitor_preprocessed3.csv` is not in the repo).
This is not cut off by capture time, unlike `app/fare_model.py`, so for past services it sees later competitor fares.
The suggestion is the allowed fare step closest to the predicted fare, inside every pricing rule. The old "reference fare, never the
suggestion" rule no longer applies. `seats_weight` is kept in the rules but is not used while the fare comes from the tree.
`POST /fare/predict` uses the same method (its `as_of` is accepted but ignored). No coach type means no prediction.
Notebook test split: MAE INR 70.87, R2 0.772; the range here is the model's in-sample error (optimistic).

**New endpoints** (all on the real tables): `GET /desk/summary`, `GET /desk/services` (windows today / tomorrow / next30 / earlier / all,
real Asia/Kolkata dates), `GET /warnings`, `GET /services/{id}/whatif`, `GET /decisions`, `POST /suggestions/{id}/decision`
(stored in the new `decisions` table; 409 if already decided), `GET /routes`, `GET /users`.
`PUT /rules` is now admin-only (`X-User-Id`; 401 / 403 otherwise). Users are placeholders in `app/config.py`.

**Dates.** The 245 services depart between 25 Jan 2023 and 26 Dec 2026, so most are in the past. Seat counts are booking-time snapshots.
