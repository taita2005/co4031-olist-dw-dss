"""Model management subsystem — decision tree that predicts bad reviews.

Algorithm: decision tree with the entropy / information gain criterion
(lecture Ch.5). scikit-learn implements CART: binary splits, with entropy as
the split criterion, so it is not ID3/C4.5 itself (those make multiway splits);
the gain computation is the same. Target: is_bad_review (score <= 2).

The tree is used in two ways:
  * as a classifier (evaluated with accuracy / precision / recall / F1);
  * as a risk model: each leaf is a segment of orders, and the leaf's
    historical bad-review rate is the probability used by the what-if
    analysis (see whatif.py).

Usage:  python src/dss/train_model.py
Outputs: models/decision_tree.joblib, models/rules.txt, models/metrics.json,
         models/options.csv (per state x level benefits for the budget optimiser),
         models/experiments.json (parameter grid evaluated by cross-validation)
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix, log_loss,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import get_engine, query  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "decision_tree.joblib"

REGIONS = ["North", "Northeast", "Central-West", "Southeast", "South"]
BASE_FEATURES = [
    "is_late", "delay_days", "delivery_days", "estimated_days",
    "n_items", "n_sellers", "freight_ratio", "same_state",
]
FEATURES = BASE_FEATURES + [f"region_{r}" for r in REGIONS]
TARGET = "is_bad_review"

DATASET_SQL = """
SELECT f.order_id, f.is_late, f.delay_days, f.delivery_days, f.estimated_days,
       f.n_items, f.n_sellers, f.order_value, f.freight_total, f.review_score, f.is_bad_review,
       c.state AS customer_state, c.region AS customer_region,
       s.state AS seller_state, p.category_en AS category
FROM dw.fact_delivery f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_seller   s ON s.seller_key   = f.seller_key
JOIN dw.dim_product  p ON p.product_key  = f.product_key
WHERE f.is_bad_review IS NOT NULL
"""


def load_dataset(engine=None) -> pd.DataFrame:
    """Delivered orders that have a review, read from the data warehouse."""
    df = query(engine or get_engine(), DATASET_SQL)
    for col in ["order_value", "freight_total"]:
        df[col] = df[col].astype(float)
    # fixed random number per order: what-if picks "which late orders get fixed"
    # with it, so a larger reduction always contains the smaller one
    df["rand"] = np.random.default_rng(42).random(len(df))
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn warehouse columns into the model's input matrix (attribute construction)."""
    X = pd.DataFrame(index=df.index)
    for col in ["is_late", "delay_days", "delivery_days", "estimated_days", "n_items", "n_sellers"]:
        X[col] = df[col]
    X["freight_ratio"] = df["freight_total"] / df["order_value"].where(df["order_value"] > 0)
    X["freight_ratio"] = X["freight_ratio"].fillna(0)
    X["same_state"] = (df["customer_state"] == df["seller_state"]).astype(int)
    for r in REGIONS:
        X[f"region_{r}"] = (df["customer_region"] == r).astype(int)
    return X[FEATURES]


def entropy(y: pd.Series) -> float:
    p = y.value_counts(normalize=True)
    return float(-(p * np.log2(p)).sum())


def information_gain(df: pd.DataFrame, attribute: str, target: str = TARGET) -> dict:
    """Info(D) - Info_A(D), computed by hand like the lecture's worked example."""
    info_d = entropy(df[target])
    info_a = sum(len(part) / len(df) * entropy(part[target]) for _, part in df.groupby(attribute))
    return {"attribute": attribute, "info_D": info_d, "info_A": info_a, "gain": info_d - info_a}


