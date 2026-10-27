"""Database schema: every table in `pi_beta`, declared in one place.

The tables are (re)built by the scripts in scripts/ with pandas `to_sql`, which creates them with
these same columns. This file is the readable contract for other modules (Person 2 / Module B):
use `metadata.tables["name"]` or the table objects below to query, and tell Person 1 before
changing a column. `tests/test_schema.py` fails if this file and the live database drift apart.

Tables with a service_id key mark it as the primary key in the docs only; pandas does not create
constraints, so they are not enforced by the database.
"""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, Integer, MetaData, Table, Text

metadata = MetaData()

# Raw NueGo bookings, every value as text exactly as in the CSV (scripts/load_raw_csv.py). Header 'w' is really Route ID.
raw_route_details = Table(
    "raw_route_details", metadata,
    Column("w", Text),
    Column("Booking ID", Text),
    Column("Booking Time", Text),
    Column("Fare (INR)", Text),
    Column("Cancellation Charges (INR)", Text),
    Column("Fare on Sale (INR)", Text),
    Column("Destination", Text),
    Column("Departure Date", Text),
    Column("Departure Time", Text),
    Column("Available Seats", Text),
    Column("Total Seats", Text),
    Column("Distance (km)", Text),
    Column("Route Monthly Service Cost (INR)", Text),
    Column("Coach Cost per km (INR)", Text),
    Column("Average Rating", Text),
    Column("Number of Ratings", Text),
    Column("Booking Status", Text),
    Column("Refund Amount (INR)", Text),
    Column("Refund Status", Text),
    Column("Crew Cost (INR)", Text),
    Column("Tolls (INR)", Text),
    Column("Origin", Text),
    Column("Holiday / Event", Text),
    Column("Duration (hours)", Text),
    Column("Arrival Date", Text),
    Column("Arrival Time", Text),
)

# Raw competitor fare snapshots, every value as text (scripts/load_raw_csv.py).
raw_competitor_data = Table(
    "raw_competitor_data", metadata,
    Column("Route ID", Text),
    Column("Route", Text),
    Column("Competitor ID", Text),
    Column("Competitor Name", Text),
    Column("Departure Date", Text),
    Column("Holiday", Text),
    Column("Departure Time", Text),
    Column("Base Fare (INR)", Text),
    Column("Fare (INR)", Text),
    Column("Total Seats", Text),
    Column("Available Seats", Text),
    Column("Capture Timestamp", Text),
    Column("Coach Type", Text),
    Column("Origin", Text),
    Column("Destination", Text),
    Column("Duration (hours)", Text),
    Column("Arrival Date", Text),
    Column("Arrival Time", Text),
)

# Clean NueGo services, one row per booking row (scripts/build_clean_tables.py, app/cleaning.py). seats_sold = total - available. ac/sleeper come from the team file and are NULL when unknown.
services = Table(
    "services", metadata,
    Column("service_id", Text),  # key
    Column("route_id", Text),
    Column("booking_id", Text),
    Column("booking_time", DateTime),
    Column("base_fare", BigInteger),
    Column("cancellation_charge", BigInteger),
    Column("fare_on_sale", BigInteger),
    Column("origin", Text),
    Column("destination", Text),
    Column("duration_hours", Float),
    Column("available_seats", BigInteger),
    Column("total_seats", BigInteger),
    Column("distance_km", BigInteger),
    Column("monthly_service_cost", BigInteger),
    Column("coach_cost_per_km", Float),
    Column("crew_cost", BigInteger),
    Column("tolls", BigInteger),
    Column("booking_status", Text),
    Column("refund_amount", BigInteger),
    Column("refund_status", Text),
    Column("holiday_event", Text),
    Column("avg_rating", Float),
    Column("num_ratings", BigInteger),
    Column("departure_at", DateTime),
    Column("arrival_at", DateTime),
    Column("seats_sold", BigInteger),
    Column("days_to_go", Float),
    Column("flag_missing_duration", Boolean),
    Column("flag_booked_after_departure", Boolean),
    Column("flag_seats_invalid", Boolean),
    Column("departure_month", Integer),
    Column("departure_weekday", Integer),
    Column("departure_hour", Integer),
    Column("holiday_score", Float),
    Column("flag_cancelled", Boolean),
    Column("ac", Float),
    Column("sleeper", Float),
    Column("coach_attrs_source", Text),
)

