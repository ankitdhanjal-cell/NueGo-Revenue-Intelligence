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
python -m scripts.load_raw_csv             # raw CSVs -> raw_route_details, raw_competitor_data (replaced)
python -m scripts.build_clean_tables       # -> services, competitor_fares
python -m scripts.compute_forecasts        # -> seat_forecasts, seat_observed_points
python -m scripts.compute_pnl              # -> pnl_services (needs seat_forecasts)

uvicorn app.main:app --port 8001           # the frontend proxies to 8001; API docs at /docs
python -m pytest -q                        # tests that write use a throwaway SQLite database
```

**Later refreshes:** `python -m scripts.refresh` rebuilds everything from the two CSVs (raw tables, clean
tables, fare model, fare predictions, forecasts, then P&L) and records the run in `pipeline_runs`. The sidebar shows when it last ran. Daily cron:
`0 6 * * * cd /path/to/repo && .venv/bin/python -m scripts.refresh`.

| Other scripts | Purpose |
|---|---|
| `scripts.train_fare_model` | Re-trains the fare model and saves `models/nuego_fare_model_linear.pkl` (the refresh runs it) |
| `scripts.seed_rules` | Creates `pricing_rules` with the default row (`GET /rules` also does this) |
| `scripts.load_outcomes path.csv` | Loads real final seats and revenue (`service_id, final_seats, final_revenue`) |
| `scripts.export_decisions [out.csv]` | Writes decisions with outcomes to a CSV for retraining (read-only) |
| `scripts.compute_fare_predictions` | Writes every service's predicted fare to `fare_predictions` (the refresh runs it) |

**New data:** replace `data/raw/route_details.csv` or `data/raw/competitor_data.csv` (same columns, money as
`₹1,234`, dates as `25-Jan-2023`), then run `python -m scripts.refresh` (it also retrains the fare model) and
restart the API (the model is cached). Rival matching reads `competitor_fares` on every request, so the Competitors tab updates at once.

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
| `POST /fare/predict` | Fare range for a new trip (`route_id, departure_at, available_seats`, optional `holiday_score` 0, 0.5 or 1, optional `engine_fare`) |
| `GET /forecast/services/{id}/curve` | Expected seats (range), seats sold, similar-services band (p10/p50/p90), checkpoints, flags |
| `GET /pricing/elasticity?route_id=&slot=&dtg_band=&day_type=` | Slope of seats against fare (range) or "not enough data", with the reason and how many sold-out services were left out |
| `GET /rivals/services/{id}?as_of=` | Competitor departures within ±30 minutes (`rivals`) and within ±3 days (`nearby_fares`, each marked if captured after our booking time), with operator names, fares and gap to ours, plus our fare and the route rating. With none, `missing_reason` (`captured_after_prediction_time`, `none_within_30_minutes` or `no_route_data`) and a `note` saying why |
| `GET /rules`, `PUT /rules` (admin) | Active pricing rules. `PUT` saves a new version and keeps old ones; it applies to the next request |
| `GET /services/{id}/fare-prediction` | The stored predicted fare from `fare_predictions` (same model). Not used by the UI |

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
  -d '{"route_id":"R001","departure_at":"2026-11-01T08:00","available_seats":20,"holiday_score":0}'
curl -X POST localhost:8001/suggestions/BKG2026112/decision -H 'X-User-Id: analyst-1' \
  -H 'content-type: application/json' -d '{"action":"reject","reason":"Festival demand"}'
```

## Models
- **Fare:** `models/nuego_fare_model_linear.pkl`, a Linear Regression (`app/fare_model.py`), trained by
  `scripts/train_fare_model.py` on the 224 services that ran.
  - Inputs: route, seats left, holiday score (0, 0.5, 1), weekend (Friday to Sunday) and departure year.
  - Accuracy: 5-fold cross-validated MAE INR 29 (R² 0.95). Trained on 2023–2025 only, it predicts 2026 within
    INR 33.5 on average. The range is the 80th percentile of the cross-validated errors (about ±INR 46).
  - Year was the missing input: fares rise every year with costs (median INR 500 in 2023, 600 in 2026). The
    previous model used month instead and missed 2026 fares by INR 80, worse than last year's route median.
  - Left out because they carry no signal in this data: AC / Sleeper (no fare difference, 90% range of the
    effect from −INR 17 to +6), competitor fares, distance, duration and total seats (one fixed value per route),
    month, weekday and hour.
  - Competitor fares are never predicted. They are only matched as rivals (below) and used in the `RIVAL_GAP`
    and `RATING` reasons.
  - The notebook's Decision Tree (`notebooks/decision_tree.ipynb`, `models/nuego_fare_model.pkl`) is kept for
    reference but not served.
- **Seats:** `models/nuego_seats_sold_model.pkl`, the team's Decision Tree, used as-is.
  - It gives expected seats (the checkpoint) with a range from its own in-sample errors, which makes the range optimistic.
  - A one-off check found it only slightly better than a route average: MAE 7.05 against 7.24.
