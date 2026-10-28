"""Module B: the revenue desk. One row per service built from Module A's tables, ranked by Module A's attention score.

Windows are real dates (Asia/Kolkata): today, tomorrow, next 30 days, earlier (already departed), all.
The seat count is the booking snapshot stored with each service, not a live feed.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app import pnl as pnl_calc
from app.config import W_BEHIND, W_MARGIN
from app.decisions import decided_service_ids
from app.desk_labels import coach_label

WINDOWS = ("today", "tomorrow", "next30", "earlier", "all")
PAGE_SIZE = 50
CACHE_SECONDS = 60  # the tables only change when the pipeline scripts run; decisions are read fresh


def now_ist() -> datetime:
    return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)


def _num(x):
    return None if x is None or pd.isna(x) else float(x)


def in_window(departure_at: pd.Series, window: str, now: datetime) -> pd.Series:
    day = departure_at.dt.normalize()
    today = pd.Timestamp(now).normalize()
    if window == "today":
        return day == today
    if window == "tomorrow":
        return day == today + pd.Timedelta(days=1)
    if window == "next30":
        return (day >= today) & (day <= today + pd.Timedelta(days=30))
    if window == "earlier":
        return day < today
    return pd.Series(True, index=departure_at.index)


_cache: dict = {}


def desk_frame(engine) -> pd.DataFrame:
    """Every service with its status, flags and global attention score. Cached for CACHE_SECONDS per engine."""
    hit = _cache.get(id(engine))
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    df = _build_frame(engine)
    _cache[id(engine)] = (time.monotonic(), df)
    return df


def _build_frame(engine) -> pd.DataFrame:
    pnl = pd.read_sql_table("pnl_services", engine)
    fc = pd.read_sql_table("seat_forecasts", engine)
    sv = pd.read_sql_table("services", engine, columns=["service_id", "booking_time"])
    ranked, _ = pnl_calc.rank(pnl, fc, W_BEHIND, W_MARGIN)
    df = (pnl.merge(fc[["service_id", "ac", "sleeper", "expected_low", "expected_mid", "expected_high",
                        "insufficient_data"]], on="service_id", how="left")
          .merge(sv, on="service_id", how="left")
          .merge(ranked[["service_id", "score", "behind_part", "margin_part"]], on="service_id", how="left"))
    no_forecast = df["expected_mid"].isna()
    df["status"] = np.select([no_forecast, df["seats_sold"] < df["expected_low"], df["seats_sold"] > df["expected_high"]],
                             [None, "behind", "ahead"], default="on_pace")
    return df


def select(df: pd.DataFrame, window: str, corridor_id: str, now: datetime) -> pd.DataFrame:
    keep = in_window(df["departure_at"], window, now)
    if corridor_id:
        keep &= df["route_id"] == corridor_id
    return df[keep]


def to_service(r, rank: int | None) -> dict:
    flags = {}
    if r.checkpoint_status != "ok" or pd.isna(r.expected_mid):
        flags["no_history"] = True
    if bool(r.insufficient_data) if not pd.isna(r.insufficient_data) else True:
        flags["low_confidence"] = True
    if r.margin_status == "cost missing":
        flags["cost_missing"] = True
    has_cp = not pd.isna(r.expected_mid)
    return dict(
        service_id=r.service_id, route_label=str(r.corridor).replace(" - ", " → "), corridor_id=r.route_id,
        corridor_label=str(r.corridor).replace(" - ", " → "), departure_at=r.departure_at.isoformat(),
        as_of=r.booking_time.isoformat(), hours_to_departure=_num(r.hours_to_departure),
        coach_type=coach_label(r.ac, r.sleeper), seats_sold=_num(r.seats_sold), capacity=_num(r.total_seats),
        checkpoint=dict(low=_num(r.expected_low), mid=_num(r.expected_mid), high=_num(r.expected_high)) if has_cp else None,
        gap_to_checkpoint=round(float(r.seats_sold - r.expected_mid), 1) if has_cp else None,
        fare_on_sale=_num(r.fare_on_sale), revenue=_num(r.revenue), cost_to_run=_num(r.cost_to_run),
        margin_now=_num(r.profit), status=None if pd.isna(r.status) else str(r.status), flags=flags, rank=rank,
        score_parts=None if rank is None else dict(score=round(float(r.score), 4), behind_part=round(float(r.behind_part), 4),
                                                   margin_part=round(float(r.margin_part), 4)),
        cancelled=bool(r.flag_cancelled))


def desk_page(engine, window: str, corridor_id: str, page: int, now: datetime | None = None) -> dict:
    now = now or now_ist()
    sel = select(desk_frame(engine), window, corridor_id, now)
    live = sel[~sel["flag_cancelled"]]
    ranked = live[live["score"].notna()].sort_values(["score", "departure_at", "service_id"], ascending=[False, True, True])
    unranked = live[live["score"].isna()].sort_values(["departure_at", "service_id"])
    items = [to_service(r, i) for i, r in enumerate(ranked.itertuples(), 1)] + [to_service(r, None) for r in unranked.itertuples()]
    cancelled = [to_service(r, None) for r in sel[sel["flag_cancelled"]].sort_values("departure_at").itertuples()]
    start = (max(page, 1) - 1) * PAGE_SIZE
    return dict(items=items[start:start + PAGE_SIZE], cancelled=cancelled, page=max(page, 1), page_size=PAGE_SIZE,
                total=len(items), as_of_today=now.date().isoformat())


def desk_summary(engine, window: str, corridor_id: str, now: datetime | None = None) -> dict:
    now = now or now_ist()
    sel = select(desk_frame(engine), window, corridor_id, now)
    live = sel[~sel["flag_cancelled"]]
    done = decided_service_ids(engine)
    waiting = live[(live["margin_status"] != "cost missing") & ~live["service_id"].isin(done)]
    return dict(services=len(live), behind_checkpoint=int((live["status"] == "behind").sum()),
                in_loss=int((live["profit"] < 0).sum()), suggestions_waiting=len(waiting))


def warnings(engine, now: datetime | None = None) -> list[dict]:
    """Services still to depart that are behind their checkpoint and have no decision yet."""
    now = now or now_ist()
    df = desk_frame(engine)
    done = decided_service_ids(engine)
    w = df[(df["status"] == "behind") & ~df["flag_cancelled"] & (df["departure_at"] >= now) & ~df["service_id"].isin(done)]
    return [dict(id=f"w-{r.service_id}", service_id=r.service_id,
                 route_label=f"{str(r.corridor).replace(' - ', ' → ')} · {r.departure_at.strftime('%H:%M')}",
                 seat_gap=round(float(r.seats_sold - r.expected_mid), 1),
                 checkpoint=dict(low=float(r.expected_low), mid=float(r.expected_mid), high=float(r.expected_high)),
                 raised_at=r.booking_time.isoformat(), departure_at=r.departure_at.isoformat())
            for r in w.sort_values("departure_at").itertuples()]


def routes(engine) -> list[dict]:
    s = pd.read_sql_query("SELECT route_id, origin, destination, total_seats FROM services", engine)
    g = s.groupby("route_id").agg(origin=("origin", "first"), destination=("destination", "first"),
                                  capacity=("total_seats", lambda x: int(x.mode().iloc[0]))).reset_index()
    return [dict(id=r.route_id, label=f"{r.origin} → {r.destination}", capacity=r.capacity) for r in g.itertuples()]
