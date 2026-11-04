-- =====================================================================
-- 05_checks.sql — Data quality checks, run at the end of every ETL run.
--
-- Each check compares an EXPECTED value with the ACTUAL value in dw.
-- Expected values are recomputed directly from staging (not by reusing
-- the transform logic), so a bug in 03_transform_load.sql shows up as a
-- mismatch instead of being copied into both sides.
--
-- Results go to meta.check_result, which (like meta.etl_log) lives outside
-- dw and survives the full refresh. run_etl.py sets 'etl.run_id' first.
-- =====================================================================
CREATE TABLE IF NOT EXISTS meta.check_result (
    check_id    SERIAL PRIMARY KEY,
    run_id      TIMESTAMP NOT NULL,
    category    TEXT      NOT NULL,   -- grain | reconciliation | domain | coverage | aggregate
    check_name  TEXT      NOT NULL,
    expected    NUMERIC,
    actual      NUMERIC,
    passed      BOOLEAN   NOT NULL,
    note        TEXT,
    checked_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TEMP TABLE chk (category TEXT, check_name TEXT, expected NUMERIC, actual NUMERIC, note TEXT);

-- Orders that should reach fact_delivery (business rule, recomputed from staging)
CREATE TEMP TABLE src_delivered AS
SELECT order_id,
       order_delivered_customer_date::TIMESTAMP::DATE  AS delivered_date,
       order_estimated_delivery_date::TIMESTAMP::DATE  AS estimated_date
FROM staging.orders
WHERE order_status = 'delivered'
  AND NULLIF(order_delivered_customer_date, '') IS NOT NULL;

-- ---------------------------------------------------------------------
-- 1. Grain: one row per declared grain, no duplicates
-- ---------------------------------------------------------------------
INSERT INTO chk SELECT 'grain', 'fact_sales: duplicate (order_id, order_item_id)', 0,
    (SELECT COUNT(*) FROM (SELECT 1 FROM dw.fact_sales GROUP BY order_id, order_item_id HAVING COUNT(*) > 1) d),
    'grain = one item in one order';
INSERT INTO chk SELECT 'grain', 'fact_delivery: duplicate order_id', 0,
    (SELECT COUNT(*) FROM (SELECT 1 FROM dw.fact_delivery GROUP BY order_id HAVING COUNT(*) > 1) d),
    'grain = one delivered order';
INSERT INTO chk SELECT 'grain', 'dim_customer: duplicate customer_unique_id', 0,
    (SELECT COUNT(*) - COUNT(DISTINCT customer_unique_id) FROM dw.dim_customer), NULL;

-- ---------------------------------------------------------------------
-- 2. Reconciliation: row counts and money totals, staging vs dw
-- ---------------------------------------------------------------------
INSERT INTO chk SELECT 'reconciliation', 'rows: staging.order_items = fact_sales',
    (SELECT COUNT(*) FROM staging.order_items), (SELECT COUNT(*) FROM dw.fact_sales), NULL;
INSERT INTO chk SELECT 'reconciliation', 'SUM(price): staging.order_items = fact_sales',
    (SELECT SUM(price::NUMERIC) FROM staging.order_items), (SELECT SUM(price) FROM dw.fact_sales), NULL;
INSERT INTO chk SELECT 'reconciliation', 'SUM(freight_value): staging.order_items = fact_sales',
    (SELECT SUM(freight_value::NUMERIC) FROM staging.order_items), (SELECT SUM(freight_value) FROM dw.fact_sales), NULL;
INSERT INTO chk SELECT 'reconciliation', 'rows: delivered orders with a delivery date = fact_delivery',
    (SELECT COUNT(*) FROM src_delivered), (SELECT COUNT(*) FROM dw.fact_delivery), NULL;
INSERT INTO chk SELECT 'reconciliation', 'SUM(order_value): items of delivered orders = fact_delivery',
    (SELECT SUM(i.price::NUMERIC) FROM staging.order_items i JOIN src_delivered d USING (order_id)),
    (SELECT SUM(order_value) FROM dw.fact_delivery),
    'order-level value must not be multiplied by items or reviews';
INSERT INTO chk SELECT 'reconciliation', 'late orders: staging = SUM(fact_delivery.is_late)',
    (SELECT COUNT(*) FROM src_delivered WHERE delivered_date > estimated_date),
    (SELECT SUM(is_late) FROM dw.fact_delivery), NULL;
INSERT INTO chk SELECT 'reconciliation', 'delivered orders with a review = fact_delivery rows with review_score',
    (SELECT COUNT(*) FROM src_delivered d
      WHERE EXISTS (SELECT 1 FROM staging.order_reviews r WHERE r.order_id = d.order_id)),
    (SELECT COUNT(review_score) FROM dw.fact_delivery), 'multiple reviews per order collapse to one';
INSERT INTO chk SELECT 'reconciliation', 'rows: distinct customer_unique_id = dim_customer',
    (SELECT COUNT(DISTINCT customer_unique_id) FROM staging.customers), (SELECT COUNT(*) FROM dw.dim_customer), NULL;
INSERT INTO chk SELECT 'reconciliation', 'rows: staging.sellers = dim_seller',
    (SELECT COUNT(*) FROM staging.sellers), (SELECT COUNT(*) FROM dw.dim_seller), NULL;
INSERT INTO chk SELECT 'reconciliation', 'rows: staging.products = dim_product',
    (SELECT COUNT(*) FROM staging.products), (SELECT COUNT(*) FROM dw.dim_product), NULL;

-- ---------------------------------------------------------------------
-- 3. Domain rules (expected = 0 violations)
-- ---------------------------------------------------------------------
INSERT INTO chk SELECT 'domain', 'review_score outside 1..5', 0,
    (SELECT COUNT(*) FROM dw.fact_delivery WHERE review_score NOT BETWEEN 1 AND 5), NULL;
INSERT INTO chk SELECT 'domain', 'is_bad_review inconsistent with review_score <= 2', 0,
    (SELECT COUNT(*) FROM dw.fact_delivery
      WHERE is_bad_review IS DISTINCT FROM CASE WHEN review_score IS NULL THEN NULL
                                                WHEN review_score <= 2 THEN 1 ELSE 0 END), NULL;
INSERT INTO chk SELECT 'domain', 'is_late inconsistent with delay_days > 0', 0,
    (SELECT COUNT(*) FROM dw.fact_delivery WHERE is_late <> (delay_days > 0)::INT), NULL;
INSERT INTO chk SELECT 'domain', 'delay_days <> delivery_days - estimated_days', 0,
    (SELECT COUNT(*) FROM dw.fact_delivery WHERE delay_days <> delivery_days - estimated_days), NULL;
INSERT INTO chk SELECT 'domain', 'negative delivery_days or estimated_days', 0,
    (SELECT COUNT(*) FROM dw.fact_delivery WHERE delivery_days < 0 OR estimated_days < 0), NULL;
INSERT INTO chk SELECT 'domain', 'price <= 0 or freight_value < 0', 0,
    (SELECT COUNT(*) FROM dw.fact_sales WHERE price <= 0 OR freight_value < 0), NULL;
INSERT INTO chk SELECT 'domain', 'total_value <> price + freight_value', 0,
    (SELECT COUNT(*) FROM dw.fact_sales WHERE total_value <> price + freight_value), NULL;

-- ---------------------------------------------------------------------
-- 4. Coverage: every source date falls inside dim_date
--    (FKs already block orphan keys; this catches dates silently dropped
--    or mis-keyed if the calendar range were too short)
-- ---------------------------------------------------------------------
INSERT INTO chk SELECT 'coverage', 'source purchase/delivery dates outside dim_date', 0,
    (SELECT COUNT(*) FROM staging.orders o
      WHERE NOT EXISTS (SELECT 1 FROM dw.dim_date d WHERE d.full_date = o.order_purchase_timestamp::TIMESTAMP::DATE)
         OR (NULLIF(o.order_delivered_customer_date, '') IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM dw.dim_date d
                             WHERE d.full_date = o.order_delivered_customer_date::TIMESTAMP::DATE))), NULL;

