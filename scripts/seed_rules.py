"""Create `pricing_rules` and add the default row if the table is empty. Safe to re-run.

Run: python -m scripts.seed_rules
"""
from app.db import engine
from app.rules import active_rules


def main() -> None:
    r = active_rules(engine)
    print(f"pricing_rules: active version {r['version']}, ceiling {r['ceiling']}, {len(r['fare_steps'])} fare steps")


if __name__ == "__main__":
    main()
