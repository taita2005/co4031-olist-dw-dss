import os

import pytest
from sqlalchemy import create_engine, text


def test_bi_views_keep_grain_totals_and_complete_status(engine):
    with engine.connect() as conn:
        status = conn.execute(text("SELECT etl_run_id,check_count,failed_count,ready FROM bi.dataset_status")).one()
        assert status.ready is True
        assert status.check_count == 43
        assert status.failed_count == 0
        assert conn.execute(text("SELECT count(*)-count(DISTINCT (order_id,order_item_id)) FROM bi.sales_items")).scalar() == 0
        assert conn.execute(text("SELECT count(*)-count(DISTINCT order_id) FROM bi.delivery_orders")).scalar() == 0
        totals = conn.execute(text("""SELECT
             (SELECT sum(price) FROM bi.sales_items),
             (SELECT sum(price) FROM dw.fact_sales WHERE order_status NOT IN ('canceled','unavailable')),
             (SELECT count(DISTINCT order_id) FROM bi.sales_items),
             (SELECT count(DISTINCT order_id) FROM dw.fact_sales WHERE order_status NOT IN ('canceled','unavailable'))""")).one()
        assert totals[0] == totals[1]
        assert totals[2] == totals[3]
        months = conn.execute(text("""SELECT count(*) FROM (
            SELECT to_char(purchase_date,'YYYY-MM') AS year_month,sum(price) AS revenue
            FROM bi.sales_items GROUP BY 1
            EXCEPT
            SELECT year_month,revenue FROM dw.mv_monthly_kpi
        ) mismatch""")).scalar()
        assert months == 0
        deliveries = conn.execute(text("""SELECT
            (SELECT count(*) FROM bi.delivery_orders),
            (SELECT count(*) FROM dw.fact_delivery),
            (SELECT count(*) FILTER (WHERE is_late) FROM bi.delivery_orders),
            (SELECT sum(is_late) FROM dw.fact_delivery),
            (SELECT count(review_score) FROM bi.delivery_orders),
            (SELECT count(review_score) FROM dw.fact_delivery),
            (SELECT count(*) FILTER (WHERE is_bad_review) FROM bi.delivery_orders),
            (SELECT sum(is_bad_review) FROM dw.fact_delivery)""")).one()
        assert all(deliveries[i] == deliveries[i + 1] for i in (0, 2, 4, 6))
        bucket_count = conn.execute(text("SELECT sum(n) FROM (SELECT count(*) n FROM bi.delivery_orders GROUP BY delay_bucket,bucket_order) q")).scalar()
        assert bucket_count == deliveries[0]
        final_share = conn.execute(text("""WITH by_state AS (SELECT customer_state,sum(price) revenue FROM bi.sales_items GROUP BY 1),
            pareto AS (SELECT sum(sum(revenue)) OVER (ORDER BY sum(revenue) DESC,customer_state) /
                nullif(sum(sum(revenue)) OVER (),0) share FROM by_state GROUP BY customer_state)
            SELECT max(share) FROM pareto""")).scalar()
        assert final_share == 1


def test_quality_fail_missing_check_and_missing_run_marker_block_data(engine):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            run_id = conn.execute(text("SELECT etl_run_id FROM bi.dataset_status")).scalar()
            check_id = conn.execute(text("SELECT check_id FROM meta.check_result WHERE run_id=:r ORDER BY check_id LIMIT 1"),
                                    {"r": run_id}).scalar()
            conn.execute(text("UPDATE meta.check_result SET passed=false WHERE check_id=:id"), {"id": check_id})
            status = conn.execute(text("SELECT ready,failed_count FROM bi.dataset_status")).one()
            assert status.ready is False and status.failed_count > 0
            assert conn.execute(text("SELECT count(*) FROM bi.sales_items")).scalar() == 0
            assert conn.execute(text("SELECT count(*) FROM bi.delivery_orders")).scalar() == 0
        finally:
            tx.rollback()

        tx = conn.begin()
        try:
            run_id = conn.execute(text("SELECT etl_run_id FROM bi.dataset_status")).scalar()
            conn.execute(text("INSERT INTO meta.check_result (run_id,category,check_name,passed) "
                              "VALUES (:r,'synthetic','unexpected test failure',false)"), {"r": run_id})
            status = conn.execute(text("SELECT ready,failed_count FROM bi.dataset_status")).one()
            assert status.ready is False and status.failed_count > 0
            assert conn.execute(text("SELECT count(*) FROM bi.delivery_orders")).scalar() == 0
        finally:
            tx.rollback()

        tx = conn.begin()
        try:
            run_id = conn.execute(text("SELECT etl_run_id FROM bi.dataset_status")).scalar()
            check_id = conn.execute(text("SELECT check_id FROM meta.check_result WHERE run_id=:r ORDER BY check_id LIMIT 1"),
                                    {"r": run_id}).scalar()
            conn.execute(text("DELETE FROM meta.check_result WHERE check_id=:id"), {"id": check_id})
            status = conn.execute(text("SELECT ready,check_count,failed_count FROM bi.dataset_status")).one()
            assert status.ready is False and status.check_count == 42 and status.failed_count > 0
        finally:
            tx.rollback()

        tx = conn.begin()
        try:
            run_id = conn.execute(text("SELECT etl_run_id FROM bi.dataset_status")).scalar()
            conn.execute(text("DELETE FROM meta.etl_log WHERE run_id=:r AND step='run'"), {"r": run_id})
            assert conn.execute(text("SELECT ready FROM bi.dataset_status")).scalar() is False
            assert conn.execute(text("SELECT count(*) FROM bi.sales_items")).scalar() == 0
        finally:
            tx.rollback()


def test_metabase_role_reads_only_bi_views(engine):
    password = os.getenv("METABASE_RO_PASSWORD")
    if not password:
        pytest.skip("METABASE_RO_PASSWORD is supplied by the Compose integration environment")
    url = engine.url.set(username="metabase_ro", password=password)
    reader = create_engine(url)
    try:
        with reader.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM bi.dataset_status")).scalar() == 1
        for sql in ("SELECT count(*) FROM staging.orders", "INSERT INTO dw.fact_sales (purchase_date_key) VALUES (0)",
                    "UPDATE dw.fact_sales SET price=price WHERE false", "DELETE FROM dw.fact_sales WHERE false"):
            with reader.connect() as conn:
                tx = conn.begin()
                try:
                    with pytest.raises(Exception) as error:
                        conn.execute(text(sql))
                    assert getattr(error.value.orig, "pgcode", None) == "42501"
                finally:
                    tx.rollback()
    finally:
        reader.dispose()