# Clean competitor snapshots. Join to services only on records captured at or before the prediction time.
competitor_fares = Table(
    "competitor_fares", metadata,
    Column("route_id", Text),
    Column("operator", Text),
    Column("base_fare", BigInteger),
    Column("fare", BigInteger),
    Column("total_seats", BigInteger),
    Column("available_seats", BigInteger),
    Column("captured_at", DateTime),
    Column("coach_type_raw", Text),
    Column("departure_at", DateTime),
    Column("flag_captured_after_departure", Boolean),
    Column("flag_fare_below_base", Boolean),
)

# Module A output per service (scripts/compute_pnl.py, app/pnl.py).
pnl_services = Table(
    "pnl_services", metadata,
    Column("service_id", Text),  # key
    Column("route_id", Text),
    Column("corridor", Text),
    Column("departure_at", DateTime),
    Column("departure_date", Text),
    Column("booking_status", Text),
    Column("seats_sold", BigInteger),
    Column("total_seats", BigInteger),
    Column("fare_on_sale", BigInteger),
    Column("gross_revenue", BigInteger),
    Column("refund", BigInteger),
    Column("revenue", BigInteger),
    Column("crew_cost_split", Float),
    Column("cost_to_run", Float),
    Column("flag_crew_split_assumed", Boolean),
    Column("flag_duration_from_route", Boolean),
    Column("profit", Float),
    Column("margin_pct", Float),
    Column("breakeven_fare_current_seats", Float),
    Column("breakeven_fare_full_coach", Float),
    Column("marginal_floor", Float),
    Column("marginal_floor_note", Text),
    Column("margin_status", Text),
    Column("route_history_days", BigInteger),
    Column("checkpoint_status", Text),
    Column("hours_to_departure", Float),
    Column("flag_cancelled", Boolean),
    Column("flag_revenue_is_estimate", Boolean),
    Column("expected_revenue_low", Float),
    Column("expected_margin_low", Float),
    Column("expected_revenue_mid", Float),
    Column("expected_margin_mid", Float),
    Column("expected_revenue_high", Float),
    Column("expected_margin_high", Float),
    Column("average_floor_low", Float),
    Column("average_floor_mid", Float),
    Column("average_floor_high", Float),
    Column("floor_switch_hours", Float),
    Column("floor_in_use", Text),
    Column("expected_margin_source", Text),
    Column("forecast_insufficient_data", Boolean),
)

# Reference fare from the team fare model. Reference only, never a suggested fare (scripts/compute_fare_predictions.py).
fare_predictions = Table(
    "fare_predictions", metadata,
    Column("service_id", Text),  # key
    Column("route_id", Text),
    Column("ac", Float),
    Column("sleeper", Float),
    Column("engine_fare", BigInteger),
    Column("comp_n", BigInteger),
    Column("comp_median_fare", Float),
    Column("fare_low", Float),
    Column("fare_mid", Float),
    Column("fare_high", Float),
    Column("insufficient_data", Boolean),
    Column("model_version", Text),
    Column("gap_to_engine", Float),
    Column("is_reference_only", Boolean),
)

# Expected seats sold from the team seat model (scripts/compute_forecasts.py).
seat_forecasts = Table(
    "seat_forecasts", metadata,
    Column("service_id", Text),  # key
    Column("route_id", Text),
    Column("ac", Float),
    Column("sleeper", Float),
    Column("total_seats", BigInteger),
    Column("actual_seats_sold", BigInteger),
    Column("days_to_go", Float),
    Column("expected_low", Float),
    Column("expected_mid", Float),
    Column("expected_high", Float),
    Column("insufficient_data", Boolean),
    Column("model_version", Text),
    Column("gap_to_expected", Float),
    Column("behind_checkpoint", Boolean),
)

# Real observed average seats sold by days-to-go band per route; no modelling (scripts/compute_forecasts.py).
seat_observed_points = Table(
    "seat_observed_points", metadata,
    Column("route_id", Text),
    Column("band", Text),
    Column("avg_seats_sold", Float),
    Column("n", BigInteger),
)
