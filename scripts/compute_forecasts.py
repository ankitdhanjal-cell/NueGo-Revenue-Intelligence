"""Expected seats sold per service -> `seat_forecasts`. Run: python -m scripts.compute_forecasts"""
import pandas as pd

from app import seat_model
from app.db import engine


def main() -> None:
    s = seat_model.prepare(pd.read_sql_table("services", engine))
    pred = seat_model.predict(seat_model.load(), s)
    out = pd.concat([s[["service_id", "route_id", "ac", "sleeper", "total_seats", "seats_sold", "days_to_go"]], pred], axis=1)
    out = out.rename(columns={"seats_sold": "actual_seats_sold"})
    out["gap_to_expected"] = out["actual_seats_sold"] - out["expected_mid"]
    # behind checkpoint only when below the LOW end of the range (not just below the mid)
    out["behind_checkpoint"] = out["actual_seats_sold"] < out["expected_low"]
    out.to_sql("seat_forecasts", engine, if_exists="replace", index=False)

    # observed pooled points (real data only): average seats sold by days-to-go band per route
    s["band"] = pd.cut(s["days_to_go"], [0, 3, 7, 14, 400], labels=["0-3", "3-7", "7-14", "14+"])
    obs = (s[~s["flag_cancelled"]].groupby(["route_id", "band"], observed=True)["seats_sold"]
           .agg(avg_seats_sold="mean", n="count").reset_index().astype({"band": str}))
    obs.to_sql("seat_observed_points", engine, if_exists="replace", index=False)
    print(f"seat_forecasts: {len(out)} rows, behind checkpoint: {int(out['behind_checkpoint'].sum())}, no prediction: {int(out['expected_mid'].isna().sum())}")


if __name__ == "__main__":
    main()
