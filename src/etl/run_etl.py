"""ETL pipeline: CSV files -> staging schema -> dw schema (full refresh).

Steps
  1. Extract   : create staging tables and bulk-load the raw CSVs (COPY).
  2. Transform : 02_dw_schema.sql + 03_transform_load.sql (cleansing,
     + Load      mapping, business rules, insert into dimensions/facts).
  3. Aggregate : 04_olap_views.sql (materialized views for ROLAP).
  4. Metadata  : every step writes row counts to meta.etl_log.
  5. Checks    : 05_checks.sql reconciles dw against staging and writes
                 the results to meta.check_result. The run is still
                 committed when a check fails (so it can be inspected),
                 but the script exits with status 1.

Usage:  python src/etl/run_etl.py [--data-dir data]
"""
import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import get_engine  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "src" / "sql"

# staging table -> source CSV file
SOURCE_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

DW_TABLES = ["dim_date", "dim_customer", "dim_seller", "dim_product", "fact_sales", "fact_delivery"]


def count_csv_rows(path: Path) -> int:
    """Count data rows with a real CSV parser (review comments contain newlines)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def run_sql_file(cur, name: str) -> None:
    print(f"  running {name}")
    cur.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def count_rows(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def log(cur, run_id, step, table, source_rows, loaded_rows, note=None) -> None:
    cur.execute(
        "INSERT INTO meta.etl_log (run_id, step, table_name, source_rows, loaded_rows, note) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (run_id, step, table, source_rows, loaded_rows, note),
    )


def extract(cur, data_dir: Path) -> list[tuple]:
    run_sql_file(cur, "01_staging.sql")
    stats = []
    for table, filename in SOURCE_FILES.items():
        path = data_dir / filename
        if not path.exists():
            sys.exit(f"Missing source file: {path}")
        # utf-8-sig strips the BOM at the start of the translation file
        with open(path, encoding="utf-8-sig", newline="") as f:
            cur.copy_expert(f"COPY staging.{table} FROM STDIN WITH (FORMAT csv, HEADER true)", f)
        source_rows = count_csv_rows(path)
        loaded_rows = count_rows(cur, f"staging.{table}")
        stats.append((f"staging.{table}", source_rows, loaded_rows))
        print(f"  staging.{table:<22} {loaded_rows:>8,} rows")
    return stats


def transform_and_load(cur) -> None:
    run_sql_file(cur, "02_dw_schema.sql")
    run_sql_file(cur, "03_transform_load.sql")
    run_sql_file(cur, "04_olap_views.sql")


def run_checks(cur, run_id) -> list[tuple]:
    """Run 05_checks.sql for this run and return (category, name, expected, actual, passed)."""
    cur.execute("SELECT set_config('etl.run_id', %s, false)", (run_id.isoformat(sep=" "),))
    run_sql_file(cur, "05_checks.sql")
    cur.execute(
        "SELECT category, check_name, expected, actual, passed FROM meta.check_result "
        "WHERE run_id = %s ORDER BY check_id",
        (run_id,),
    )
    return cur.fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=PROJECT_ROOT / "data", type=Path)
    args = parser.parse_args()

    run_id = datetime.now()
    started = time.time()
    conn = get_engine().raw_connection()
    try:
        cur = conn.cursor()
        print("[1/4] Extract -> staging")
        staging_stats = extract(cur, args.data_dir)

        print("[2/4] Transform + Load -> dw")
        transform_and_load(cur)

        print("[3/4] Metadata -> meta.etl_log")
        for table, source_rows, loaded_rows in staging_stats:
            log(cur, run_id, "extract", table, source_rows, loaded_rows)

        # The "source" of each dw table is the staging table it is derived from
        source_of = {
            "dim_customer": ("staging.customers", "deduplicated to customer_unique_id"),
            "dim_seller": ("staging.sellers", None),
            "dim_product": ("staging.products", None),
            "fact_sales": ("staging.order_items", None),
            "fact_delivery": ("staging.orders", "only delivered orders with a delivery date"),
        }
        for table in DW_TABLES:
            loaded = count_rows(cur, f"dw.{table}")
            source_table, note = source_of.get(table, (None, "generated calendar 2016-2018"))
            source = count_rows(cur, source_table) if source_table else None
            log(cur, run_id, "load", f"dw.{table}", source, loaded, note)
            print(f"  dw.{table:<16} {loaded:>8,} rows" + (f"  (from {source:,} in {source_table})" if source else ""))

        print("[4/4] Checks -> meta.check_result")
        checks = run_checks(cur, run_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    failed = [c for c in checks if not c[4]]
    for category, name, expected, actual, passed in checks:
        status = "ok  " if passed else "FAIL"
        detail = "" if passed else f"  (expected {expected}, actual {actual})"
        print(f"  {status} [{category}] {name}{detail}")
    print(f"ETL finished in {time.time() - started:.1f}s; "
          f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
