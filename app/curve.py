"""Module B, step 4: extra fields for GET /forecast/services/{id}/curve (FR-PRC-003).

The seat forecast fields are Module A's and stay as they are. This adds:
  actual     seats sold so far for this service (one snapshot per service in this data)
  band       p10 / p50 / p90 of seats sold for similar PAST services (same route, slot, day type,
             days-to-go band, departed before this service), or "no history"
  checkpoints the same band for every days-to-go band
No curve shape is built: seats sold does not move with days-to-go in this data (correlation
~0.09, band means not monotonic), so a shape would be invented.
"""
import pandas as pd

from app.config import MIN_BAND_SERVICES
from app.elasticity import DTG_BANDS, add_segment_columns


def _percentiles(d: pd.DataFrame) -> dict:
    n = len(d)
    if n < MIN_BAND_SERVICES:
        return dict(p10=None, p50=None, p90=None, n=n, status="no history")
    p10, p50, p90 = (round(float(d["seats_sold"].quantile(q)), 1) for q in (0.1, 0.5, 0.9))
    return dict(p10=p10, p50=p50, p90=p90, n=n, status="ok")


def curve_extras(service: pd.DataFrame, history: pd.DataFrame) -> dict:
    """`service` is one row of the services table (as a DataFrame); `history` is the other services."""
    both = add_segment_columns(pd.concat([service, history], ignore_index=True))
    me, hist = both.iloc[0], both.iloc[1:]
    similar = hist[(hist["route_id"] == me["route_id"]) & (hist["slot"] == me["slot"])
                   & (hist["day_type"] == me["day_type"]) & ~hist["flag_cancelled"].astype(bool)
                   & (hist["departure_at"] < me["departure_at"])]
    band = _percentiles(similar[similar["dtg_band"] == me["dtg_band"]])
    checkpoints = [dict(dtg_band=b, **_percentiles(similar[similar["dtg_band"] == b])) for b in DTG_BANDS]
    return {
        "capacity": None if pd.isna(me["total_seats"]) else int(me["total_seats"]),
        "actual": {"points": [dict(days_to_go=round(float(me["days_to_go"]), 2), seats_sold=float(me["seats_sold"]))],
                   "note": "One booking snapshot per service in this data."},
        "band": None if band["status"] != "ok" else {k: band[k] for k in ("p10", "p50", "p90", "n")},
        "band_status": band["status"],
        "band_basis": dict(route_id=me["route_id"], slot=me["slot"], day_type=me["day_type"],
                           dtg_band=me["dtg_band"], departed_before=str(me["departure_at"])),
        "checkpoints": checkpoints,
    }
