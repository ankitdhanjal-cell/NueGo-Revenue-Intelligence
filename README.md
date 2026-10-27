# NueGo Revenue Intelligence (POC): Person 1 scope

This project answers three questions about every NueGo bus service:

1. **Module A, service P&L:** how much money is it making against what it costs to run?
2. **Fare prediction:** what fare does the model expect for it? (a reference only, never a suggestion)
3. **Seat prediction:** how many seats should it have sold by now?

Rules we follow everywhere: no fare is ever suggested or changed, nothing is written to any outside
system, every prediction comes with a low / mid / high range, and missing data is shown as missing
(never filled in or guessed).

---

## 1. What was built, in order

| Step | What | Result |
|---|---|---|
| 0. Setup | `.env`, `docker-compose.yml`, `requirements.txt`, a virtual env, and both CSV files loaded into the database | 245 NueGo services and 1,225 competitor rows in Postgres |
| 1. Clean layer | Turn the raw text into proper numbers and dates, and flag problems | `services` and `competitor_fares` tables |
| 2. Module A P&L | Revenue, cost to run, profit and margin, cost floors, totals | `GET /pnl/services/{id}`, `GET /pnl/totals`, `GET /pnl/cancelled` |
| 3. Fare prediction | Use the team's fare Decision Tree | `GET /services/{id}/fare-prediction`, `POST /fare/predict` |
| 4. Seat prediction | Use the team's seat Decision Tree | `GET /forecast/services/{id}/curve` |
| 5. Finish Module A | Expected margin, attention ranking, 8-week trend, better cost floors, real-data tests | `GET /pnl/ranking`, `GET /pnl/services/{id}/trend` |
| 6. Clean-up | Removed unused files and all retraining code; only the two team models are used | 28 tests pass |

## 2. What it is made of

| Tool | Used for |
|---|---|
| Python 3.12 + `.venv` | everything |
| PostgreSQL (pgvector image) + pgAdmin, in Docker | stores raw and computed tables (database `pi_beta`, pgAdmin on port 8090) |
| Pandas | cleaning and calculations |
| SQLAlchemy + psycopg2 | talking to the database |
| scikit-learn + joblib | loading and running the team's two Decision Tree models |
| FastAPI + uvicorn | the API |
| Alembic | database migrations (versioned schema changes) |
| pytest | 28 tests |
| python-dotenv | reads `.env` (database login, settings) |

## 3. How the data flows

```
data/raw/*.csv  ->  raw_route_details, raw_competitor_data    (scripts/load_raw_csv.py, text as-is)
                ->  services, competitor_fares                (scripts/build_clean_tables.py)
                ->  fare_predictions                          (scripts/compute_fare_predictions.py)
                ->  seat_forecasts, seat_observed_points      (scripts/compute_forecasts.py)
                ->  pnl_services                              (scripts/compute_pnl.py, needs seat_forecasts)
                ->  API (app/main.py) reads these tables
```

Folder map:

```
app/cleaning.py     parsing and data-quality flags
app/pnl.py          Module A maths, ranking, trend
app/fare_model.py   runs the fare model, builds competitor inputs, range
app/seat_model.py   runs the seat model, range
app/main.py         all API endpoints
app/config.py       settings that are assumptions (see section 8)
app/db.py           database connection
app/models.py       the database schema: all 8 tables and their columns (read this first)
migrations/         Alembic migrations: every schema change is a numbered file (0001 = baseline)
alembic.ini         Alembic settings (the database URL comes from .env)
scripts/            the pipeline scripts above
models/             the two team models (used as-is)
data/raw/           the two source CSVs
data/processed/     team file with AC / Sleeper per service
notebooks/          the team's original training notebook (reference only)
tests/              28 tests
```

## 4. Step 1: cleaning (how)

Done in `app/cleaning.py`:
- Money like `₹147,600` becomes the number 147600.
- Booking, departure and arrival dates and times are parsed into real timestamps.
- The first CSV header `w` is renamed `route_id`.
- `Available Seats` means seats **remaining**, so `seats_sold = Total Seats - Available Seats`.
- `days_to_go` = departure time minus booking time.
- `holiday_score` comes from the holiday text: 0 = none, 0.5 = adjacent travel day, 1 = the holiday itself.
- Flags are kept as columns: missing duration (5 rows), booked after departure (0), invalid seat count (0), cancelled (21).
- Competitor rows get flags too: captured after departure, fare below base fare. Their coach type stays as the raw "(verify)" text and is never interpreted.
- AC / Sleeper for NueGo services come from the team file `data/processed/nuego_train_241_ac_sleeper.csv` (240 of 245 match; the 5 original sample rows have none and are never guessed).

