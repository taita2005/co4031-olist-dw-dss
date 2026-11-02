"""Model management subsystem — decision tree that predicts bad reviews.

Algorithm: decision tree with the entropy / information gain criterion
(ID3 / C4.5 family, lecture Ch.5). Target: is_bad_review (score <= 2).

The tree is used in two ways:
  * as a classifier (evaluated with accuracy / precision / recall / F1);
  * as a risk model: each leaf is a segment of orders, and the leaf's
    historical bad-review rate is the probability used by the what-if
    analysis (see whatif.py).

Usage:  python src/dss/train_model.py
Outputs: models/decision_tree.joblib, models/rules.txt, models/metrics.json
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
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


def train(engine=None, verbose: bool = True) -> dict:
    df = load_dataset(engine)
    X, y = build_features(df), df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    # class_weight='balanced' because bad reviews are the minority class
    tree = DecisionTreeClassifier(
        criterion="entropy", max_depth=4, min_samples_leaf=200, class_weight="balanced", random_state=42
    )
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
    }
    rules = extract_rules(tree, leaf_rate, leaf_size)
    rules_text = format_rules(rules) + "\n\n" + export_text(tree, feature_names=FEATURES)

    bundle = {"tree": tree, "features": FEATURES, "leaf_rate": leaf_rate, "metrics": metrics, "rules": rules}
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
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
