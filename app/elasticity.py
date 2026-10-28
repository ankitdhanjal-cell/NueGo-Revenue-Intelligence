"""Module B, step 3: how seats sold change with the fare, for one segment (FR-PRC-001).

Slope = polyfit of log(seats sold) on log(fare on sale) over the OBSERVED services in the
segment. It is a correlation, not a causal price response: in this data the engine raises the
fare as the coach fills, so fare follows demand and the slope usually comes out positive.
A positive slope is never offered as a price response (enough_data = False). Too few services
or too few distinct fares -> no slope at all. Nothing is filled in.
Sold-out services are left out (FR-PRC-002): their true demand was above capacity, so "seats sold"
understates it. Estimating that demand needs booking pace over time, which the data does not have.
A regression on real fare experiments or history replaces this when such data exists.
"""
import numpy as np
import pandas as pd

from app.config import MIN_ELASTICITY_FARES, MIN_ELASTICITY_SERVICES

SLOTS = ["morning", "afternoon", "evening", "night"]
DTG_BANDS = ["0-3", "3-7", "7-14", "14+"]  # same bands as seat_observed_points
DAY_TYPES = ["weekday", "weekend", "holiday"]
BOOTSTRAPS = 300


def slot_of(hour: int) -> str:
    return "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 20 else "night"


def day_type_of(weekday: int, holiday_score: float) -> str:
    return "holiday" if holiday_score >= 0.5 else "weekend" if weekday >= 5 else "weekday"


def add_segment_columns(s: pd.DataFrame) -> pd.DataFrame:
    s = s.copy()
    s["slot"] = s["departure_at"].dt.hour.map(slot_of)
    s["dtg_band"] = pd.cut(s["days_to_go"], [0, 3, 7, 14, 400], labels=DTG_BANDS).astype(object)
    s["day_type"] = [day_type_of(w, h) for w, h in zip(s["departure_at"].dt.weekday, s["holiday_score"])]
    return s


def _slope(logfare: np.ndarray, logseats: np.ndarray) -> float:
    return float(np.polyfit(logfare, logseats, 1)[0])


def _observed_points(d: pd.DataFrame) -> list[dict]:
    """Real averages only: seats sold by fare band (up to 4 equal-count bands)."""
    if d["fare_on_sale"].nunique() < 2:
        return []
    band = pd.qcut(d["fare_on_sale"], q=min(4, d["fare_on_sale"].nunique()), duplicates="drop")
    g = d.groupby(band, observed=True).agg(n=("seats_sold", "count"), fare_from=("fare_on_sale", "min"),
                                          fare_to=("fare_on_sale", "max"), avg_seats_sold=("seats_sold", "mean"))
    return [dict(fare_from=float(r.fare_from), fare_to=float(r.fare_to), n=int(r.n),
                 avg_seats_sold=round(float(r.avg_seats_sold), 1)) for r in g.itertuples()]


def elasticity(segment: pd.DataFrame) -> dict:
    """Slope range and the honest enough-data verdict for the services in one segment."""
    sold_out = segment["seats_sold"] >= segment["total_seats"]
    d = segment[~segment["flag_cancelled"] & ~sold_out & (segment["seats_sold"] > 0) & (segment["fare_on_sale"] > 0)]
    n, fares = len(d), int(d["fare_on_sale"].nunique())
    out = dict(n_services=n, distinct_fares=fares, sold_out_left_out=int((sold_out & ~segment["flag_cancelled"]).sum()),
               elasticity=None, enough_data=False, reason=None,
               observed_points=_observed_points(d) if n else [])
    if n < MIN_ELASTICITY_SERVICES:
        out["reason"] = f"not_enough_services (have {n}, need {MIN_ELASTICITY_SERVICES})"
    elif fares < MIN_ELASTICITY_FARES:
        out["reason"] = f"not_enough_fare_variation (have {fares} distinct fares, need {MIN_ELASTICITY_FARES})"
    else:
        x, y = np.log(d["fare_on_sale"].to_numpy()), np.log(d["seats_sold"].to_numpy())
        rng = np.random.default_rng(0)  # fixed seed: the same data gives the same range
        boot = []
        for _ in range(BOOTSTRAPS):
            i = rng.integers(0, n, n)
            if np.ptp(x[i]) > 0:
                boot.append(_slope(x[i], y[i]))
        low, mid, high = (round(float(v), 3) for v in (np.percentile(boot, 10), _slope(x, y), np.percentile(boot, 90)))
        out["elasticity"] = dict(low=min(low, mid), mid=mid, high=max(high, mid))
        if mid >= 0:
            out["reason"] = "fare_follows_demand (slope is not negative, so it is not read as a price response)"
        else:
            out["enough_data"] = True
    return out
