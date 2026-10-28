import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main, pipeline


@pytest.fixture()
def eng(monkeypatch):
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(main, "engine", e)
    return e


def test_no_run_yet(eng):
    assert TestClient(main.app).get("/pipeline/status").json() == {"last_run": None}


def test_steps_run_in_order_and_the_run_is_recorded(eng):
    order = []
    pipeline.run(eng, [("a", lambda: order.append("a")), ("b", lambda: order.append("b"))])
    last = TestClient(main.app).get("/pipeline/status").json()["last_run"]
    assert order == ["a", "b"] and last["status"] == "ok" and last["steps_done"] == "a, b" and last["error"] is None


def test_a_failure_stops_the_run_is_recorded_and_raised(eng):
    def boom():
        raise RuntimeError("database unreachable")
    later = []
    with pytest.raises(RuntimeError):
        pipeline.run(eng, [("a", lambda: None), ("b", boom), ("c", lambda: later.append(1))])
    last = pipeline.last_run(eng)
    assert later == [] and last["status"] == "failed" and last["steps_done"] == "a" and last["error"] == "b: database unreachable"
