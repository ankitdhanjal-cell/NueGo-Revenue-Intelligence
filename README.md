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
python -m scripts.train_fare_model       # honest time-split evaluation of the fare tree
python -m scripts.train_seat_model       # same for the seat tree
python -m scripts.compute_fare_predictions
python -m scripts.compute_forecasts      # must run before compute_pnl
python -m scripts.compute_pnl
uvicorn app.main:app --reload            # docs at http://localhost:8000/docs
python -m pytest -q
```
Models served: `models/nuego_fare_model.pkl`, `models/nuego_seats_sold_model.pkl` (team Decision Trees).
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

## Model results (time-based split, newest 20% held out)
| Model | MAE | Baseline MAE | Note |
|---|---|---|---|
| Fare tree | 85.0 INR | 91.2 (route median) | range +-125 INR; model under-predicts newer fares by ~77 INR on average |
| Seat tree | 7.05 seats | 7.24 (route mean) | range +-12.8 seats; days-to-go adds nothing (7.01) |

## Known limits
- Only 15 of 245 services have a competitor fare captured before their booking time (+-3 days, same route) -> most fare predictions are flagged `insufficient_data`.
- One snapshot per service and no link between seats sold and days-to-go -> no booking-curve shape is returned (`curve: null`); observed pooled points are returned instead.
- Crew cost is a route-level monthly figure, split by scheduled hours over an assumed 30 trips/month.
- Marginal floor needs channel commission, which is not in the data -> "cost missing". Energy and channel are also absent, so totals by channel / coach type are unavailable.
- Expected margin uses the seat forecast as a stand-in for Module B.
- Coach type for 5 services (original sample rows) is unknown and never guessed.
