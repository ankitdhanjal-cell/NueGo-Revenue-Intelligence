import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from app.auth import require_admin, require_user
from app.db import engine
from app.pnl import GROUPABLE, UNAVAILABLE, totals

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
from datetime import datetime  # noqa: E402

from pydantic import BaseModel  # noqa: E402

from app import fare_model, fare_notebook  # noqa: E402

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
    as_of: datetime | None = None  # kept for compatibility; the notebook method does not cut competitor rows by time
    engine_fare: float | None = None


@app.post("/fare/predict")
def fare_predict(req: FareRequest):
    services = pd.read_sql_table("services", engine)
    route = services[services["route_id"] == req.route_id]
    if route.empty:
        raise HTTPException(404, f"unknown route {req.route_id}")
    comp = pd.read_sql_table("competitor_fares", engine)
    dep = pd.Timestamp(req.departure_at)
    stats = fare_notebook.route_stats(comp).set_index("route_id")
    cs = stats.loc[req.route_id] if req.route_id in stats.index else None
    comp_feats = (dict(comp_min_fare=float("nan"), comp_median_fare=float("nan"), comp_avg_fare=float("nan"), comp_n=0)
                  if cs is None else dict(comp_min_fare=cs["comp_min_fare"], comp_median_fare=cs["comp_median_fare"],
                                          comp_avg_fare=cs["comp_avg_fare"], comp_n=int(cs["comp_n"])))
    feats = pd.DataFrame([dict(
        route_id=req.route_id, available_seats=req.available_seats, ac=req.ac, sleeper=req.sleeper,
        total_seats=route["total_seats"].mode().iloc[0], distance_km=route["distance_km"].mode().iloc[0],
        holiday_score=0.0, departure_month=dep.month, departure_weekday=dep.weekday(),
        departure_hour=dep.hour, duration_hours=route["duration_hours"].median(),
        **comp_feats)])
    p = fare_notebook.predict(fare_notebook.load(), feats).iloc[0]
    gap = None if req.engine_fare is None else float(p["fare_mid"] - req.engine_fare)
    return {"route_id": req.route_id, "model_version": p["model_version"],
            "fare_low": float(p["fare_low"]), "fare_mid": float(p["fare_mid"]), "fare_high": float(p["fare_high"]),
            "gap_to_engine": gap, "competitor_rows_used": int(feats.loc[0, "comp_n"]),
            "insufficient_data": bool(p["insufficient_data"]),
            "assumptions": "holiday_score assumed 0 (not supplied); competitor fares are the route-level summary used in the notebook", "note": REFERENCE_NOTE}