def extract_rules(tree: DecisionTreeClassifier, leaf_rate: dict, leaf_size: dict) -> list[dict]:
    """One IF-THEN rule per leaf, sorted from riskiest to safest segment."""
    t = tree.tree_
    rules = []

    def describe(bounds: dict) -> list[str]:
        # merge repeated tests on one feature into a single range, e.g. "1.5 < delay_days <= 4.5"
        parts = []
        for name, (low, high) in bounds.items():
            if low is not None and high is not None:
                parts.append(f"{low:g} < {name} <= {high:g}")
            elif low is not None:
                parts.append(f"{name} > {low:g}")
            else:
                parts.append(f"{name} <= {high:g}")
        return parts

    def walk(node: int, bounds: dict) -> None:
        if t.children_left[node] == -1:  # leaf
            rules.append({"conditions": describe(bounds), "n_orders": int(leaf_size.get(node, 0)),
                          "bad_rate": float(leaf_rate.get(node, 0.0))})
            return
        name, threshold = FEATURES[t.feature[node]], round(float(t.threshold[node]), 2)
        low, high = bounds.get(name, (None, None))
        walk(t.children_left[node], {**bounds, name: (low, threshold)})
        walk(t.children_right[node], {**bounds, name: (threshold, high)})

    walk(0, {})
    return sorted(rules, key=lambda r: -r["bad_rate"])


def format_rules(rules: list[dict]) -> str:
    return "\n".join(
        f"IF {' AND '.join(r['conditions'])} THEN P(bad review) = {r['bad_rate']:.1%} (n = {r['n_orders']:,})"
        for r in rules
    )


# Chosen parameters and the grid they were compared against (tree_experiments)
TREE_PARAMS = {"max_depth": 4, "min_samples_leaf": 200}
PARAM_GRID = {"max_depth": [3, 4, 5, 6], "min_samples_leaf": [100, 200, 500]}


def make_tree(max_depth: int, min_samples_leaf: int) -> DecisionTreeClassifier:
    # class_weight='balanced' because bad reviews are the minority class
    return DecisionTreeClassifier(criterion="entropy", max_depth=max_depth, min_samples_leaf=min_samples_leaf,
                                  class_weight="balanced", random_state=42)


def tree_experiments(X_train: pd.DataFrame, y_train: pd.Series) -> list[dict]:
    """Compare every parameter pair with 5-fold stratified cross-validation on the TRAINING set.

    Two groups of metrics, because the tree is used in two ways:
      * classifier (tree.predict): accuracy, precision, recall, F1 of the bad class;
      * risk model (leaf bad-review rate as probability, what whatif.py uses):
        Brier score and log-loss (lower is better), AUC (higher is better).
    The test set is not used here, so it stays an unbiased final check of the chosen model.
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    rows = []
    for depth in PARAM_GRID["max_depth"]:
        for leaf in PARAM_GRID["min_samples_leaf"]:
            folds = []
            for tr, va in cv.split(X_train, y_train):
                X_tr, y_tr, X_va, y_va = X_train.iloc[tr], y_train.iloc[tr], X_train.iloc[va], y_train.iloc[va]
                tree = make_tree(depth, leaf).fit(X_tr, y_tr)
                rate = pd.Series(y_tr.values).groupby(tree.apply(X_tr)).mean()
                prob = rate.reindex(tree.apply(X_va)).to_numpy()
                pred = tree.predict(X_va)
                precision, recall, f1, _ = precision_recall_fscore_support(y_va, pred, average="binary")
                folds.append({
                    "accuracy": accuracy_score(y_va, pred), "precision": precision, "recall": recall, "f1": f1,
                    "brier": brier_score_loss(y_va, prob), "log_loss": log_loss(y_va, np.clip(prob, 1e-6, 1 - 1e-6)),
                    "auc": roc_auc_score(y_va, prob),
                })
            folds = pd.DataFrame(folds)
            rows.append({
                "max_depth": depth, "min_samples_leaf": leaf,
                "n_leaves": int(make_tree(depth, leaf).fit(X_train, y_train).get_n_leaves()),
                **{f"cv_{m}": float(folds[m].mean()) for m in folds.columns},
                "cv_f1_std": float(folds["f1"].std()),
                "chosen": depth == TREE_PARAMS["max_depth"] and leaf == TREE_PARAMS["min_samples_leaf"],
            })
    return rows


def leaf_check(tree: DecisionTreeClassifier, leaf_rate: dict, leaf_size: dict,
               X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Are the leaf bad-review rates (learned on train) still right on unseen test orders?

    The what-if and the optimiser use leaf_rate as probabilities, so this is the
    out-of-sample check of the risk model, not only of the classifier.
    """
    test = pd.Series(y_test.values).groupby(tree.apply(X_test)).agg(["size", "mean"])
    leaves = []
    for leaf, rate in sorted(leaf_rate.items(), key=lambda kv: -kv[1]):
        n_test = int(test["size"].get(leaf, 0))
        leaves.append({"leaf": int(leaf), "n_train": int(leaf_size[leaf]), "rate_train": float(rate),
                       "n_test": n_test, "rate_test": float(test["mean"].get(leaf, np.nan)) if n_test else None})
    df = pd.DataFrame(leaves).dropna(subset=["rate_test"])
    weights = df["n_test"] / df["n_test"].sum()
    return {
        "leaves": leaves,
        "expected_bad_test": float((df["rate_train"] * df["n_test"]).sum()),   # what the risk model predicts
        "actual_bad_test": int(y_test.sum()),
        "n_test": int(len(y_test)),
        "weighted_mean_abs_diff_pts": float((weights * (df["rate_train"] - df["rate_test"]).abs()).sum()),
    }


