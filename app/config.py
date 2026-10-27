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