INSERT INTO chk SELECT 'coverage', 'products with a source category but no English name', 0,
    (SELECT COUNT(*) FROM dw.dim_product WHERE category_pt <> 'unknown' AND category_en = 'unknown'),
    'mapping PT -> EN, including the 2 categories missing from the translation file';
INSERT INTO chk SELECT 'coverage', 'customers/sellers with a state but no region', 0,
    (SELECT COUNT(*) FROM dw.dim_customer WHERE region = 'Unknown')
  + (SELECT COUNT(*) FROM dw.dim_seller   WHERE region = 'Unknown'),
    'mapping UF -> region';

-- ---------------------------------------------------------------------
-- 5. Aggregates: materialized views agree with the facts they summarise
-- ---------------------------------------------------------------------
INSERT INTO chk SELECT 'aggregate', 'mv_sales_cube grand total = fact_sales (excl. canceled/unavailable)',
    (SELECT SUM(price) FROM dw.fact_sales WHERE order_status NOT IN ('canceled', 'unavailable')),
    (SELECT revenue FROM dw.mv_sales_cube WHERE year IS NULL AND customer_region IS NULL AND category IS NULL),
    'CUBE subtotal row (all NULL) = grand total';
INSERT INTO chk SELECT 'aggregate', 'SUM(mv_monthly_kpi.revenue) = fact_sales (excl. canceled/unavailable)',
    (SELECT SUM(price) FROM dw.fact_sales WHERE order_status NOT IN ('canceled', 'unavailable')),
    (SELECT SUM(revenue) FROM dw.mv_monthly_kpi), NULL;
INSERT INTO chk SELECT 'aggregate', 'SUM(mv_delivery_by_state.n_orders) = fact_delivery',
    (SELECT COUNT(*) FROM dw.fact_delivery), (SELECT SUM(n_orders) FROM dw.mv_delivery_by_state), NULL;
INSERT INTO chk SELECT 'aggregate', 'rates in materialized views outside [0, 1]', 0,
    (SELECT COUNT(*) FROM dw.mv_delivery_by_state
      WHERE late_rate NOT BETWEEN 0 AND 1 OR bad_review_rate NOT BETWEEN 0 AND 1)
  + (SELECT COUNT(*) FROM dw.mv_monthly_kpi
      WHERE late_rate NOT BETWEEN 0 AND 1 OR bad_review_rate NOT BETWEEN 0 AND 1), NULL;

INSERT INTO meta.check_result (run_id, category, check_name, expected, actual, passed, note)
SELECT current_setting('etl.run_id')::TIMESTAMP, category, check_name, expected, actual,
       expected IS NOT DISTINCT FROM actual, note
FROM chk;

DROP TABLE chk;
DROP TABLE src_delivered;
