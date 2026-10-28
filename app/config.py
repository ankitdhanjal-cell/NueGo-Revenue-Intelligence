"""Settings that are assumptions, not data. Change them in .env."""
import os

# The brief: when only route-level monthly totals exist, split crew by scheduled hours.
# The data does not say how many trips a route runs per month, so this is an explicit
# assumption (30 = one departure a day). Set TRIPS_PER_ROUTE_MONTH in .env to the real number.
TRIPS_PER_ROUTE_MONTH = int(os.getenv("TRIPS_PER_ROUTE_MONTH", "30"))

# Attention ranking: score = W_BEHIND * (seats behind checkpoint / total seats)
#                          + W_MARGIN * (expected loss / cost to run, capped at 1)
W_BEHIND = float(os.getenv("RANK_W_BEHIND", "0.5"))
W_MARGIN = float(os.getenv("RANK_W_MARGIN", "0.5"))

# Which cost floor applies: average floor (advance pricing) until this many hours before
# departure, then the marginal floor. Which switch point GreenCell wants is an open question,
# so this is a setting and the value used is recorded on every row.
FLOOR_SWITCH_HOURS = float(os.getenv("FLOOR_SWITCH_HOURS", "24"))
MIN_HISTORY_DAYS = 28  # under 4 weeks of route history -> checkpoint "no history"

# Module B: values used to seed the first row of `pricing_rules`. After that the table is the
# single source of truth (GET/PUT /rules). Every one of these is an ASSUMPTION to confirm with GreenCell.
DEFAULT_RULES = dict(
    floor_switch_hours=FLOOR_SWITCH_HOURS,   # average floor until this many hours before departure
    ceiling=1500.0,                          # highest fare ever suggested (INR)
    state_cap=None,                          # legal cap in INR; None = no cap known
    max_change_pct=15.0,                     # largest change per step, % of the current fare
    min_minutes_between_changes=240,         # shortest time between two fare changes
    seats_weight=0.0,                        # INR value of one extra expected seat (0 = margin only)
    fare_steps=list(range(200, 1501, 10)),   # allowed fares, every INR 10
)

# Module B price response: a segment needs at least this many services and distinct fares
# before a slope is called "enough data". Both are assumptions, not data.
MIN_ELASTICITY_SERVICES = int(os.getenv("MIN_ELASTICITY_SERVICES", "30"))
MIN_ELASTICITY_FARES = int(os.getenv("MIN_ELASTICITY_FARES", "5"))

# Module B booking-curve band: a group of similar past services needs at least this many
# services before its p10/p50/p90 is shown. Fewer = "no history". An assumption, not data.
MIN_BAND_SERVICES = int(os.getenv("MIN_BAND_SERVICES", "4"))

# Auth stub: the UI sends X-User-Id. Only an admin may change the pricing rules.
# Replace with the real identity provider; these are placeholders, not people.
USERS = [
    {"id": "analyst-1", "name": "Pricing analyst 1", "role": "analyst"},
    {"id": "analyst-2", "name": "Pricing analyst 2", "role": "analyst"},
    {"id": "admin", "name": "Admin", "role": "admin"},
]
