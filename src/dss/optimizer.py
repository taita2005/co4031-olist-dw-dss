"""Choice phase — budget allocation across states (0-1 integer programming).

Decision problem: with a limited budget, in which states should late
deliveries be reduced, and by how much, to avoid the most bad reviews?

Model (multiple-choice knapsack, lecture Ch.7 "mathematical programming"):
  decision variables : x[s, r] = 1 if state s gets late-order reduction r
  result variable    : expected bad reviews avoided = sum benefit[s, r] * x[s, r]
  constraints        : at most one level per state; total cost <= budget;
                       optionally at most K states (management capacity)

benefit[s, r] comes from the decision-tree risk model (whatif.evaluate_scenario)
and is pre-computed by build_options() when the model is trained, so the
dashboard only solves the small integer program. Orders in different states
are disjoint and each order's risk depends only on its own features, so the
benefits of different states add up exactly.

cost[s, r] (BRL) = freight actually paid for the late orders that level fixes
(real Olist data) x surcharge x tier[r]. Only the two parameters are
assumptions (config/cost_assumptions.csv):
  * surcharge : cost of the intervention (other carrier, extra hub, priority
                handling...) that makes a late order on time, as a share of
                its freight. Freight only measures how expensive logistics are
                in that state: within the same route and weight, paying more
                freight is NOT faster in Olist (checked, see config/README.md).
                It scales every cost equally, so it only rescales the budget
                and never changes which states are chosen.
  * tier[r]   : marginal cost multiplier per level; the last late orders are
                the hardest to fix. This one does shape the plan, see
                tier_sensitivity().
An incremental greedy heuristic is kept as a baseline to show what the exact
optimisation adds.
"""
import contextlib
import csv
import ctypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from dss.whatif import evaluate_scenario

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COST_PATH = PROJECT_ROOT / "config" / "cost_assumptions.csv"
OPTIONS_PATH = PROJECT_ROOT / "models" / "options.csv"

LEVELS = (0.25, 0.5, 0.75, 1.0)
# Alternative tier assumptions for the sensitivity analysis
TIER_SCENARIOS = {
    "flat": {0.25: 1.0, 0.5: 1.0, 0.75: 1.0, 1.0: 1.0},
    "default": {0.25: 1.0, 0.5: 1.2, 0.75: 1.5, 1.0: 2.0},
    "steep": {0.25: 1.0, 0.5: 1.5, 0.75: 2.25, 1.0: 3.5},
}


# ---------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------
def build_options(bundle: dict, df: pd.DataFrame, levels=LEVELS, min_orders: int = 100) -> pd.DataFrame:
    """One row per (state, level): late orders fixed, their freight, and bad reviews avoided."""
    rows = []
    for state, sub in df.groupby("customer_state"):
        if len(sub) < min_orders:
            continue
        everything = pd.Series(True, index=sub.index)
        n_late = int(sub["is_late"].sum())
        for level in levels:
            fixed = (sub["is_late"] == 1) & (sub["rand"] < level)
            if not fixed.any():
                continue
            res = evaluate_scenario(bundle, sub, everything, late_reduction=level)
            rows.append({
                "state": state,
                "region": sub["customer_region"].iloc[0],
                "n_orders": len(sub),
                "n_late": n_late,
                "level": level,
                "late_fixed": int(fixed.sum()),
                "freight_fixed": float(sub.loc[fixed, "freight_total"].sum()),  # BRL, real data
                "benefit": res["bad_reviews_avoided"],
                "bad_rate_before": res["bad_rate_before_scope"],
                "bad_rate_after": res["bad_rate_after_scope"],
            })
    return pd.DataFrame(rows)


