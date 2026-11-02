-- =====================================================================
-- 03_transform_load.sql — Transform (cleansing, mapping, business rules)
-- and Load from staging into the dw schema.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Mapping helper: Brazilian state (UF) -> macro region (attribute construction)
-- ---------------------------------------------------------------------
CREATE TEMP TABLE ref_state_region (state CHAR(2) PRIMARY KEY, region TEXT NOT NULL);
INSERT INTO ref_state_region VALUES
    ('AC','North'),('AP','North'),('AM','North'),('PA','North'),('RO','North'),('RR','North'),('TO','North'),
    ('AL','Northeast'),('BA','Northeast'),('CE','Northeast'),('MA','Northeast'),('PB','Northeast'),
    ('PE','Northeast'),('PI','Northeast'),('RN','Northeast'),('SE','Northeast'),
    ('DF','Central-West'),('GO','Central-West'),('MT','Central-West'),('MS','Central-West'),
    ('ES','Southeast'),('MG','Southeast'),('RJ','Southeast'),('SP','Southeast'),
    ('PR','South'),('RS','South'),('SC','South');

-- Cleansing: two categories are missing from the source translation table
CREATE TEMP TABLE ref_category AS
SELECT product_category_name AS category_pt, product_category_name_english AS category_en
FROM staging.category_translation
UNION ALL
SELECT * FROM (VALUES
    ('pc_gamer', 'pc_gamer'),
    ('portateis_cozinha_e_preparadores_de_alimentos', 'portable_kitchen_food_processors')
) AS missing(category_pt, category_en)
WHERE NOT EXISTS (SELECT 1 FROM staging.category_translation t
                  WHERE t.product_category_name = missing.category_pt);

-- ---------------------------------------------------------------------
-- dim_date: one row per calendar day covering the whole dataset
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_date
SELECT to_char(d, 'YYYYMMDD')::INTEGER,
       d::DATE,
       EXTRACT(DAY FROM d),
       EXTRACT(MONTH FROM d),
       to_char(d, 'Mon'),
       EXTRACT(QUARTER FROM d),
       EXTRACT(YEAR FROM d),
       to_char(d, 'YYYY-MM'),
       EXTRACT(ISODOW FROM d),
       EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series('2016-01-01'::DATE, '2018-12-31'::DATE, INTERVAL '1 day') AS d;

-- ---------------------------------------------------------------------
-- dim_customer
-- Business rule: customer_id is issued per order; the real customer is
-- customer_unique_id. Keep the location of the customer's latest order.
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_customer (customer_unique_id, zip_code_prefix, city, state, region)
SELECT DISTINCT ON (c.customer_unique_id)
       c.customer_unique_id,
       c.customer_zip_code_prefix,      -- kept as TEXT (leading zeros)
       c.customer_city,
       c.customer_state,
       COALESCE(r.region, 'Unknown')
FROM staging.customers c
JOIN staging.orders o ON o.customer_id = c.customer_id
LEFT JOIN ref_state_region r ON r.state = c.customer_state
ORDER BY c.customer_unique_id, o.order_purchase_timestamp::TIMESTAMP DESC;

-- ---------------------------------------------------------------------
-- dim_seller
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_seller (seller_id, zip_code_prefix, city, state, region)
SELECT s.seller_id, s.seller_zip_code_prefix, s.seller_city, s.seller_state,
       COALESCE(r.region, 'Unknown')
FROM staging.sellers s
LEFT JOIN ref_state_region r ON r.state = s.seller_state;

-- ---------------------------------------------------------------------
-- dim_product
-- Cleansing: missing category -> 'unknown'; Mapping: PT -> EN name;
-- Attribute construction: volume = length * height * width.
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_product (product_id, category_pt, category_en, photos_qty, weight_g, volume_cm3)
SELECT p.product_id,
       COALESCE(NULLIF(p.product_category_name, ''), 'unknown'),
       COALESCE(rc.category_en, 'unknown'),
       NULLIF(p.product_photos_qty, '')::SMALLINT,
       NULLIF(p.product_weight_g, '')::INTEGER,
       NULLIF(p.product_length_cm, '')::INTEGER
         * NULLIF(p.product_height_cm, '')::INTEGER
         * NULLIF(p.product_width_cm, '')::INTEGER
