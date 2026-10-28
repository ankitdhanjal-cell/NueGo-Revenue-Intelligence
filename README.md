# NueGo Revenue Intelligence (POC)

A revenue tool for NueGo's pricing team. For every bus service it shows the profit or loss against the cost to run,
how many seats it should have sold by now, and a suggested fare with the reasons. A person approves, changes or
rejects each suggestion.

**It only advises.** It never changes a fare, never writes to GreenCell's or NueGo's systems, and sends nothing
anywhere. Decisions are recorded in this app's own database.

| Module | What it does |
|---|---|
| A: service P&L | Revenue, cost to run, margin and cost floors per service; attention ranking; totals; 8-week trend |
| B: prediction and suggestions | Predicted fare (Linear Regression), suggested fare inside the pricing rules, reasons, rivals, rating, price response |
| C: alerts, what-if, decisions | Behind-pace alerts by owner (in-app only), what-if table, decision record with outcome |

The React screens are in [`frontend/`](frontend/README.md).

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d                       # local Postgres + pgAdmin on :8090 (or point DATABASE_URL in .env elsewhere)

# build the tables once, in this order
python -m scripts.load_raw_csv             # raw CSVs -> raw_route_details, raw_competitor_data (never overwrites)
python -m scripts.build_clean_tables       # -> services, competitor_fares
python -m scripts.compute_forecasts        # -> seat_forecasts, seat_observed_points
python -m scripts.compute_pnl              # -> pnl_services (needs seat_forecasts)

uvicorn app.main:app --port 8001           # the frontend proxies to 8001; API docs at /docs
python -m pytest -q                        # tests that write use a throwaway SQLite database
```

**Later refreshes:** `python -m scripts.refresh` runs the forecasts and then the P&L, and records the run in
`pipeline_runs`. The sidebar shows when it last ran. Daily cron:
`0 6 * * * cd /path/to/repo && .venv/bin/python -m scripts.refresh`.

| Other scripts | Purpose |
|---|---|
| `scripts.train_linear_fare_model` | Re-trains the fare model and saves `models/nuego_fare_model_linear.pkl` |
| `scripts.seed_rules` | Creates `pricing_rules` with the default row (`GET /rules` also does this) |
| `scripts.load_outcomes path.csv` | Loads real final seats and revenue (`service_id, final_seats, final_revenue`) |
| `scripts.export_decisions [out.csv]` | Writes decisions with outcomes to a CSV for retraining (read-only) |
| `scripts.compute_fare_predictions` | Legacy: older as-of fare predictions into `fare_predictions` |

**Settings in `.env`:**
- `DATABASE_URL`
- `TRIPS_PER_ROUTE_MONTH` (default 30, an assumption)
- `RANK_W_BEHIND`, `RANK_W_MARGIN` (0.5 each)
- `FLOOR_SWITCH_HOURS` (24, the seed for the first rules row)
- `MIN_ELASTICITY_SERVICES` (30), `MIN_ELASTICITY_FARES` (5), `MIN_BAND_SERVICES` (4)

## Who can do what
There is no login yet. The UI sends `X-User-Id`, chosen from the placeholder users in `app/config.py` (`analyst-1`,
`analyst-2`, `admin`).
- Recording a decision and reading owners need a known user (401 otherwise).
- Changing the rules or the route owners needs the admin (403 otherwise).

Replace this with real authentication before real use.

## API
### Module A: service P&L
| Endpoint | Returns |
|---|---|
| `GET /pnl/services/{id}` | Revenue, cost to run, margin now, average floor (cost ÷ expected seats), marginal floor, floor in use, checkpoint status, expected margin range |
| `GET /pnl/totals?group_by=corridor\|date\|coach_type` | Totals with cancelled services left out. Coach type is "Unknown" when not in the data. `channel` gives 422 (not in the data) |
| `GET /pnl/services/{id}/trend` | Same route and weekday over the previous 8 weeks: load %, revenue, margin |
| `GET /pnl/ranking?limit=` | Attention ranking with the score parts and the excluded services. Not used by the UI |
| `GET /pnl/cancelled` | Cancelled services, listed separately. Not used by the UI |

### Module B: prediction and suggestions
| Endpoint | Returns |
|---|---|
| `GET /services/{id}/suggestion?minutes_since_last_change=` | Predicted fare (range), suggested fare or `blocked_reason`, expected seats / revenue / margin ranges, 1 to 3 reasons, floor, engine fare, rating, nearest rival before and after ours, flags |
| `POST /fare/predict` | Fare range for a new trip (`route_id, departure_at, available_seats, ac, sleeper`). `as_of` is accepted but ignored |
| `GET /forecast/services/{id}/curve` | Expected seats (range), seats sold, similar-services band (p10/p50/p90), checkpoints, flags |
| `GET /pricing/elasticity?route_id=&slot=&dtg_band=&day_type=` | Slope of seats against fare (range) or "not enough data", with the reason and how many sold-out services were left out |
| `GET /rivals/services/{id}?as_of=` | Rival departures within ±30 minutes as "Rival A", "Rival B", their fares and gap to ours, route rating |
| `GET /rules`, `PUT /rules` (admin) | Active pricing rules. `PUT` saves a new version and keeps old ones; it applies to the next request |
| `GET /services/{id}/fare-prediction` | Legacy as-of fare from `fare_predictions`. Not used by the UI |

### Module C: alerts, what-if and decisions
| Endpoint | Returns |
|---|---|
| `GET /warnings?owner_id=` | Services still to depart, behind the bottom of their checkpoint range, with no decision yet: seat gap, `raised_at`, `owner_id`. With `owner_id`, only that person's routes (404 for an unknown user) |
| `GET /owners`, `PUT /owners/{route_id}` (admin) | Who owns each route. Starts empty. `PUT {"user_id": "analyst-1"}`, or `null` to clear |
| `GET /services/{id}/whatif?minutes_since_last_change=` | Every fare step within 25% of the current fare: expected seats, revenue and margin ranges; rule-breaking steps marked `blocked_by` |
| `POST /suggestions/{id}/decision` | `approve`, `change` (fare checked against the rules), `reject` or `wrong` (reason and category required). Stores who, when, why, engine fare, our fare, rules version, model version, predicted fare and floor. 409 if already decided. The id is the `service_id` |
| `GET /decisions?service_id=` | Decisions with `outcome` `{final_seats, revenue}` once loaded, otherwise `null` |

### Revenue desk and support
| Endpoint | Returns |
|---|---|
| `GET /desk/summary?window=&corridor_id=` | Services, behind checkpoint, in loss, suggestions waiting |
| `GET /desk/services?window=&corridor_id=&page=` | Ranked services with all desk columns, plus cancelled and unranked lists. `window` is `today`, `tomorrow`, `next30`, `earlier` or `all` (Asia/Kolkata dates) |
| `GET /routes`, `GET /users` | Route list, placeholder users |
| `GET /pipeline/status` | The last data refresh (time, status, error), or `null` before the first one |

```bash
curl localhost:8001/services/BKG2026112/suggestion
curl "localhost:8001/desk/services?window=next30"
curl "localhost:8001/pnl/totals?group_by=coach_type"
curl -X POST localhost:8001/fare/predict -H 'content-type: application/json' \
  -d '{"route_id":"R001","departure_at":"2026-11-01T08:00","available_seats":20,"ac":1,"sleeper":0}'