def train(engine=None, verbose: bool = True) -> dict:
    df = load_dataset(engine)
    X, y = build_features(df), df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    tree = make_tree(**TREE_PARAMS)
    tree.fit(X_train, y_train)

    # Risk model: real (unweighted) bad-review rate of each leaf on the training data
    by_leaf = pd.Series(y_train.values).groupby(tree.apply(X_train))
    leaf_rate, leaf_size = by_leaf.mean().to_dict(), by_leaf.size().to_dict()

    y_pred = tree.predict(X_test)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary")
    metrics = {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "bad_review_rate": float(y.mean()),
        "accuracy": accuracy_score(y_test, y_pred),
        "precision_bad": precision,
        "recall_bad": recall,
        "f1_bad": f1,
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),  # [[TN, FP], [FN, TP]]
        "feature_importance": dict(sorted(
            zip(FEATURES, tree.feature_importances_.round(4).tolist()), key=lambda kv: -kv[1]
        )),
        "information_gain_is_late": information_gain(df, "is_late"),
        "params": TREE_PARAMS,
        "leaf_check": leaf_check(tree, leaf_rate, leaf_size, X_test, y_test),
    }
    rules = extract_rules(tree, leaf_rate, leaf_size)
    rules_text = format_rules(rules) + "\n\n" + export_text(tree, feature_names=FEATURES)

    bundle = {"tree": tree, "features": FEATURES, "leaf_rate": leaf_rate, "metrics": metrics, "rules": rules}

    # Pre-compute the optimiser's benefit table (imported here: optimizer -> whatif -> this module)
    from dss.optimizer import OPTIONS_PATH, build_options
    from dss.whatif import predict_bad_prob
    started = time.perf_counter()
    options = build_options(bundle, df)
    metrics["optimizer_baseline"] = {
        "n_reviews": len(df),
        "expected_bad_before": float(predict_bad_prob(bundle, df).sum()),
        "n_options": len(options),
        "n_states": int(options["state"].nunique()),
        "build_seconds": round(time.perf_counter() - started, 2),
    }

    started = time.perf_counter()
    experiments = {"method": "5-fold stratified CV on the training set (80%)",
                   "rows": tree_experiments(X_train, y_train)}
    experiments["seconds"] = round(time.perf_counter() - started, 2)

    MODEL_DIR.mkdir(exist_ok=True)
    (MODEL_DIR / "experiments.json").write_text(json.dumps(experiments, indent=2), encoding="utf-8")
    joblib.dump(bundle, MODEL_PATH)
    options.to_csv(OPTIONS_PATH, index=False)
    (MODEL_DIR / "rules.txt").write_text(rules_text, encoding="utf-8")
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if verbose:
        print(format_rules(rules))
        print(json.dumps(metrics, indent=2))
        print(f"Saved model to {MODEL_PATH}")
    return bundle


def load_model(engine=None) -> dict:
    """Load the saved model, training it first if it does not exist yet."""
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return train(engine, verbose=False)


if __name__ == "__main__":
    train()
