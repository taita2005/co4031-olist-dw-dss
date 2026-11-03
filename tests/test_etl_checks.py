"""Data quality checks (src/sql/05_checks.sql) — needs the loaded database.

1. The latest ETL run passed every check.
2. The checks are not vacuous: each one fails when the warehouse is
   deliberately broken. The damage is done inside a transaction that is
   always rolled back, so the real data is never changed.
3. Re-running the ETL gives the same result (idempotent full refresh).
"""
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text

CHECKS_SQL = (Path(__file__).resolve().parents[1] / "src" / "sql" / "05_checks.sql").read_text(encoding="utf-8")
MIN_CHECKS = 25


def latest_runs(conn, n):
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT run_id FROM meta.check_result ORDER BY run_id DESC LIMIT :n"), {"n": n})]


def test_latest_run_passes_all_checks(engine):
    with engine.connect() as conn:
        runs = latest_runs(conn, 1)
        assert runs, "no ETL run has recorded checks yet; run python src/etl/run_etl.py"
        rows = conn.execute(text(
            "SELECT check_name, expected, actual, passed FROM meta.check_result WHERE run_id = :r"),
            {"r": runs[0]}).all()
    assert len(rows) >= MIN_CHECKS
    failed = [r for r in rows if not r.passed]
    assert not failed, f"failed checks: {failed}"


# (description, SQL that damages dw, name of a check that must then fail)
BREAKAGES = [
    ("price changed during load",
     "UPDATE dw.fact_sales SET price = price * 10 "
     "WHERE (order_id, order_item_id) = (SELECT order_id, order_item_id FROM dw.fact_sales LIMIT 1)",
     "SUM(price): staging.order_items = fact_sales"),
    ("item row lost",
     "DELETE FROM dw.fact_sales "
     "WHERE (order_id, order_item_id) = (SELECT order_id, order_item_id FROM dw.fact_sales LIMIT 1)",
     "rows: staging.order_items = fact_sales"),
    ("item row duplicated into another partition (fan-out)",
     "INSERT INTO dw.fact_sales SELECT 20180101, customer_key, seller_key, product_key, order_id, order_item_id, "
     "order_status, price, freight_value, total_value FROM dw.fact_sales "
     "WHERE purchase_date_key < 20180101 LIMIT 1",
     "fact_sales: duplicate (order_id, order_item_id)"),
    ("delivered order lost",
     "DELETE FROM dw.fact_delivery WHERE order_id = (SELECT order_id FROM dw.fact_delivery LIMIT 1)",
     "rows: delivered orders with a delivery date = fact_delivery"),
    ("late flag wrong",
     "UPDATE dw.fact_delivery SET is_late = 1 - is_late "
     "WHERE order_id = (SELECT order_id FROM dw.fact_delivery LIMIT 1)",
     "is_late inconsistent with delay_days > 0"),
    ("bad-review flag wrong",
     "UPDATE dw.fact_delivery SET is_bad_review = 1 - is_bad_review "
     "WHERE order_id = (SELECT order_id FROM dw.fact_delivery WHERE review_score IS NOT NULL LIMIT 1)",
     "is_bad_review inconsistent with review_score <= 2"),
    ("review score out of range",
     "UPDATE dw.fact_delivery SET review_score = 7 "
     "WHERE order_id = (SELECT order_id FROM dw.fact_delivery WHERE review_score IS NOT NULL LIMIT 1)",
     "review_score outside 1..5"),
]


@pytest.mark.parametrize("description, damage, expected_failure", BREAKAGES, ids=[b[0] for b in BREAKAGES])
def test_checks_detect_broken_warehouse(engine, description, damage, expected_failure):
    run_id = datetime(1999, 1, 1)  # marker run; everything below is rolled back
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(damage)
        assert cur.rowcount == 1, f"damage statement for '{description}' touched {cur.rowcount} rows"
        cur.execute("SELECT set_config('etl.run_id', %s, false)", (run_id.isoformat(sep=" "),))
        cur.execute(CHECKS_SQL)
        cur.execute("SELECT check_name FROM meta.check_result WHERE run_id = %s AND NOT passed", (run_id,))
        failed = {r[0] for r in cur.fetchall()}
    finally:
        raw.rollback()
        raw.close()
    assert expected_failure in failed, f"'{description}' was not detected; failed checks: {failed}"


def test_rerun_gives_identical_results(engine):
    """Compare the two most recent ETL runs: same row counts and same check values."""
    with engine.connect() as conn:
        runs = latest_runs(conn, 2)
        if len(runs) < 2:
            pytest.skip("needs two ETL runs; run python src/etl/run_etl.py twice")
        q_log = text("SELECT step, table_name, source_rows, loaded_rows FROM meta.etl_log "
                     "WHERE run_id = :r ORDER BY step, table_name")
        q_chk = text("SELECT check_name, expected, actual FROM meta.check_result "
                     "WHERE run_id = :r ORDER BY check_name")
        newer, older = runs
        assert conn.execute(q_log, {"r": newer}).all() == conn.execute(q_log, {"r": older}).all()
        assert conn.execute(q_chk, {"r": newer}).all() == conn.execute(q_chk, {"r": older}).all()
