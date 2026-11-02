"""What-if, sensitivity analysis, goal seeking and priority ranking.

Model variables (lecture Ch.7):
  * decision variables      : late_reduction (share of late orders made on time),
                              days_faster (days cut from every delivery)
  * uncontrollable variables: customer behaviour, captured by the tree's leaf rates
  * result variable         : expected bad-review rate
The model works under risk: each order gets a probability of a bad review
(its leaf's historical rate), and the expected rate is the mean probability.
"""
import numpy as np
import pandas as pd

from dss.train_model import build_features


def predict_bad_prob(bundle: dict, df: pd.DataFrame) -> np.ndarray:
    """Probability of a bad review for each order = bad-review rate of its leaf."""
    leaves = bundle["tree"].apply(build_features(df))
    leaf_rate = bundle["leaf_rate"]
    return np.array([leaf_rate[leaf] for leaf in leaves])


def simulate(df: pd.DataFrame, scope: pd.Series, late_reduction: float = 0.0, days_faster: int = 0) -> pd.DataFrame:
    """Return a copy of df with the scenario applied to the orders in scope."""
    sim = df.copy()
    if days_faster:
        sim.loc[scope, "delivery_days"] = (sim.loc[scope, "delivery_days"] - days_faster).clip(lower=0)
        sim.loc[scope, "delay_days"] = sim.loc[scope, "delivery_days"] - sim.loc[scope, "estimated_days"]
        sim.loc[scope, "is_late"] = (sim.loc[scope, "delay_days"] > 0).astype(int)
    if late_reduction > 0:
        # a late order that gets fixed arrives exactly on the estimated date
        fixed = scope & (sim["is_late"] == 1) & (sim["rand"] < late_reduction)
        sim.loc[fixed, "delivery_days"] = sim.loc[fixed, "estimated_days"]
        sim.loc[fixed, "delay_days"] = 0
        sim.loc[fixed, "is_late"] = 0
    return sim


def evaluate_scenario(bundle: dict, df: pd.DataFrame, scope: pd.Series,
                      late_reduction: float = 0.0, days_faster: int = 0) -> dict:
    p_before = predict_bad_prob(bundle, df)
    sim = simulate(df, scope, late_reduction, days_faster)
    p_after = predict_bad_prob(bundle, sim)
    s = scope.to_numpy()
    return {
        "n_orders_scope": int(s.sum()),
        "late_rate_before": float(df.loc[scope, "is_late"].mean()),
        "late_rate_after": float(sim.loc[scope, "is_late"].mean()),
        "actual_bad_rate_scope": float(df.loc[scope, "is_bad_review"].mean()),
        "bad_rate_before_scope": float(p_before[s].mean()),
        "bad_rate_after_scope": float(p_after[s].mean()),
        "bad_rate_before_all": float(p_before.mean()),
        "bad_rate_after_all": float(p_after.mean()),
        "bad_reviews_avoided": float((p_before - p_after).sum()),
    }


def sensitivity(bundle: dict, df: pd.DataFrame, scope: pd.Series, steps: int = 21) -> pd.DataFrame:
    """Expected bad-review rate (in scope) as late_reduction goes from 0% to 100%."""
    rows = []
    for r in np.linspace(0, 1, steps):
        res = evaluate_scenario(bundle, df, scope, late_reduction=r)
        rows.append({"late_reduction": r, "late_rate": res["late_rate_after"],
                     "bad_rate": res["bad_rate_after_scope"]})
    return pd.DataFrame(rows)


def goal_seek(bundle: dict, df: pd.DataFrame, scope: pd.Series, target_bad_rate: float):
    """Smallest late_reduction (searched in 1% steps, complete enumeration)
    that brings the expected bad-review rate in scope down to the target.
    Returns None if even fixing every late order is not enough."""
    for pct in range(0, 101):
        res = evaluate_scenario(bundle, df, scope, late_reduction=pct / 100)
        if res["bad_rate_after_scope"] <= target_bad_rate:
            return {"late_reduction": pct / 100, **res}
    return None


def priority_ranking(bundle: dict, df: pd.DataFrame, group_col: str, min_orders: int = 100) -> pd.DataFrame:
    """Rank groups (e.g. customer_state, category) by expected bad reviews
    avoided if every late order in the group were delivered on time."""
    all_orders = pd.Series(True, index=df.index)
    p_before = predict_bad_prob(bundle, df)
    p_after = predict_bad_prob(bundle, simulate(df, all_orders, late_reduction=1.0))
    work = df.assign(avoided=p_before - p_after,
                     late_value=np.where(df["is_late"] == 1, df["order_value"], 0.0))
    ranking = work.groupby(group_col).agg(
        n_orders=("order_id", "count"),
        late_rate=("is_late", "mean"),
        bad_review_rate=("is_bad_review", "mean"),
        bad_reviews_avoided=("avoided", "sum"),
        late_order_value=("late_value", "sum"),
    )
    ranking = ranking[ranking["n_orders"] >= min_orders]
    ranking["bad_rate_reduction_pts"] = ranking["bad_reviews_avoided"] / ranking["n_orders"]
    return ranking.sort_values("bad_reviews_avoided", ascending=False).reset_index()
