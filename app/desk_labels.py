"""Small shared label helpers (kept apart so app.suggestion and app.desk do not import each other)."""
import pandas as pd


def coach_label(ac, sleeper) -> str | None:
    """'AC Sleeper', 'Non-AC Seater', ... or None when the coach type is unknown. Never guessed."""
    if pd.isna(ac) or pd.isna(sleeper):
        return None
    return ("AC" if ac == 1 else "Non-AC") + (" Sleeper" if sleeper == 1 else " Seater")
