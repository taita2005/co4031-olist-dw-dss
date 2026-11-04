"""DSS behaviour on the real warehouse data (needs the database and the saved model)."""
import numpy as np
import pandas as pd
import pytest

from dss.whatif import evaluate_scenario, goal_seek, priority_ranking

LEVELS = np.linspace(0, 1, 11)


@pytest.fixture(scope="module")
def nationwide(dataset):
    return pd.Series(True, index=dataset.index)


def test_zero_scenario_changes_nothing(bundle, dataset, nationwide):
    res = evaluate_scenario(bundle, dataset, nationwide)
    assert res["bad_rate_after_all"] == pytest.approx(res["bad_rate_before_all"])
    assert res["bad_reviews_avoided"] == pytest.approx(0.0)


@pytest.mark.parametrize("state", [None, "RJ", "SP", "BA"])
def test_bad_review_rate_never_rises_as_late_orders_fall(bundle, dataset, nationwide, state):
    scope = nationwide if state is None else dataset["customer_state"] == state
    rates = [evaluate_scenario(bundle, dataset, scope, late_reduction=r)["bad_rate_after_scope"] for r in LEVELS]
    assert all(b <= a + 1e-12 for a, b in zip(rates, rates[1:])), rates
    assert rates[-1] < rates[0]


def test_late_rate_after_full_fix_is_zero(bundle, dataset, nationwide):
    res = evaluate_scenario(bundle, dataset, nationwide, late_reduction=1.0)
    assert res["late_rate_after"] == 0


def test_goal_seek_returns_the_smallest_sufficient_level(bundle, dataset, nationwide):
    before = evaluate_scenario(bundle, dataset, nationwide)["bad_rate_before_scope"]
    best = evaluate_scenario(bundle, dataset, nationwide, late_reduction=1.0)["bad_rate_after_scope"]
    target = (before + best) / 2
    found = goal_seek(bundle, dataset, nationwide, target)
    assert found is not None and found["bad_rate_after_scope"] <= target
    one_step_less = round(found["late_reduction"] - 0.01, 2)
    assert evaluate_scenario(bundle, dataset, nationwide, late_reduction=one_step_less)["bad_rate_after_scope"] > target


def test_goal_seek_already_met_and_unreachable(bundle, dataset, nationwide):
    before = evaluate_scenario(bundle, dataset, nationwide)["bad_rate_before_scope"]
    assert goal_seek(bundle, dataset, nationwide, before)["late_reduction"] == 0
    assert goal_seek(bundle, dataset, nationwide, 0.0) is None  # no leaf has a 0% bad-review rate


def test_priority_ranking_is_sorted_and_respects_min_orders(bundle, dataset):
    ranking = priority_ranking(bundle, dataset, "customer_state", min_orders=100)
    assert (ranking["n_orders"] >= 100).all()
    assert ranking["bad_reviews_avoided"].is_monotonic_decreasing
    assert (ranking["bad_reviews_avoided"] >= -1e-9).all()


# ---------------------------------------------------------------------
# Model selection evidence (models/experiments.json, metrics["leaf_check"])
# ---------------------------------------------------------------------
def test_experiments_cover_the_grid_and_mark_the_chosen_model(bundle):
    import json
    from dss.train_model import MODEL_DIR, PARAM_GRID, TREE_PARAMS
    rows = json.loads((MODEL_DIR / "experiments.json").read_text())["rows"]
    assert len(rows) == len(PARAM_GRID["max_depth"]) * len(PARAM_GRID["min_samples_leaf"])
    chosen = [r for r in rows if r["chosen"]]
    assert len(chosen) == 1
    assert {k: chosen[0][k] for k in TREE_PARAMS} == TREE_PARAMS == bundle["metrics"]["params"]
    assert chosen[0]["n_leaves"] == bundle["tree"].get_n_leaves()


def test_leaf_rates_hold_on_the_test_set(bundle):
    """The risk model is checked out of sample: predicted vs actual bad reviews on the 20% test set."""
    lc = bundle["metrics"]["leaf_check"]
    assert sum(leaf["n_test"] for leaf in lc["leaves"]) == lc["n_test"]
    assert lc["expected_bad_test"] == pytest.approx(lc["actual_bad_test"], rel=0.05)
    assert lc["weighted_mean_abs_diff_pts"] < 0.02
