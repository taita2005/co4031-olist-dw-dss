"""Fail early with actionable instructions if the DW or DSS model is stale."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from db import get_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402


def check_ready():
    engine = get_engine()
    with engine.connect() as conn:
        status = conn.execute(text("SELECT etl_run_id, ready FROM bi.dataset_status")).one()
        latest = conn.execute(text("SELECT MAX(run_id) FROM meta.etl_log WHERE step='load'")).scalar()
    model_path = Path("models/decision_tree.joblib")
    metadata_path = Path("models/metrics.json")
    if latest is None or not status.ready:
        raise RuntimeError("DW checks are missing or failed. Run scripts/docker_bootstrap_db.py, then src/etl/run_etl.py.")
    if not model_path.is_file() or not metadata_path.is_file():
        raise RuntimeError("DSS model is missing. Run src/dss/train_model.py after a successful ETL.")
    model = json.loads(metadata_path.read_text(encoding="utf-8"))
    if str(model.get("etl_run_id")) != str(latest):
        raise RuntimeError("DSS model was trained on an older ETL run. Run src/dss/train_model.py again.")


if __name__ == "__main__":
    try:
        check_ready()
    except Exception as exc:
        print(f"Streamlit preflight failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    import subprocess
    raise SystemExit(subprocess.call([
        "streamlit", "run", "src/app/Home.py", "--server.address=0.0.0.0", "--server.port=8501",
        "--server.headless=true",
    ]))
