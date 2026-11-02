-- =====================================================================
-- 04_olap_views.sql — ROLAP pre-aggregation (materialized views)
-- Detail stays in the relational fact tables; frequently used summaries
-- are pre-computed here so the dashboard does not rescan the facts.
-- =====================================================================

-- Monthly KPIs combining both facts (used by the Home page)
CREATE MATERIALIZED VIEW dw.mv_monthly_kpi AS
WITH sales AS (
    SELECT d.year_month,
           SUM(f.price)               AS revenue,
           SUM(f.freight_value)       AS freight,
           COUNT(*)                   AS n_items,
           COUNT(DISTINCT f.order_id) AS n_orders
    FROM dw.fact_sales f
    JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY d.year_month
),
delivery AS (
    SELECT d.year_month,
           COUNT(*)                AS n_delivered,
           AVG(f.is_late)          AS late_rate,
           AVG(f.delivery_days)    AS avg_delivery_days,
           AVG(f.review_score)     AS avg_review,
           AVG(f.is_bad_review)    AS bad_review_rate
    FROM dw.fact_delivery f
    JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.year_month
)
SELECT s.*, dl.n_delivered, dl.late_rate, dl.avg_delivery_days, dl.avg_review, dl.bad_review_rate
FROM sales s
LEFT JOIN delivery dl USING (year_month)
ORDER BY s.year_month;

-- Sales cube: GROUP BY CUBE computes every combination of
-- (year, customer region, category), including subtotals (NULL = "All").
CREATE MATERIALIZED VIEW dw.mv_sales_cube AS
SELECT d.year,
       c.region      AS customer_region,
       p.category_en AS category,
       SUM(f.price)  AS revenue,
       COUNT(*)      AS n_items
FROM dw.fact_sales f
JOIN dw.dim_date     d ON d.date_key = f.purchase_date_key
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_product  p ON p.product_key = f.product_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY CUBE (d.year, c.region, p.category_en);

-- Delivery performance per customer state (used by the Delivery page)
CREATE MATERIALIZED VIEW dw.mv_delivery_by_state AS
SELECT c.state,
       c.region,
       COUNT(*)              AS n_orders,
       AVG(f.is_late)        AS late_rate,
       AVG(f.delivery_days)  AS avg_delivery_days,
       AVG(f.review_score)   AS avg_review,
       AVG(f.is_bad_review)  AS bad_review_rate,
       SUM(f.order_value)    AS revenue
FROM dw.fact_delivery f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.state, c.region;