# ---------- Step 4: expected seats sold (checkpoint) ----------
@app.get("/forecast/services/{service_id}/curve")
def forecast_curve(service_id: str):
    f = pd.read_sql_query("SELECT * FROM seat_forecasts WHERE service_id = %(i)s", engine, params={"i": service_id})
    if f.empty:
        raise HTTPException(404, f"no forecast for service {service_id}")
    r = _json(f)[0]
    obs = pd.read_sql_query("SELECT band, avg_seats_sold, n FROM seat_observed_points WHERE route_id = %(r)s",
                            engine, params={"r": r["route_id"]})
    out = {
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
    return {**out, **curve_extras_for(service_id, r)}


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


# ---------- Module B: pricing rules and allowed fare steps ----------
from app import rules as pricing_rules  # noqa: E402


@app.get("/rules")
def get_rules():
    """The active pricing rules and allowed fare steps (newest version, read from the database)."""
    return pricing_rules.active_rules(engine)


@app.put("/rules")
def put_rules(body: pricing_rules.RulesIn, _admin: dict = Depends(require_admin)):
    """Save a new version of the rules (admin only). Takes effect on the next request, no restart."""
    pricing_rules.ensure_rules(engine)
    return pricing_rules.save_rules(engine, body)


# ---------- Module B: rivals ----------
from sqlalchemy import text  # noqa: E402

from app import rivals as rival_calc  # noqa: E402


@app.get("/rivals/services/{service_id}")
def rivals(service_id: str, as_of: datetime | None = None):
    """Rival departures within 30 minutes of ours. as_of defaults to the service's booking time."""
    s = pd.read_sql_query(text("SELECT * FROM services WHERE service_id = :i"), engine, params={"i": service_id},
                          parse_dates=["booking_time", "departure_at"])
    if s.empty:
        raise HTTPException(404, f"service {service_id} not found")
    service = s.iloc[0]
    comp = pd.read_sql_query(text("SELECT operator, departure_at, fare, captured_at, route_id FROM competitor_fares "
                                  "WHERE route_id = :r"), engine, params={"r": service["route_id"]},
                             parse_dates=["departure_at", "captured_at"])
    return rival_calc.rival_view(service, comp, pd.Timestamp(as_of or service["booking_time"]))


# ---------- Module B: price response ----------
from app import elasticity as elast  # noqa: E402


@app.get("/pricing/elasticity")
def pricing_elasticity(route_id: str, slot: str | None = None, dtg_band: str | None = None,
                       day_type: str | None = None):
    """Seats vs fare for one route, optionally narrowed by slot / dtg_band / day_type."""
    for name, val, allowed in (("slot", slot, elast.SLOTS), ("dtg_band", dtg_band, elast.DTG_BANDS),
                               ("day_type", day_type, elast.DAY_TYPES)):
        if val is not None and val not in allowed:
            raise HTTPException(422, f"{name} must be one of {allowed}")
    s = pd.read_sql_query(text("SELECT * FROM services WHERE route_id = :r"), engine, params={"r": route_id},
                          parse_dates=["departure_at"])
    if s.empty:
        raise HTTPException(404, f"unknown route {route_id}")
    s = elast.add_segment_columns(s)
    for col, val in (("slot", slot), ("dtg_band", dtg_band), ("day_type", day_type)):
        if val is not None:
            s = s[s[col] == val]
    r = elast.elasticity(s)
    return {"route_id": route_id, "segment": {"slot": slot, "dtg_band": dtg_band, "day_type": day_type},
            **r, "flags": {"insufficient_data": not r["enough_data"]},
            "method": "slope of log(seats sold) on log(fare on sale) over observed services; correlation, not causal",
            "note": "Not enough data is a valid answer here. No slope is invented."}


# ---------- Module B: booking-curve band (extends Module A's /forecast/.../curve) ----------
from app import curve as curve_calc  # noqa: E402


def curve_extras_for(service_id: str, r: dict) -> dict:
    """Extra curve fields: actual, band, checkpoints, forecast to departure. Module A's fields stay as they are."""
    s = pd.read_sql_query(text("SELECT * FROM services WHERE route_id = :r"), engine, params={"r": r["route_id"]},
                          parse_dates=["departure_at"])
    me = s[s["service_id"] == service_id]
    extras = curve_calc.curve_extras(me, s[s["service_id"] != service_id]) if not me.empty else {}
    flags = {"no_history": extras.get("band_status") != "ok", "insufficient_data": bool(r["insufficient_data"])}
    return {**extras, "forecast_to_departure": {
        "days_to_go": 0, "seats": {"low": r["expected_low"], "mid": r["expected_mid"], "high": r["expected_high"]},
        "source": "seat forecast (team seat model)"}, "flags": flags}


# ---------- Module B: suggested fare (advice only) ----------
from app import suggestion as suggestion_calc  # noqa: E402


@app.get("/services/{service_id}/suggestion")
def suggestion(service_id: str, minutes_since_last_change: float | None = Query(None, ge=0)):
    """Suggested fare from the allowed fare steps, inside every pricing rule. Advice only, never written anywhere."""
    out = suggestion_calc.suggest_for_service(engine, service_id, minutes_since_last_change)
    if out is None:
        raise HTTPException(404, f"service {service_id} not found")
    return out


# ---------- Module B: desk, alerts, what-if, decisions, users ----------
from app import decisions as decisions_calc  # noqa: E402
from app import desk as desk_calc  # noqa: E402
from app import whatif as whatif_calc  # noqa: E402
from app.config import USERS  # noqa: E402


def _window(window: str) -> str:
    if window not in desk_calc.WINDOWS:
        raise HTTPException(422, f"window must be one of {list(desk_calc.WINDOWS)}")
    return window


@app.get("/users")
def users():
    """Who can sign in (auth stub). The UI sends the chosen id as X-User-Id."""
    return {"items": USERS}


@app.get("/routes")
def routes():
    return {"items": desk_calc.routes(engine)}


@app.get("/desk/summary")
def desk_summary(window: str = "next30", corridor_id: str = ""):
    return desk_calc.desk_summary(engine, _window(window), corridor_id)


@app.get("/desk/services")
def desk_services(window: str = "next30", corridor_id: str = "", page: int = Query(1, ge=1)):
    return desk_calc.desk_page(engine, _window(window), corridor_id, page)


@app.get("/warnings")
def warnings():
    return {"items": desk_calc.warnings(engine)}


@app.get("/services/{service_id}/whatif")
def whatif(service_id: str, minutes_since_last_change: float | None = Query(None, ge=0)):
    out = whatif_calc.what_if_for_service(engine, service_id, minutes_since_last_change)
    if out is None:
        raise HTTPException(404, f"service {service_id} not found")
    return out


@app.get("/decisions")
def list_decisions(service_id: str | None = None):
    return {"items": decisions_calc.list_decisions(engine, service_id)}


@app.post("/suggestions/{service_id}/decision", status_code=201)
def decide(service_id: str, body: decisions_calc.DecisionIn, user: dict = Depends(require_user)):
    """Record a decision. It is only stored here; nothing is sent to any pricing system."""
    try:
        out = decisions_calc.decide(engine, service_id, user, body)
    except decisions_calc.AlreadyDecided as e:
        when = datetime.fromisoformat(e.prior["at"]).strftime("%d %b %Y, %I:%M %p")
        return JSONResponse({"detail": f"Already decided by {e.prior['user']} on {when}."}, status_code=409)
    except decisions_calc.NotAllowed as e:
        return JSONResponse({"detail": e.errors}, status_code=422)
    if out is None:
        raise HTTPException(404, f"service {service_id} not found")
    return out
