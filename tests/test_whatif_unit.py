"""Unit tests for whatif.simulate on a tiny hand-made dataset (no database)."""
import pandas as pd
import pytest

from dss.whatif import simulate


@pytest.fixture
def orders():
    # delay_days = delivery_days - estimated_days; is_late = delay_days > 0
    return pd.DataFrame({
        "delivery_days":  [20, 15, 30, 8, 12, 25],
        "estimated_days": [10, 14, 20, 10, 12, 20],
        "delay_days":     [10,  1, 10, -2, 0,  5],
        "is_late":        [ 1,  1,  1,  0, 0,  1],
        "rand":           [0.1, 0.4, 0.8, 0.2, 0.5, 0.3],
        "state":          ["RJ", "RJ", "RJ", "RJ", "SP", "SP"],
    })


def test_fixed_late_orders_arrive_on_the_estimated_date(orders):
    sim = simulate(orders, pd.Series(True, index=orders.index), late_reduction=0.5)
    fixed = (orders["is_late"] == 1) & (orders["rand"] < 0.5)          # rows 0, 1, 5
    assert fixed.sum() == 3
    assert (sim.loc[fixed, "delivery_days"] == orders.loc[fixed, "estimated_days"]).all()
    assert (sim.loc[fixed, "delay_days"] == 0).all()
    assert (sim.loc[fixed, "is_late"] == 0).all()
    # late orders not selected, and on-time orders, are untouched
    assert sim.loc[~fixed].equals(orders.loc[~fixed])


def test_scope_limits_the_scenario(orders):
    scope = orders["state"] == "RJ"
    sim = simulate(orders, scope, late_reduction=1.0)
    assert sim.loc[scope, "is_late"].sum() == 0
    assert sim.loc[~scope].equals(orders.loc[~scope])  # SP row 5 is still late


def test_larger_reduction_fixes_a_superset(orders):
    """Orders are picked by the fixed rand column, so scenarios are nested (monotone results)."""
    everything = pd.Series(True, index=orders.index)
    still_late = [set(orders.index[simulate(orders, everything, late_reduction=r)["is_late"] == 1])
                  for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
    for bigger, smaller in zip(still_late, still_late[1:]):
        assert smaller <= bigger
    assert still_late[-1] == set()


def test_days_faster_recomputes_lateness_and_never_goes_negative(orders):
    sim = simulate(orders, pd.Series(True, index=orders.index), days_faster=10)
    assert (sim["delivery_days"] >= 0).all()
    assert (sim["delay_days"] == sim["delivery_days"] - sim["estimated_days"]).all()
    assert (sim["is_late"] == (sim["delay_days"] > 0).astype(int)).all()
    assert sim["is_late"].tolist() == [0, 0, 0, 0, 0, 0]


def test_no_scenario_changes_nothing(orders):
    assert simulate(orders, pd.Series(True, index=orders.index)).equals(orders)
