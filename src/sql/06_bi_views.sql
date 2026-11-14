-- BI status requires the complete current check contract (27 SQL + 16 source checks).
CREATE SCHEMA IF NOT EXISTS bi AUTHORIZATION CURRENT_USER;

CREATE OR REPLACE VIEW bi.dataset_status AS
WITH required(check_name) AS (VALUES
 ('fact_sales: duplicate (order_id, order_item_id)'),
 ('fact_delivery: duplicate order_id'),
 ('dim_customer: duplicate customer_unique_id'),
 ('rows: staging.order_items = fact_sales'),
 ('SUM(price): staging.order_items = fact_sales'),
 ('SUM(freight_value): staging.order_items = fact_sales'),
 ('rows: delivered orders with a delivery date = fact_delivery'),
 ('SUM(order_value): items of delivered orders = fact_delivery'),
 ('late orders: staging = SUM(fact_delivery.is_late)'),
 ('delivered orders with a review = fact_delivery rows with review_score'),
 ('rows: distinct customer_unique_id = dim_customer'),
 ('rows: staging.sellers = dim_seller'),
 ('rows: staging.products = dim_product'),
 ('review_score outside 1..5'),
 ('is_bad_review inconsistent with review_score <= 2'),
 ('is_late inconsistent with delay_days > 0'),
 ('delay_days <> delivery_days - estimated_days'),
 ('negative delivery_days or estimated_days'),
 ('price <= 0 or freight_value < 0'),
 ('total_value <> price + freight_value'),
 ('source purchase/delivery dates outside dim_date'),
 ('products with a source category but no English name'),
 ('customers/sellers with a state but no region'),
 ('mv_sales_cube grand total = fact_sales (excl. canceled/unavailable)'),
 ('SUM(mv_monthly_kpi.revenue) = fact_sales (excl. canceled/unavailable)'),
 ('SUM(mv_delivery_by_state.n_orders) = fact_delivery'),
 ('rates in materialized views outside [0, 1]')
), filenames(filename, table_name) AS (VALUES
 ('olist_orders_dataset.csv','orders'), ('olist_order_items_dataset.csv','order_items'),
 ('olist_order_payments_dataset.csv','order_payments'), ('olist_order_reviews_dataset.csv','order_reviews'),
 ('olist_customers_dataset.csv','customers'), ('olist_sellers_dataset.csv','sellers'),
 ('olist_products_dataset.csv','products'), ('product_category_name_translation.csv','category_translation')
), all_required(check_name) AS (
 SELECT check_name FROM required
 UNION ALL SELECT filename || ': vi phạm hợp đồng' FROM filenames
 UNION ALL SELECT 'rows: ' || filename || ' = staging.' || table_name FROM filenames
), latest AS (
 SELECT max(run_id) AS run_id FROM meta.etl_log WHERE step='load'
), scored AS (
 SELECT l.run_id,
        COUNT(DISTINCT a.check_name) FILTER (WHERE c.check_name IS NOT NULL) AS check_count,
        COUNT(DISTINCT a.check_name) FILTER (WHERE c.check_name IS NULL) +
        (SELECT COUNT(*) FROM meta.check_result x WHERE x.run_id=l.run_id AND NOT x.passed) AS failed_count
 FROM latest l CROSS JOIN all_required a
 LEFT JOIN meta.check_result c ON c.run_id=l.run_id AND c.check_name=a.check_name
 GROUP BY l.run_id
)
SELECT l.run_id AS etl_run_id,
       COALESCE(s.check_count, 0)::INTEGER AS check_count,
       CASE WHEN l.run_id IS NULL OR NOT EXISTS (
           SELECT 1 FROM meta.etl_log e WHERE e.run_id=l.run_id AND e.step='run'
       ) THEN COALESCE(s.failed_count,0)+43 ELSE COALESCE(s.failed_count,43) END::INTEGER AS failed_count,
       (l.run_id IS NOT NULL AND EXISTS (
           SELECT 1 FROM meta.etl_log e WHERE e.run_id=l.run_id AND e.step='run'
       ) AND COALESCE(s.check_count,0)=43 AND COALESCE(s.failed_count,43)=0) AS ready
FROM latest l LEFT JOIN scored s ON s.run_id=l.run_id;

CREATE OR REPLACE VIEW bi.sales_items AS
SELECT f.order_id, f.order_item_id, d.full_date AS purchase_date,
       c.state::TEXT AS customer_state, c.region AS customer_region,
       p.category_en AS category, f.price, f.freight_value
FROM dw.fact_sales f
JOIN dw.dim_date d ON d.date_key=f.purchase_date_key
JOIN dw.dim_customer c ON c.customer_key=f.customer_key
JOIN dw.dim_product p ON p.product_key=f.product_key
CROSS JOIN bi.dataset_status s
WHERE s.ready AND f.order_status NOT IN ('canceled','unavailable');

CREATE OR REPLACE VIEW bi.delivery_orders AS
SELECT f.order_id, d.full_date AS purchase_date, c.state::TEXT AS customer_state,
       c.region AS customer_region, f.delivery_days::INTEGER AS delivery_days,
       f.delay_days::INTEGER AS delay_days, (f.is_late=1) AS is_late,
       f.review_score::INTEGER AS review_score,
       (f.is_bad_review=1)::BOOLEAN AS is_bad_review,
       CASE WHEN f.delay_days <= 0 THEN 'Đúng hạn hoặc sớm'
            WHEN f.delay_days <= 3 THEN '1–3 ngày'
            WHEN f.delay_days <= 7 THEN '4–7 ngày'
            WHEN f.delay_days <= 14 THEN '8–14 ngày'
            ELSE '15+ ngày' END AS delay_bucket,
       CASE WHEN f.delay_days <= 0 THEN 0 WHEN f.delay_days <= 3 THEN 1
            WHEN f.delay_days <= 7 THEN 2 WHEN f.delay_days <= 14 THEN 3 ELSE 4 END AS bucket_order
FROM dw.fact_delivery f
JOIN dw.dim_date d ON d.date_key=f.purchase_date_key
JOIN dw.dim_customer c ON c.customer_key=f.customer_key
CROSS JOIN bi.dataset_status s
WHERE s.ready;

DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='metabase_ro') THEN
   EXECUTE format('GRANT CONNECT ON DATABASE %I TO metabase_ro', current_database());
   GRANT USAGE ON SCHEMA bi TO metabase_ro;
   GRANT SELECT ON bi.dataset_status, bi.sales_items, bi.delivery_orders TO metabase_ro;
 END IF;
END $$;