## 5. Step 2 and 5: Module A (plain arithmetic, no model)

**Revenue** = seats sold × fare on sale. For a cancelled booking the refund is subtracted (never below 0).
It is an estimate, because seats sold is a snapshot taken at booking time. Every row says so.

**Cost to run** = distance × coach cost per km + crew cost (split) + tolls.
Crew cost in the data is a route-level monthly figure, so, as the brief says, it is split across the
month's trips by scheduled hours: `monthly crew × trip hours ÷ (trips per month × route average hours)`.
The monthly route cost is repeated on every row, so it is not added again. A missing duration is taken from
the same route's other trips and flagged.

**Profit / margin now** = revenue − cost. If cost is missing, margin shows "cost missing".

**Cost floors:**
- Average floor = cost ÷ expected seats sold (low / mid / high).
- Marginal floor = extra cost of one more passenger (mainly channel commission). That data does not exist, so it shows "cost missing".
- Each row records which floor applies (`floor_in_use`): average until `FLOOR_SWITCH_HOURS` before departure, then marginal.

**Expected margin** = expected seats × fare on sale − cost, as low / mid / high from the seat forecast's range.
The brief wants Module B's revenue; Module B does not exist yet, so the seat forecast stands in, and the row says so.

**Totals** by corridor or date. Every total equals the sum of its services. Cancelled services are left out and
listed at `/pnl/cancelled`. Totals by coach type or channel return a clear 422, because that data does not exist.

**Attention ranking:** `score = 0.5 × behind_part + 0.5 × margin_part`
- `behind_part` = seats below the expected checkpoint ÷ total seats.
- `margin_part` = expected loss ÷ cost to run (max 1).
- Highest score first, ties go to the earliest departure, same data always gives the same order, and the parts are shown.
- Excluded (and listed with a reason): cancelled, cost missing, no forecast.
- A service with under 28 days of route history gets checkpoint status "no history": no behind-checkpoint score, margin still counted.

**Trend:** same route and weekday over the previous 8 weeks. With about one service per route per month, most services will have none.

## 6. Step 3 and 4: the two models

Both are the team's own scikit-learn Decision Tree pipelines, used exactly as given:
- `models/nuego_fare_model.pkl` (depth 5): predicts the fare.
- `models/nuego_seats_sold_model.pkl` (depth 4): predicts seats sold.

**Nothing is trained in this project.** What we add around them:
- **Inputs:** built from the cleaned tables, with AC / Sleeper from the team file. A service with no AC / Sleeper gets no prediction (`insufficient_data`).
- **Competitor inputs for the fare model** are rebuilt so they never leak the future: same route, departing within ±3 days, and captured **at or before the booking time**. The notebook used all-time stats, which would leak.
- **Range:** low / high = mid ± the 80th percentile of the model's own errors on this data (about ±₹66 for fares, ±9.6 seats). These errors are in-sample, so the range is optimistic; `range_basis` says so.
- **Fare output:** low / mid / high, model version, the gap to the engine fare, and a "reference only" note.
- **Seat output:** expected seats low / mid / high, gap to actual, `behind_checkpoint` (true only when actual is below the low end), and the real observed average seats by days-to-go band for the route.
- **No booking curve is returned (`curve: null`).** In this data seats sold does not change with days-to-go (correlation about 0.06), the seat model has no days-to-go input, and there is one snapshot per service. Any curve shape would be invented.

One-off accuracy check (refit the same trees on older rows, test on the newest 20%, not kept in the project):

| Model | Error (MAE) | Simple baseline |
|---|---|---|
| Fare tree | 85 INR | 91 INR (route median) |
| Seat tree | 7.05 seats | 7.24 seats (route mean) |

So both models are only slightly better than a plain average. Treat the ranking as a screening aid.