FROM staging.products p
LEFT JOIN ref_category rc ON rc.category_pt = p.product_category_name;

-- ---------------------------------------------------------------------
-- fact_sales (grain: order item) — all order statuses are kept;
-- order_status lets analysts filter e.g. canceled orders out.
-- ---------------------------------------------------------------------
INSERT INTO dw.fact_sales
SELECT to_char(o.order_purchase_timestamp::TIMESTAMP, 'YYYYMMDD')::INTEGER,
       dc.customer_key,
       ds.seller_key,
       dp.product_key,
       i.order_id,
       i.order_item_id::SMALLINT,
       o.order_status,
       i.price::NUMERIC,
       i.freight_value::NUMERIC,
       i.price::NUMERIC + i.freight_value::NUMERIC
FROM staging.order_items i
JOIN staging.orders     o  ON o.order_id = i.order_id
JOIN staging.customers  c  ON c.customer_id = o.customer_id
JOIN dw.dim_customer    dc ON dc.customer_unique_id = c.customer_unique_id
JOIN dw.dim_seller      ds ON ds.seller_id = i.seller_id
JOIN dw.dim_product     dp ON dp.product_id = i.product_id;

-- ---------------------------------------------------------------------
-- fact_delivery (grain: delivered order)
-- Business rules: only 'delivered' orders that have a delivery date;
-- is_late = delivered after the estimated date; bad review = score <= 2.
-- Cleansing: an order can have several reviews -> keep the latest answer.
-- ---------------------------------------------------------------------
INSERT INTO dw.fact_delivery
WITH item_agg AS (
    SELECT order_id,
           COUNT(*)                     AS n_items,
           COUNT(DISTINCT seller_id)    AS n_sellers,
           SUM(price::NUMERIC)          AS order_value,
           SUM(freight_value::NUMERIC)  AS freight_total
    FROM staging.order_items
    GROUP BY order_id
),
main_item AS (
    SELECT DISTINCT ON (order_id) order_id, seller_id, product_id
    FROM staging.order_items
    ORDER BY order_id, price::NUMERIC DESC, order_item_id::INTEGER
),
latest_review AS (
    SELECT DISTINCT ON (order_id) order_id, review_score::SMALLINT AS review_score
    FROM staging.order_reviews
    ORDER BY order_id, review_answer_timestamp::TIMESTAMP DESC
),
delivered AS (
    SELECT order_id, customer_id,
           order_purchase_timestamp::TIMESTAMP::DATE      AS purchase_date,
           order_delivered_customer_date::TIMESTAMP::DATE AS delivered_date,
           order_estimated_delivery_date::TIMESTAMP::DATE AS estimated_date
    FROM staging.orders
    WHERE order_status = 'delivered'
      AND NULLIF(order_delivered_customer_date, '') IS NOT NULL
)
SELECT d.order_id,
       to_char(d.purchase_date,  'YYYYMMDD')::INTEGER,
       to_char(d.delivered_date, 'YYYYMMDD')::INTEGER,
       dc.customer_key,
       ds.seller_key,
       dp.product_key,
       ia.n_items,
       ia.n_sellers,
       ia.order_value,
       ia.freight_total,
       d.delivered_date - d.purchase_date,
       d.estimated_date - d.purchase_date,
       d.delivered_date - d.estimated_date,
       CASE WHEN d.delivered_date > d.estimated_date THEN 1 ELSE 0 END,
       lr.review_score,
       CASE WHEN lr.review_score IS NULL THEN NULL
            WHEN lr.review_score <= 2 THEN 1 ELSE 0 END
FROM delivered d
JOIN item_agg          ia ON ia.order_id = d.order_id
JOIN main_item         mi ON mi.order_id = d.order_id
JOIN staging.customers c  ON c.customer_id = d.customer_id
JOIN dw.dim_customer   dc ON dc.customer_unique_id = c.customer_unique_id
JOIN dw.dim_seller     ds ON ds.seller_id = mi.seller_id
JOIN dw.dim_product    dp ON dp.product_id = mi.product_id
LEFT JOIN latest_review lr ON lr.order_id = d.order_id;

ANALYZE dw.dim_date, dw.dim_customer, dw.dim_seller, dw.dim_product,
        dw.fact_sales, dw.fact_delivery;