def load_options(path: Path = OPTIONS_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run python src/dss/train_model.py")
    return pd.read_csv(path)


def load_cost_assumptions(path: Path = COST_PATH) -> tuple[float, dict]:
    """Return (surcharge, tier) from config/cost_assumptions.csv."""
    with open(path, encoding="utf-8", newline="") as f:
        values = {row["parameter"]: float(row["value"]) for row in csv.DictReader(f)}
    surcharge = values["surcharge"]
    tier = {level: values[f"tier_{round(level * 100)}"] for level in LEVELS}
    if surcharge <= 0 or any(t <= 0 for t in tier.values()):
        raise ValueError("cost assumptions must be positive")
    return surcharge, tier


def attach_costs(options: pd.DataFrame, surcharge: float, tier: dict) -> pd.DataFrame:
    """cost (BRL) = freight of the late orders fixed x surcharge x tier multiplier of the level."""
    missing = set(options["level"]) - set(tier)
    if missing:
        raise ValueError(f"no tier multiplier for levels: {sorted(missing)}")
    out = options.copy()
    out["cost"] = out["freight_fixed"] * surcharge * out["level"].map(tier)
    return out


# ---------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------
@dataclass
class Plan:
    method: str          # "optimal" (MILP) or "greedy"
    status: str          # "optimal", "time_limit", "heuristic", "empty"
    selected: pd.DataFrame
    cost: float
    benefit: float
    seconds: float


SELECTED_COLS = ["state", "region", "level", "late_fixed", "freight_fixed", "cost", "benefit"]


def _plan(method, status, options, chosen, started) -> Plan:
    sel = options.loc[chosen, SELECTED_COLS].sort_values("benefit", ascending=False).reset_index(drop=True)
    return Plan(method, status, sel, float(sel["cost"].sum()), float(sel["benefit"].sum()), time.perf_counter() - started)


def _flush_c_stdio() -> None:
    try:
        ctypes.CDLL(None).fflush(None)
    except (OSError, AttributeError):   # libc not reachable this way (e.g. Windows)
        pass


@contextlib.contextmanager
def _quiet_native_output():
    """Silence debug lines that the HiGHS C++ library prints to stdout (fd 1).

    HiGHS writes through C stdio buffers, so they are flushed while the file
    descriptors still point at /dev/null; otherwise the lines appear later.
    Python's own buffers are flushed first so no real output is lost.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        saved = {fd: os.dup(fd) for fd in (1, 2)}
    except OSError:          # no real file descriptors (some hosted environments)
        yield
        return
    with open(os.devnull, "w") as devnull:
        for fd in saved:
            os.dup2(devnull.fileno(), fd)
        try:
            yield
        finally:
            _flush_c_stdio()
            for fd, copy in saved.items():
                os.dup2(copy, fd)
                os.close(copy)


def solve(options: pd.DataFrame, budget: float, max_states: int | None = None, time_limit: float = 10) -> Plan:
    """Exact 0-1 integer program solved with scipy.optimize.milp (HiGHS)."""
    started = time.perf_counter()
    opts = options.reset_index(drop=True)
    if opts.empty or budget <= 0 or max_states == 0:
        return _plan("optimal", "empty", opts, [], started)

    states = opts["state"].to_numpy()
    unique_states = np.unique(states)
    one_level_per_state = (states[None, :] == unique_states[:, None]).astype(float)
    constraints = [
        LinearConstraint(one_level_per_state, -np.inf, 1),
        LinearConstraint(opts["cost"].to_numpy()[None, :], -np.inf, budget),
    ]
    if max_states is not None:
        constraints.append(LinearConstraint(np.ones((1, len(opts))), -np.inf, max_states))

    with _quiet_native_output():
        res = milp(
            c=-opts["benefit"].to_numpy(),      # milp minimises, we maximise benefit
            constraints=constraints,
            integrality=np.ones(len(opts)),
            bounds=Bounds(0, 1),
            options={"time_limit": time_limit},
        )
    if res.x is None:
        raise RuntimeError(f"MILP solver failed: {res.message}")
    status = "optimal" if res.status == 0 else "time_limit"
    return _plan("optimal", status, opts, np.flatnonzero(res.x > 0.5), started)


def greedy(options: pd.DataFrame, budget: float, max_states: int | None = None) -> Plan:
    """Baseline heuristic (incremental greedy, the usual one for multiple-choice knapsack).

    Every state starts at level 0. Each step takes the single move with the best
    marginal benefit per marginal cost that still fits the budget, where a move
    is raising one state from its current level to any higher level. It stops
    when no move fits. Fast and usually close to optimal, but with no guarantee.
    """
    started = time.perf_counter()
    opts = options.reset_index(drop=True)
    current = {}  # state -> row index of its current level
    remaining = budget
    while True:
        best, best_key = None, None
        for i, row in opts.iterrows():
            cur = current.get(row["state"])
            if cur is None and max_states is not None and len(current) >= max_states:
                continue  # cannot add another state
            base_cost = 0.0 if cur is None else opts.at[cur, "cost"]
            base_benefit = 0.0 if cur is None else opts.at[cur, "benefit"]
            if cur is not None and row["level"] <= opts.at[cur, "level"]:
                continue  # only upgrades
            d_cost, d_benefit = row["cost"] - base_cost, row["benefit"] - base_benefit
            if d_cost > remaining or d_benefit <= 0:
                continue
            key = (d_benefit / d_cost if d_cost > 0 else np.inf, d_benefit, -i)
            if best_key is None or key > best_key:
                best, best_key = i, key
        if best is None:
            break
        state = opts.at[best, "state"]
        remaining -= opts.at[best, "cost"] - (opts.at[current[state], "cost"] if state in current else 0.0)
        current[state] = best
    return _plan("greedy", "heuristic", opts, list(current.values()), started)


def frontier(options: pd.DataFrame, budgets, max_states: int | None = None) -> pd.DataFrame:
    """Budget sensitivity: best benefit (and greedy's) at each budget level."""
    rows = []
    for b in budgets:
        opt, gr = solve(options, b, max_states), greedy(options, b, max_states)
        rows.append({
            "budget": b,
            "optimal_benefit": opt.benefit, "optimal_cost": opt.cost, "optimal_states": len(opt.selected),
            "greedy_benefit": gr.benefit, "greedy_cost": gr.cost, "greedy_states": len(gr.selected),
            "gap_pct": 0.0 if opt.benefit == 0 else 100 * (opt.benefit - gr.benefit) / opt.benefit,
        })
    return pd.DataFrame(rows)


def tier_sensitivity(options: pd.DataFrame, budget: float, surcharge: float,
                     scenarios: dict = TIER_SCENARIOS, max_states: int | None = None) -> pd.DataFrame:
    """Does the optimal plan change when the tier assumption changes? One row per scenario."""
    rows = []
    for name, tier in scenarios.items():
        plan = solve(attach_costs(options, surcharge, tier), budget, max_states)
        rows.append({
            "scenario": name,
            "tier": " / ".join(f"{tier[l]:g}" for l in LEVELS),
            "benefit": plan.benefit,
            "cost": plan.cost,
            "n_states": len(plan.selected),
            "late_fixed": int(plan.selected["late_fixed"].sum()),
            "plan": ", ".join(f"{r.state} {r.level:.0%}" for r in plan.selected.sort_values("state").itertuples()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Implementation phase: plain-language recommendation
# ---------------------------------------------------------------------
def recommend(plan: Plan, budget: float, n_reviews: int, expected_bad_before: float) -> str:
    """Turn a plan into a recommendation a manager can act on (Vietnamese UI text)."""
    if plan.selected.empty:
        return f"Với ngân sách {budget:,.0f} BRL, không có phương án nào khả thi."
    by_level = plan.selected.sort_values(["level", "benefit"], ascending=[False, False]).groupby("level", sort=False)
    actions = "; ".join(f"giảm {level:.0%} đơn trễ ở {', '.join(g['state'])}" for level, g in by_level)
    rate_before = expected_bad_before / n_reviews
    rate_after = (expected_bad_before - plan.benefit) / n_reviews
    return (
        f"Với ngân sách {budget:,.0f} BRL: {actions} "
        f"(tổng chi phí {plan.cost:,.0f} BRL, {plan.selected['late_fixed'].sum():,} đơn trễ được xử lý). "
        f"Dự kiến tránh được khoảng {plan.benefit:,.0f} review xấu; tỷ lệ review xấu kỳ vọng toàn quốc "
        f"giảm từ {rate_before:.2%} xuống {rate_after:.2%}."
    )
