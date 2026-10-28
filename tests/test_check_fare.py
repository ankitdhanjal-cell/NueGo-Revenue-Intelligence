import pytest

from app.rules import RuleContext, check_fare


def _ctx(**changes):
    base = dict(current_fare=500.0, floor=450.0, ceiling=600.0, state_cap=None, max_change_pct=15.0,
                min_minutes_between_changes=240, minutes_since_last_change=None,
                fare_steps=[float(x) for x in range(400, 701, 10)])
    return RuleContext(**{**base, **changes})


def test_valid_fare_has_no_violations():
    assert check_fare(520.0, _ctx()) == []


@pytest.mark.parametrize("fare,ctx,code", [
    (525.0, _ctx(), "NOT_A_FARE_STEP"),
    (440.0, _ctx(current_fare=450.0, floor=450.0), "BELOW_FLOOR"),
    (610.0, _ctx(current_fare=600.0, max_change_pct=100), "ABOVE_CEILING"),
    (560.0, _ctx(state_cap=550.0), "ABOVE_STATE_CAP"),
    (580.0, _ctx(), "STEP_TOO_LARGE"),
    (510.0, _ctx(minutes_since_last_change=60), "TOO_SOON"),
])
def test_each_violation_code(fare, ctx, code):
    assert code in check_fare(fare, ctx)


def test_step_size_boundary_is_inclusive():
    assert check_fare(575.0, _ctx(fare_steps=[500.0, 575.0], ceiling=900)) == []  # exactly 15%


def test_too_soon_allows_only_the_current_fare():
    ctx = _ctx(minutes_since_last_change=60)
    assert check_fare(500.0, ctx) == [] and "TOO_SOON" in check_fare(510.0, ctx)
    assert "TOO_SOON" not in check_fare(510.0, _ctx(minutes_since_last_change=240))  # long enough
    assert "TOO_SOON" not in check_fare(510.0, _ctx(minutes_since_last_change=None))  # unknown: not checked


def test_several_violations_are_all_reported():
    assert set(check_fare(1000.0, _ctx(state_cap=700.0))) == {
        "NOT_A_FARE_STEP", "ABOVE_CEILING", "ABOVE_STATE_CAP", "STEP_TOO_LARGE"}
