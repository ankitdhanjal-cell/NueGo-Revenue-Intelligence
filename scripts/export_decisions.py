"""Write every decision, with the final outcome where one is loaded, to a CSV for model retraining.

Read-only: it only reads the decisions and service_outcomes tables.

Run:  python -m scripts.export_decisions [out.csv]
"""
import sys

import pandas as pd

from app import decisions
from app.db import engine


def main(out: str) -> None:
    rows = decisions.list_decisions(engine)
    flat = pd.DataFrame([{**{k: v for k, v in d.items() if k != "outcome"},
                          "final_seats": (d["outcome"] or {}).get("final_seats"),
                          "final_revenue": (d["outcome"] or {}).get("revenue")} for d in rows])
    flat.to_csv(out, index=False)
    print(f"wrote {len(flat)} decisions to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "decisions_export.csv")
