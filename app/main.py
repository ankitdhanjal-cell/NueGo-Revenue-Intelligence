import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from app.db import engine
from app.pnl import GROUPABLE, UNAVAILABLE, totals
from datetime import datetime  # noqa: E402

from pydantic import BaseModel  # noqa: E402

from app import fare_model

app = FastAPI(title="NueGo Revenue Intelligence")


def _json(df: pd.DataFrame) -> list[dict]:
    """NaN -> None so the JSON is valid and nothing is invented."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


@app.get("/pnl/services/{service_id}")
def pnl_service(service_id: str):
    df = pd.read_sql_query("SELECT * FROM pnl_services WHERE service_id = %(i)s",
                           engine, params={"i": service_id})
    if df.empty:
        raise HTTPException(404, f"service {service_id} not found")
    return _json(df)[0]


@app.get("/pnl/totals")
def pnl_totals(group_by: str = Query("corridor")):
    if group_by in UNAVAILABLE:
        raise HTTPException(422, f"group_by={group_by} is not available: the data has no {group_by} column")
    if group_by not in GROUPABLE:
        raise HTTPException(422, f"group_by must be one of {sorted(GROUPABLE)}")
    pnl = pd.read_sql_table("pnl_services", engine)
    return {"group_by": group_by, "rows": _json(totals(pnl, group_by))}


@app.get("/pnl/cancelled")
def pnl_cancelled():
    """Cancelled services are left out of totals and listed here instead."""
    df = pd.read_sql_query("SELECT * FROM pnl_services WHERE flag_cancelled", engine)
    return {"count": len(df), "rows": _json(df)}


# ---------- Step 3: reference fare prediction (never the suggested fare) ----------
  # noqa: E402

REFERENCE_NOTE = "Reference only. This is not a suggested fare and is not written to any system."


@app.get("/services/{service_id}/fare-prediction")
def fare_prediction(service_id: str):
    df = pd.read_sql_query("SELECT * FROM fare_predictions WHERE service_id = %(i)s",
                           engine, params={"i": service_id})
    if df.empty:
        raise HTTPException(404, f"no fare prediction for service {service_id}")
    r = _json(df)[0]
    return {"service_id": service_id, "route_id": r["route_id"], "model_version": r["model_version"],
            "fare_low": r["fare_low"], "fare_mid": r["fare_mid"], "fare_high": r["fare_high"],
            "engine_fare": r["engine_fare"], "gap_to_engine": r["gap_to_engine"],
            "competitor_rows_used": r["comp_n"], "insufficient_data": bool(r["insufficient_data"]),
            "note": REFERENCE_NOTE}


class FareRequest(BaseModel):
    route_id: str
    departure_at: datetime
    available_seats: int
    ac: int  # 1 = AC. Required: coach type is never guessed.
    sleeper: int
    as_of: datetime | None = None  # prediction time; competitor rows after it are ignored
    engine_fare: float | None = None


@app.post("/fare/predict")
def fare_predict(req: FareRequest):
    services = pd.read_sql_table("services", engine)
    route = services[services["route_id"] == req.route_id]
    if route.empty:
        raise HTTPException(404, f"unknown route {req.route_id}")
    comp = pd.read_sql_table("competitor_fares", engine)
    as_of = pd.Timestamp(req.as_of or datetime.now())
    dep = pd.Timestamp(req.departure_at)
    feats = pd.DataFrame([dict(
        route_id=req.route_id, available_seats=req.available_seats, ac=req.ac, sleeper=req.sleeper,
        total_seats=route["total_seats"].mode().iloc[0], distance_km=route["distance_km"].mode().iloc[0],
        holiday_score=0.0, departure_month=dep.month, departure_weekday=dep.weekday(),
        departure_hour=dep.hour, duration_hours=route["duration_hours"].median(),
        **fare_model.competitor_features(req.route_id, dep, as_of, comp))])
    p = fare_model.predict(fare_model.load(), feats).iloc[0]
    gap = None if req.engine_fare is None else float(p["fare_mid"] - req.engine_fare)
    return {"route_id": req.route_id, "model_version": p["model_version"],
            "fare_low": float(p["fare_low"]), "fare_mid": float(p["fare_mid"]), "fare_high": float(p["fare_high"]),
            "gap_to_engine": gap, "competitor_rows_used": int(feats.loc[0, "comp_n"]),
            "insufficient_data": bool(p["insufficient_data"]),
            "assumptions": "holiday_score assumed 0 (not supplied)", "note": REFERENCE_NOTE}


# ---------- Step 4: expected seats sold (checkpoint) ----------
@app.get("/forecast/services/{service_id}/curve")
def forecast_curve(service_id: str):
    f = pd.read_sql_query("SELECT * FROM seat_forecasts WHERE service_id = %(i)s", engine, params={"i": service_id})
    if f.empty:
        raise HTTPException(404, f"no forecast for service {service_id}")
    r = _json(f)[0]
    obs = pd.read_sql_query("SELECT band, avg_seats_sold, n FROM seat_observed_points WHERE route_id = %(r)s",
                            engine, params={"r": r["route_id"]})
    return {
        "service_id": service_id, "route_id": r["route_id"], "model_version": r["model_version"],
        "expected_seats_sold": {"low": r["expected_low"], "mid": r["expected_mid"], "high": r["expected_high"]},
        "actual_seats_sold": r["actual_seats_sold"], "days_to_go_at_snapshot": round(r["days_to_go"], 2),
        "gap_to_expected": r["gap_to_expected"], "behind_checkpoint": bool(r["behind_checkpoint"]),
        "insufficient_data": bool(r["insufficient_data"]),
        "curve": None,
        "curve_note": ("No booking-curve shape is returned: in this data seats sold does not vary with "
                       "days-to-go and there is one snapshot per service, so a shape would be invented. "
                       "Observed pooled points for the route are given instead."),
        "observed_points": _json(obs),
    }


# ---------- Step 5: attention ranking and trend ----------
from app import pnl as pnl_calc  # noqa: E402
from app.config import W_BEHIND, W_MARGIN  # noqa: E402


@app.get("/pnl/ranking")
def pnl_ranking(limit: int = Query(50, ge=1, le=1000)):
    pnl = pd.read_sql_table("pnl_services", engine)
    fc = pd.read_sql_table("seat_forecasts", engine)
    ranked, excluded = pnl_calc.rank(pnl, fc, W_BEHIND, W_MARGIN)
    return {"weights": {"behind_checkpoint": W_BEHIND, "expected_margin": W_MARGIN},
            "score_formula": "w_behind*behind_part + w_margin*margin_part; ties -> earliest departure",
            "note": "Forecast is weak (MAE close to a simple average); treat the order as a screening aid.",
            "ranked_count": len(ranked), "excluded_count": len(excluded),
            "excluded_by_reason": excluded["excluded_reason"].value_counts().to_dict(),
            "ranked": _json(ranked.head(limit))}


@app.get("/pnl/services/{service_id}/trend")
def pnl_trend(service_id: str):
    pnl = pd.read_sql_table("pnl_services", engine)
    if service_id not in set(pnl["service_id"]):
        raise HTTPException(404, f"service {service_id} not found")
    return pnl_calc.trend(pnl, service_id)