curl -X POST localhost:8001/suggestions/BKG2026112/decision -H 'X-User-Id: analyst-1' \
  -H 'content-type: application/json' -d '{"action":"reject","reason":"Festival demand"}'
```

## Models
- **Fare:** `models/nuego_fare_model_linear.pkl`, a Linear Regression trained by `scripts/train_linear_fare_model.py`.
  - It uses the same inputs and one-hot step as `notebooks/decision_tree.ipynb`.
  - It replaced the notebook's Decision Tree because it was more accurate on every split tried. On the notebook's own split its MAE is about INR 41, against 70.87 for the tree; its 5-fold cross-validated MAE is about INR 45.
  - The range is the 80th percentile of the cross-validated errors (about ±INR 68).
  - Competitor inputs are the route's min, median and mean competitor fare over all rows, as in the notebook.
  - No coach type means no prediction.
  - The old tree is kept in `models/nuego_fare_model.pkl` but not served.
- **Seats:** `models/nuego_seats_sold_model.pkl`, the team's Decision Tree, used as-is.
  - It gives expected seats (the checkpoint) with a range from its own in-sample errors, which makes the range optimistic.
  - A one-off check found it only slightly better than a route average: MAE 7.05 against 7.24.
- **Coach type:** AC and Sleeper come from `data/processed/nuego_train_241_ac_sleeper.csv`. They are never guessed.

## Pricing rules (`pricing_rules`)
Each version holds:
- `floor_switch_hours`, `ceiling`, `state_cap` (null = none), `max_change_pct`
- `min_minutes_between_changes`, `seats_weight`, `fare_steps`
- `updated_by`, `updated_at`

The defaults are assumptions to confirm with GreenCell (`DEFAULT_RULES` in `app/config.py`): ceiling 1500, no state cap, 15%, 240 minutes, steps every INR 10 from 200 to 1500.

`rules.check_fare` returns the codes `NOT_A_FARE_STEP`, `BELOW_FLOOR`, `ABOVE_CEILING`, `ABOVE_STATE_CAP`, `STEP_TOO_LARGE` and `TOO_SOON`. A suggestion that breaks a rule cannot be produced.

## How a suggestion is made
1. **No suggestion, with a `blocked_reason`:**
   - `CANCELLED`, `COST_MISSING`, `NO_FLOOR`, `NO_FARE_PREDICTION`, `NO_ALLOWED_FARE`, `NO_SEAT_FORECAST`.
   - `NO_ALLOWED_FARE` carries the floor, the highest fare the other rules allow, and the rules broken per fare step.
   - The predicted fare is still returned.
2. **Floor:** the average floor (mid) is used until `floor_switch_hours` before departure, then the marginal floor.
   - The marginal floor needs channel commission, which is not in the data.
   - Near departure it therefore falls back to the average floor and sets `floor_missing`.
3. **The fare:** the allowed fare step closest to the predicted fare (ties go to the lower step).
   - `seats_weight` is stored but not used while the fare comes from the model.
4. **Seats, revenue and margin** at that fare come from the seat model, as ranges.
5. **Change against the current fare:** the seat model shows more seats at a higher fare, because fare follows demand in this data.
   - So a change is only claimed when expected seats fall as the fare rises (`price_response: "used"`).
   - Otherwise `change_vs_current` is null.
6. **Reasons:** 1 to 3 from a fixed list (`app/reasons.py`), in this priority, with text from templates:
   - `BOOKING_PACE`: below p10 or above p90 of similar past services.
   - `RIVAL_GAP`: more than 10% from the median rival fare.
   - `FESTIVAL`: holiday score of 0.5 or more.
   - `COST_FLOOR`: the floor limited the fare.
   - `RATING`: 4.3 or more and above rivals, or 3.8 or less and below them.

## Where the data comes from
- **Seat counts** are booking-time snapshots, one per service. There is no live feed, so an alert's "time raised" is the snapshot time.
- **Owners:** there is no owner in the data, so an admin assigns them in Settings.
- **Alerts** are in-app only: the Alerts page and the sidebar badge. The badge shows the signed-in person's routes if they own any, otherwise everyone's.
- **Outcomes:** there are no final seats in the data. Decisions show "Not in the data" until `scripts.load_outcomes` loads a real file.
- **Sold out:** full coaches are flagged and left out of the price-response fit. There are none in the current data.
- **Upgrades:** older `decisions` tables gain the new columns in place, and their rows are kept.

## Results on the current data (245 services)
- **Suggestions:**
  - 49 made: 44 with `not_reliable`, 3 with `used` and 2 with `not_assessed` price response.
  - 172 `NO_ALLOWED_FARE`, 21 cancelled, 3 `NO_FLOOR`.
- **Why 172 are blocked:** the average floor is above the sale fare for 80% of services, and more than 15% above it for 76%. For those, no fare step passes both the floor and the 15% step limit.
- **Price response:** the slope of seats on fare is positive on all five routes (about +1.9 to +3.4), so it is reported as "fare follows demand", never as a price response.
- **Rivals:** only 4 of 245 services have a rival fare captured before their booking time (1,225 competitor rows in all).
- **Dates:** services depart between 25 Jan 2023 and 26 Dec 2026, about once a month per route. Most are in the past, and few have an earlier same-weekday service within 8 weeks.

## Known limits
- **Booking curve:** there is no day-by-day curve, because the data has one seat snapshot per service. Checkpoints are similar-services bands per days-to-go group.
- **Missing costs:** channel commission and energy cost are not in the data. So there is no marginal floor and no totals by channel.
- **Crew cost** is a monthly route figure, split by scheduled hours over an assumed 30 trips a month.
- **Time between changes:** this rule is checked only when `minutes_since_last_change` is passed, because there is no fare-change log.
- **Derived segments:**
  - Slots: morning 05–12, afternoon 12–17, evening 17–20, night otherwise.
  - Day type: holiday when the holiday score is 0.5 or more, otherwise weekend or weekday.
- **No risky-change warning:** there is no schedule-change history.

## Open questions for GreenCell
1. The real ceiling, state caps (and MSRTC reference fares where needed), step size, minimum time between changes and fare steps.
2. Is average cost ÷ expected seats the right floor? It sits above the sale fare for most services.
3. Which floor applies when (the switch point).
4. Channel commission, energy cost and channel per booking.
5. Booking-level data and the fare-on-sale history, so price response and the booking curve can be measured.
6. Final seats and revenue after departure, and the schedule-change history.
