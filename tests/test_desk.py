from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import desk, main
from app.db import engine

NOW = datetime(2026, 10, 27, 14, 0)  # fixed, so the windows do not move


def test_windows_are_real_dates():
    dep = pd.Series(pd.to_datetime(["2026-10-26 23:00", "2026-10-27 08:00", "2026-10-28 08:00", "2026-11-26 08:00", "2026-11-27 08:00"]))
    got = {w: desk.in_window(dep, w, NOW).tolist() for w in desk.WINDOWS}
    assert got["today"] == [False, True, False, False, False]
    assert got["tomorrow"] == [False, False, True, False, False]
    assert got["next30"] == [False, True, True, True, False]
    assert got["earlier"] == [True, False, False, False, False]
    assert got["all"] == [True] * 5


def test_desk_page_is_ranked_worst_first_with_cancelled_and_unranked_apart():
    page = desk.desk_page(engine, "all", "", 1, now=NOW)
    ranks = [s["rank"] for s in page["items"] if s["rank"] is not None]
    assert ranks == list(range(1, len(ranks) + 1))
    scores = [s["score_parts"]["score"] for s in page["items"] if s["rank"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert all(not s["cancelled"] for s in page["items"]) and all(s["cancelled"] for s in page["cancelled"])
    assert all(s["rank"] is None for s in page["cancelled"]) and len(page["items"]) <= desk.PAGE_SIZE


def test_every_window_row_belongs_to_its_window_and_nothing_is_invented():
    for w in ("next30", "earlier"):
        page = desk.desk_page(engine, w, "", 1, now=NOW)
        mask = desk.in_window(pd.Series(pd.to_datetime([s["departure_at"] for s in page["items"] + page["cancelled"]])), w, NOW)
        assert mask.all()
    s = desk.desk_page(engine, "all", "", 1, now=NOW)["items"][0]
    for k in ("checkpoint", "cost_to_run", "margin_now", "coach_type"):
        assert k in s
    assert s["checkpoint"] is None or s["checkpoint"]["low"] <= s["checkpoint"]["mid"] <= s["checkpoint"]["high"]
    assert "synthetic_data" not in s["flags"]


def test_corridor_filter_and_summary_counts_match_the_list():
    page = desk.desk_page(engine, "all", "R002", 1, now=NOW)
    assert page["items"] and all(s["corridor_id"] == "R002" for s in page["items"] + page["cancelled"])
    summary = desk.desk_summary(engine, "all", "R002", now=NOW)
    assert summary["services"] == page["total"]
    assert summary["behind_checkpoint"] == sum(s["status"] == "behind" for s in page["items"])


def test_alerts_only_for_services_still_to_depart():
    items = desk.warnings(engine, now=datetime(2026, 1, 1))
    assert items and all(i["departure_at"] >= "2026-01-01" for i in items)
    assert all(i["seat_gap"] < 0 and i["checkpoint"]["low"] <= i["checkpoint"]["high"] for i in items)
    assert desk.warnings(engine, now=datetime(2030, 1, 1)) == []


def test_api_errors_and_shapes():
    c = TestClient(main.app)
    assert c.get("/desk/services", params={"window": "someday"}).status_code == 422
    assert c.get("/desk/summary", params={"window": "someday"}).status_code == 422
    assert c.get("/desk/services", params={"page": 0}).status_code == 422
    r = c.get("/routes").json()["items"]
    assert {x["id"] for x in r} >= {"R001", "R005"} and all(x["capacity"] == 40 for x in r)
    assert {u["role"] for u in c.get("/users").json()["items"]} == {"analyst", "admin"}
    assert c.get("/services/NOPE/whatif").status_code == 404


def test_whatif_rows_name_the_rule_that_blocks_a_fare():
    rows = TestClient(main.app).get("/services/BKG2026103/whatif").json()["rows"]
    assert rows and any(r["blocked_by"] for r in rows) and any(not r["blocked_by"] for r in rows)
    for r in rows:
        assert r["seats"]["low"] <= r["seats"]["mid"] <= r["seats"]["high"]
        assert r["margin"] is None or r["margin"]["low"] <= r["margin"]["mid"] <= r["margin"]["high"]
    assert sum(r["is_current"] for r in rows) == 1
    assert [r["fare"] for r in rows] == sorted(r["fare"] for r in rows)


@pytest.mark.parametrize("sid", ["BKG2023011", "BKG2026103"])
def test_suggested_fare_is_the_model_prediction_snapped_to_an_allowed_step(sid):
    s = TestClient(main.app).get(f"/services/{sid}/suggestion").json()
    p = s["predicted_fare"]
    assert p and p["low"] <= p["mid"] <= p["high"] and "linear regression" in p["label"]
    if s["suggested_fare"] is not None:
        rules = TestClient(main.app).get("/rules").json()
        near = min((f for f in rules["fare_steps"] if abs(f - s["fare_on_sale"]) <= s["fare_on_sale"] * rules["max_change_pct"] / 100
                    and f >= s["floor_value"] and f <= rules["ceiling"]), key=lambda f: (abs(f - p["mid"]), f))
        assert s["suggested_fare"] == near


def test_the_desk_frame_is_cached_briefly_then_rebuilt(monkeypatch):
    calls = []
    real = desk._build_frame
    monkeypatch.setattr(desk, "_build_frame", lambda e: calls.append(1) or real(e))
    desk._cache.clear()
    first = desk.desk_frame(engine)
    assert desk.desk_frame(engine) is first and len(calls) == 1  # second call is served from the cache
    desk.desk_summary(engine, "all", "", now=NOW)
    desk.desk_page(engine, "all", "", 1, now=NOW)
    assert len(calls) == 1  # summary and list share it
    key = id(engine)
    desk._cache[key] = (desk._cache[key][0] - desk.CACHE_SECONDS - 1, first)
    assert desk.desk_frame(engine) is not first and len(calls) == 2  # expired, rebuilt
