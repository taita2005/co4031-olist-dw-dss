"""Shared pytest fixtures.

Unit tests (test_whatif_unit.py) need nothing but the Python env.
Tests that use the `engine`, `bundle` or `dataset` fixtures need the
project database to be running and loaded (`bash scripts/db_start.sh`,
`python src/etl/run_etl.py`); they are skipped when it is unreachable.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import get_engine  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM dw.fact_delivery LIMIT 1"))
    except Exception as exc:  # noqa: BLE001 - any connection problem means "no DB"
        pytest.skip(f"database not available: {exc.__class__.__name__}")
    return eng


@pytest.fixture(scope="session")
def dataset(engine):
    from dss.train_model import load_dataset
    return load_dataset(engine)


@pytest.fixture(scope="session")
def bundle(engine):
    from dss.train_model import load_model
    return load_model(engine)