- **Coach type:** AC and Sleeper come from `data/processed/nuego_train_241_ac_sleeper.csv` and are never guessed.
  They are shown in the UI and used by the seat model, but are unverified (see Data quality).

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
- **The two raw files** share `Route ID` (R001 to R005, Delhi to Chandigarh, Rishikesh, Shimla, Jaipur, Dehradun),
  dates as `25-Jan-2023`, times as `08:10` and money as `₹1,234`. Edits made to sync them (29 Oct 2026):
  - `route_details.csv`: the Route ID header was `w`.
  - The 5 original sample rows (BKG001 to BKG005) had the holiday label "Original sample row — not reclassified",
    which scored as a full holiday. Each now has the label the competitor file gives for the same date.
  - `competitor_data.csv`: 325 fares written as bare numbers (`1155`) are now `₹1,155`.
- **Rivals:** a competitor departure on the same route within ±30 minutes of ours, using its latest fare captured
  at or before our booking time (a later capture would be hindsight). Only these feed the reasons.
  For comparing prices, the Competitors tab also lists every competitor departure on our route within ±3 days,
  with operator name. NueGo's own rows in the competitor file (62 on R004) are never treated as a competitor.
- **Seat counts** are booking-time snapshots, one per service. There is no live feed, so an alert's "time raised" is the snapshot time.
- **Owners:** there is no owner in the data, so an admin assigns them in Settings.
- **Alerts** are in-app only: the Alerts page and the sidebar badge. The badge shows the signed-in person's routes if they own any, otherwise everyone's.
- **Outcomes:** there are no final seats in the data. Decisions show "Not in the data" until `scripts.load_outcomes` loads a real file.
- **Sold out:** full coaches are flagged and left out of the price-response fit. There are none in the current data.
- **Upgrades:** older `decisions` tables gain the new columns in place, and their rows are kept.

## Data quality
Both files were generated with AI. They were checked field by field; nothing was filled in or made up.

| Reliable, and used for prediction | Why |
|---|---|
| Route, dates, times, seats sold, fare on sale | Consistent; fares rise with seats sold (correlation 0.6 within a route) and by year |
| Holiday labels (both files) | Match the real Indian calendar (Republic Day, Holi, Eid, Diwali, Dussehra and so on), with the days either side marked |
| Cancellation charge | Always 20% of the fare |
| Route costs, rating counts | One value per route per year, rising each year |

| Unreliable, so not used for prediction (kept and flagged) | Effect |
|---|---|
| AC / Sleeper (team file) | No fare difference; the competitor file lists NueGo itself as "AC electric coach". Used only for display and the seat model |
| Seats sold vs days before departure | No relation (correlation 0.07), so there is no real booking curve and the seat model is weak |
| Refund on 19 of 21 cancellations | A random 53–90% of the fare. Only the 2 sample rows follow fare − cancellation charge. Affects only cancelled services' P&L, which totals leave out |
| BKG001 to BKG005 (the original sample rows) | No duration, AC or Sleeper; distances 359, 280 and 268 km differ from every other service on their routes (345, 270, 239) |
| Competitor capture times | All at 10:30 or 15:00; 474 rows are after departure (flagged, never used as rivals) |
| Competitor seats, durations, coach types | 40 seats for every operator, one trip time per route, coach types marked "(verify)"; each operator has exactly 62 rows |
| Competitor fares below their base fare | 259 rows (flagged) |
| Our R002 and R003 fares | 57% and 23% above the competitor median, against 9–13% on the other routes |
| Coverage | Our services end in Dec 2026; competitor rows run to Dec 2027 |

Edits made to the raw files to sync them (29 Oct 2026): the route file's Route ID header was `w`; the 5 sample rows'
holiday label "Original sample row — not reclassified" (scored as a full holiday) now has the competitor file's
label for the same date; 325 competitor fares written as bare numbers are now `₹1,234`.

## Results on the current data (245 services)
- **Suggestions** with the default 15% step limit:
  - 49 made: 44 with `not_reliable`, 3 with `used` and 2 with `not_assessed` price response.
  - 172 `NO_ALLOWED_FARE`, 21 cancelled, 3 `NO_FLOOR`.
  - With the 18% limit set in rules version 8 (29 Oct 2026): 56 made and 165 `NO_ALLOWED_FARE`.
- **Why 172 are blocked:** the average floor is above the sale fare for 80% of services, and more than 15% above it for 76%. For those, no fare step passes both the floor and the 15% step limit.
- **Price response:** the slope of seats on fare is positive on all five routes (about +1.9 to +3.4), so it is reported as "fare follows demand", never as a price response.
- **Rivals:** 1,550 competitor rows, departing 24 Jan 2023 to 27 Dec 2027. Of 245 services, 4 have a rival fare
  captured before their booking time, 28 have a rival within 30 minutes whose fares were all captured later, and 213
  have no rival within 30 minutes. The 325 rows for 2027 match no service yet, because our services end in Dec 2026.
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
7. Real route and competitor data in place of the AI-generated files, and the true coach type of each NueGo service.
8. Why R002 (Rishikesh) is priced 57% above competitors when the other routes are 9–23% above.
