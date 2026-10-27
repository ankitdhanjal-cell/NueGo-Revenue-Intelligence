"""Step 1: turn the raw text CSV tables into a clean `services` table.

Only parsing and flagging happens here. Nothing is invented: a value that
cannot be parsed becomes NaN/NaT, and a data-quality flag explains why.
"""
import pandas as pd

RENAME = {
    "w": "route_id",
    "Booking ID": "booking_id",
    "Booking Time": "booking_time",
    "Fare (INR)": "base_fare",
    "Cancellation Charges (INR)": "cancellation_charge",
    "Fare on Sale (INR)": "fare_on_sale",
    "Origin": "origin",
    "Destination": "destination",
    "Departure Date": "departure_date",
    "Departure Time": "departure_time",
    "Arrival Date": "arrival_date",
    "Arrival Time": "arrival_time",
    "Duration (hours)": "duration_hours",
    "Available Seats": "available_seats",
    "Total Seats": "total_seats",
    "Distance (km)": "distance_km",
    "Route Monthly Service Cost (INR)": "monthly_service_cost",
    "Coach Cost per km (INR)": "coach_cost_per_km",
    "Crew Cost (INR)": "crew_cost",
    "Tolls (INR)": "tolls",
    "Booking Status": "booking_status",
    "Refund Amount (INR)": "refund_amount",
    "Refund Status": "refund_status",
    "Holiday / Event": "holiday_event",
    "Average Rating": "avg_rating",
    "Number of Ratings": "num_ratings",
}

MONEY_COLS = ["base_fare", "cancellation_charge", "fare_on_sale", "monthly_service_cost",
              "coach_cost_per_km", "crew_cost", "tolls", "refund_amount"]
NUMBER_COLS = ["available_seats", "total_seats", "distance_km", "duration_hours",
               "avg_rating", "num_ratings"]


def clean_money(s: pd.Series) -> pd.Series:
    """'₹147,600' -> 147600.0. Blank or unparseable -> NaN."""
    return pd.to_numeric(s.str.replace(r"[₹,\s]", "", regex=True), errors="coerce")


def clean_services(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=RENAME)[list(RENAME.values())].copy()
    df = df.apply(lambda c: c.str.strip())

    for c in MONEY_COLS:
        df[c] = clean_money(df[c])
    for c in NUMBER_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["booking_time"] = pd.to_datetime(df["booking_time"], format="%d-%b-%Y %H:%M")
    df["departure_at"] = pd.to_datetime(df["departure_date"] + " " + df["departure_time"],
                                        format="%d-%b-%Y %H:%M")
    df["arrival_at"] = pd.to_datetime(df["arrival_date"] + " " + df["arrival_time"],
                                      format="%d-%b-%Y %H:%M", errors="coerce")
    df = df.drop(columns=["departure_date", "departure_time", "arrival_date", "arrival_time"])

    # Available Seats means seats REMAINING, so sold = total - remaining.
    df["seats_sold"] = df["total_seats"] - df["available_seats"]
    df["days_to_go"] = (df["departure_at"] - df["booking_time"]).dt.total_seconds() / 86400

    # Data-quality flags (kept as columns so the API can surface them).
    df["flag_missing_duration"] = df["duration_hours"].isna()
    df["flag_booked_after_departure"] = df["days_to_go"] < 0
    df["flag_seats_invalid"] = (df["seats_sold"] < 0) | (df["seats_sold"] > df["total_seats"])
    df["flag_cancelled"] = df["booking_status"].eq("Cancelled")

    df.insert(0, "service_id", df["booking_id"])  # one booking row per service in this data
    return df