## 7. Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d                       # Postgres + pgAdmin, reads .env (newer Docker: `docker compose up -d`)
alembic upgrade head                       # creates all 8 tables (the schema lives in migrations/)
python -m scripts.load_raw_csv             # raw CSVs -> database (skips tables that already have rows)
python -m scripts.build_clean_tables       # clean tables
python -m scripts.compute_fare_predictions
python -m scripts.compute_forecasts        # must run before compute_pnl
python -m scripts.compute_pnl
uvicorn app.main:app --reload              # docs at http://localhost:8000/docs
python -m pytest -q                        # 28 tests
```

## 8. API

| Endpoint | Returns |
|---|---|
| `GET /pnl/services/{id}` | revenue, cost, margin, cost floors, floor in use, checkpoint status, expected margin |
| `GET /pnl/totals?group_by=corridor\|date` | totals (cancelled left out) |
| `GET /pnl/cancelled` | cancelled services |
| `GET /pnl/ranking?limit=` | attention ranking, score parts, excluded services |
| `GET /pnl/services/{id}/trend` | 8-week same-weekday history |
| `GET /services/{id}/fare-prediction` | fare low / mid / high, model version, gap to engine fare |
| `POST /fare/predict` | same for a new request: `route_id, departure_at, available_seats, ac, sleeper, as_of, engine_fare` |
| `GET /forecast/services/{id}/curve` | expected seats low / mid / high, gap, behind-checkpoint flag |

```bash
curl localhost:8000/pnl/services/BKG2023011
curl "localhost:8000/pnl/ranking?limit=5"
curl localhost:8000/services/BKG2023011/fare-prediction
curl localhost:8000/forecast/services/BKG2023011/curve
curl -X POST localhost:8000/fare/predict -H 'content-type: application/json' \
  -d '{"route_id":"R001","departure_at":"2026-03-01T08:00","available_seats":20,"ac":1,"sleeper":0,"engine_fare":500}'
```

## Changing the database schema (migrations)
The tables are created by migrations, not by the scripts. The scripts only replace the rows inside
existing tables (`app/db.py: write_table`), so a script can never change a column by accident.
To change the schema:
1. Edit the table in `app/models.py`.
2. `alembic revision --autogenerate -m "what changed" ` then read the new file in `migrations/versions/`.
3. `alembic upgrade head`. Undo the last change with `alembic downgrade -1`.
4. Tell the other module's owner, and run the tests (`tests/test_schema.py` checks models.py against the database).
New tables (for example Module B's rules table) are added the same way. Your existing database was marked as
already at the baseline with `alembic stamp 0001`; a new database just runs `alembic upgrade head`.

## 9. Tests (28)

- P&L: revenue, cost, refunds with a zero floor, zero seats, expected margin ranges, missing cost, average floor and floor-in-use.
- Crew split adds back to the monthly total within 0.5% (synthetic and real data).
- Totals equal the sum of their services (synthetic and real data).
- Revenue hand check: 20 services recomputed straight from the raw CSV text match the API to the rupee.
- Ranking order, ties, determinism, exclusions, "no history" rule; trend window.
- Fare: competitor join ignores rows captured after the prediction time and respects route and window; no AC / Sleeper means no prediction; ordered range; API responses.
- Seats: ordered range within capacity; no coach type means no prediction; API returns no invented curve.
- Schema: `app/models.py` must match the live database column for column (fails if a script changes a column).

## 10. Settings that are assumptions (in `.env`, defaults in `app/config.py`)

| Setting | Default | Why it is an assumption |
|---|---|---|
| `TRIPS_PER_ROUTE_MONTH` | 30 | the data does not say how many trips a route runs per month; drives the crew split |
| `FLOOR_SWITCH_HOURS` | 24 | which floor applies when is an open question for GreenCell |
| `RANK_W_BEHIND`, `RANK_W_MARGIN` | 0.5, 0.5 | ranking weights |

## 11. Known limits and open items

- Only 15 of 245 services have a competitor fare captured before their booking time (same route, ±3 days), so 230 fare predictions are flagged `insufficient_data`.
- The 5 original sample rows (BKG001 to BKG005) have no AC / Sleeper and no duration: no predictions for them.
- Not in the data, so not available: energy cost, channel commission (so no marginal floor), coach type and channel totals.
- Expected margin uses the seat forecast in place of Module B.
- Even the model-based numbers are weak: both trees barely beat a simple average.
- Still to do outside the code: get the real trips-per-month figure from GreenCell, and agree the P&L response shape with Person 2.
