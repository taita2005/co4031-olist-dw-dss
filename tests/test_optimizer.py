"""Budget optimiser (src/dss/optimizer.py).

Unit tests use small hand-made or random option tables (no database); the
exact solver is checked against brute-force enumeration of every plan.
The last tests check models/options.csv against the what-if model (need DB).
"""
import itertools

import numpy as np
import pandas as pd
import pytest

from dss.optimizer import (LEVELS, TIER_SCENARIOS, attach_costs, frontier, greedy, load_cost_assumptions,
                           load_options, recommend, solve, tier_sensitivity)

TIER = TIER_SCENARIOS["default"]


def make_options(rows):
    """rows: (state, level, cost, benefit)"""
    df = pd.DataFrame(rows, columns=["state", "level", "cost", "benefit"])
    df["region"] = "X"
    df["late_fixed"] = 1
    df["freight_fixed"] = df["cost"]
    return df


def random_options(seed, n_states=5):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_states):
        unit = rng.uniform(0.5, 3)
        late = rng.integers(5, 60)
        benefit_per_order = rng.uniform(0.2, 0.6)
        for level in LEVELS:
            fixed = int(round(late * level))
            # benefit roughly proportional to orders fixed, with noise; cost convex via TIER
            rows.append((f"S{s}", level, fixed * unit * TIER[level],
                         fixed * benefit_per_order * rng.uniform(0.8, 1.2)))
    return make_options(rows)


def brute_force(options, budget, max_states=None):
    """Best total benefit over every assignment of one level (or none) per state."""
    groups = [g.index.tolist() + [None] for _, g in options.groupby("state")]
    best = 0.0
    for combo in itertools.product(*groups):
        chosen = [i for i in combo if i is not None]
        if max_states is not None and len(chosen) > max_states:
            continue
        if options.loc[chosen, "cost"].sum() <= budget + 1e-9:
            best = max(best, options.loc[chosen, "benefit"].sum())
    return best


def assert_feasible(plan, budget, max_states=None):
    assert plan.cost <= budget + 1e-6
    assert plan.selected["state"].is_unique                     # one level per state
    if max_states is not None:
        assert len(plan.selected) <= max_states


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("max_states", [None, 2])
def test_solver_matches_brute_force(seed, max_states):
    options = random_options(seed)
    total = options.groupby("state")["cost"].max().sum()
    for budget in (0.1 * total, 0.3 * total, 0.6 * total):
        plan = solve(options, budget, max_states)
        assert_feasible(plan, budget, max_states)
        assert plan.status == "optimal"
        assert plan.benefit == pytest.approx(brute_force(options, budget, max_states), rel=1e-6)


@pytest.mark.parametrize("seed", range(8))
def test_greedy_is_feasible_and_never_beats_the_optimum(seed):
    options = random_options(seed)
    for budget in (50, 150, 400):
        for k in (None, 2):
            g, opt = greedy(options, budget, k), solve(options, budget, k)
            assert_feasible(g, budget, k)
            assert g.benefit <= opt.benefit + 1e-6


def test_greedy_can_be_suboptimal():
    # A has the best ratio, but taking it leaves too little budget for B
    options = make_options([("A", 0.25, 1, 1.5), ("B", 0.25, 10, 10)])
    assert greedy(options, 10).benefit == pytest.approx(1.5)
    opt = solve(options, 10)
    assert opt.benefit == pytest.approx(10)
    assert opt.selected["state"].tolist() == ["B"]


def test_greedy_upgrades_a_state_instead_of_stopping():
    options = make_options([("A", 0.25, 1, 2), ("A", 1.0, 5, 8)])
    plan = greedy(options, 5)
    assert plan.selected["level"].tolist() == [1.0]
    assert plan.benefit == pytest.approx(8)


def test_no_budget_means_no_plan():
    options = random_options(0)
    for plan in (solve(options, 0), greedy(options, 0), solve(options, 100, max_states=0)):
        assert plan.selected.empty and plan.benefit == 0


def test_unlimited_budget_takes_the_best_level_everywhere():
    options = random_options(1)
    plan = solve(options, 1e9)
    assert plan.benefit == pytest.approx(options.groupby("state")["benefit"].max().sum())


