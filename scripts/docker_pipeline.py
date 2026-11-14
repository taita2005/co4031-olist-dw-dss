"""Run one automatic Compose initialization step, skipping certified snapshots."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def should_run_etl(sales_exists, delivery_exists, ready):
    if not sales_exists and not delivery_exists:
        return True
    if sales_exists != delivery_exists:
        raise RuntimeError("DW is partially initialized; refusing to overwrite it. Inspect the database before recovery.")
    if ready is not True:
        raise RuntimeError("Existing DW checks are missing or failed; refusing to reload data automatically.")
    return False


def ensure_etl(sales_exists, delivery_exists, ready, run_etl):
    if should_run_etl(sales_exists, delivery_exists, ready):
        run_etl()
        return "loaded"
    return "skipped"


def should_train(etl_run_id, model_path, metadata_path):
    model_path, metadata_path = Path(model_path), Path(metadata_path)
    if not model_path.is_file() or not metadata_path.is_file():
        return True
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"DSS model metadata is unreadable at {metadata_path}; inspect or back it up before retrying.") from exc
    if not isinstance(metadata, dict) or metadata.get("etl_run_id") is None:
        raise RuntimeError(f"DSS model metadata has no etl_run_id at {metadata_path}; inspect or back it up before retrying.")
    return str(metadata["etl_run_id"]) != str(etl_run_id)


def ensure_model(etl_run_id, model_path, metadata_path, run_train):
    if should_train(etl_run_id, model_path, metadata_path):
        run_train()
        return "trained"
    return "skipped"


def _run(script):
    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def _dw_state():
    from sqlalchemy import text

    sys.path.insert(0, str(ROOT / "src"))
    from db import get_engine

    try:
        with get_engine().connect() as conn:
            sales_exists, delivery_exists = conn.execute(text(
                "SELECT to_regclass('dw.fact_sales') IS NOT NULL, "
                "to_regclass('dw.fact_delivery') IS NOT NULL"
            )).one()
            if not sales_exists and not delivery_exists:
                return sales_exists, delivery_exists, None, None
            if sales_exists != delivery_exists:
                return sales_exists, delivery_exists, None, None
            status = conn.execute(text(
                "SELECT etl_run_id, ready FROM bi.dataset_status"
            )).one()
            latest = conn.execute(text(
                "SELECT MAX(run_id) FROM meta.etl_log WHERE step='load'"
            )).scalar()
            return sales_exists, delivery_exists, status.ready is True and latest is not None and \
                str(status.etl_run_id) == str(latest), latest
    except Exception as exc:
        raise RuntimeError("Could not certify the existing DW; refusing to reload it automatically. "
                           "Inspect database state and logs before recovery.") from exc


def _latest_ready_run():
    sales_exists, delivery_exists, ready, run_id = _dw_state()
    if not sales_exists or not delivery_exists or ready is not True:
        raise RuntimeError("ETL did not produce a certified DW; refusing to train the DSS model.")
    return run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("etl", "train"))
    step = parser.parse_args().step
    if step == "etl":
        sales, delivery, ready, run_id = _dw_state()
        result = ensure_etl(sales, delivery, ready, lambda: _run("src/etl/run_etl.py"))
        if result == "skipped":
            print(f"Existing certified DW run {run_id}; ETL skipped.")
        else:
            print("DW was empty; ETL completed.")
    else:
        run_id = _latest_ready_run()
        model = ROOT / "models/decision_tree.joblib"
        metadata = ROOT / "models/metrics.json"
        result = ensure_model(run_id, model, metadata, lambda: _run("src/dss/train_model.py"))
        print(f"DSS model {result} for ETL run {run_id}.")


if __name__ == "__main__":
    main()