def test_frontier_is_non_decreasing():
    f = frontier(random_options(2), [0, 20, 50, 100, 200, 400, 1e9])
    assert f["optimal_benefit"].is_monotonic_increasing
    assert (f["optimal_benefit"] >= f["greedy_benefit"] - 1e-6).all()


def test_attach_costs_formula_and_missing_level():
    options = pd.DataFrame({"state": ["RJ", "RJ"], "region": ["Southeast", "Southeast"], "level": [0.25, 1.0],
                            "late_fixed": [10, 40], "freight_fixed": [200.0, 900.0], "benefit": [1.0, 3.0]})
    costed = attach_costs(options, 0.5, TIER)
    assert costed["cost"].tolist() == [200.0 * 0.5 * TIER[0.25], 900.0 * 0.5 * TIER[1.0]]
    with pytest.raises(ValueError):
        attach_costs(options.assign(level=0.3), 0.5, TIER)


@pytest.mark.parametrize("seed", range(4))
def test_surcharge_only_rescales_the_budget(seed):
    """Doubling the surcharge and the budget gives the same plan (documented in config/README.md)."""
    options = random_options(seed).assign(freight_fixed=lambda d: d["cost"])
    for budget in (50, 150, 400):
        a = solve(attach_costs(options, 0.5, TIER), budget)
        b = solve(attach_costs(options, 1.0, TIER), 2 * budget)
        assert a.benefit == pytest.approx(b.benefit)
        assert sorted(zip(a.selected["state"], a.selected["level"])) == sorted(zip(b.selected["state"], b.selected["level"]))


def test_tier_sensitivity_reports_every_scenario():
    options = random_options(3).assign(freight_fixed=lambda d: d["cost"])
    table = tier_sensitivity(options, 150, 1.0)
    assert table["scenario"].tolist() == list(TIER_SCENARIOS)
    # cheaper deep levels (flat tier) can never be worse than the default tier
    flat, default = table.set_index("scenario").loc[["flat", "default"], "benefit"]
    assert flat >= default - 1e-6


def test_recommendation_mentions_every_action_and_the_effect():
    options = make_options([("RJ", 0.5, 300, 120.0), ("SP", 0.5, 400, 130.0), ("BA", 0.25, 100, 40.0)])
    plan = solve(options, 1000)
    text = recommend(plan, 1000, n_reviews=10_000, expected_bad_before=1_300)
    assert text.startswith("Với ngân sách 1,000 BRL")
    assert "giảm 50% đơn trễ ở SP, RJ" in text and "giảm 25% đơn trễ ở BA" in text
    assert "290 review xấu" in text and "13.00%" in text and "10.10%" in text
    assert "không có phương án" in recommend(solve(options, 0), 0, 10_000, 1_300)


def test_shipped_cost_assumptions():
    surcharge, tier = load_cost_assumptions()
    assert surcharge > 0
    assert set(tier) == set(LEVELS)
    assert [tier[l] for l in sorted(tier)] == sorted(tier.values())  # marginal cost never falls


# ---------------------------------------------------------------------
# models/options.csv vs the what-if model (needs the database + trained model)
# ---------------------------------------------------------------------
def test_options_benefit_grows_with_the_level(bundle):
    options = load_options()
    for _, g in options.groupby("state"):
        g = g.sort_values("level")
        assert g["late_fixed"].is_monotonic_increasing
        assert g["benefit"].is_monotonic_increasing


def test_options_freight_is_the_real_freight_of_fixed_orders(bundle, dataset):
    options = load_options()
    for row in options.sample(10, random_state=0).itertuples():
        sub = dataset[dataset["customer_state"] == row.state]
        fixed = (sub["is_late"] == 1) & (sub["rand"] < row.level)
        assert row.late_fixed == fixed.sum()
        assert row.freight_fixed == pytest.approx(sub.loc[fixed, "freight_total"].sum())


def test_options_match_priority_ranking(bundle, dataset):
    """Per-state benefit at 100% equals the what-if ranking (benefits of states add up)."""
    from dss.whatif import priority_ranking
    ranking = priority_ranking(bundle, dataset, "customer_state", min_orders=100).set_index("customer_state")
    full = load_options().query("level == 1.0").set_index("state")
    assert set(full.index) == set(ranking.index[ranking["bad_reviews_avoided"] > 0])
    for state, row in full.iterrows():
        assert row["benefit"] == pytest.approx(ranking.at[state, "bad_reviews_avoided"], rel=1e-9)
