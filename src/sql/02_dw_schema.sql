-- =====================================================================
-- 02_dw_schema.sql — Dimensional Data Store (middle tier)
-- Fact constellation: fact_sales and fact_delivery share the dimensions
-- (mirrors the "sales and shipping" example in lecture Ch.3).
-- Full refresh: the dw schema is rebuilt on every ETL run.
-- =====================================================================
DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;

-- Metadata ("history of extracts") lives in its own schema so it survives
-- the full refresh of dw.
CREATE SCHEMA IF NOT EXISTS meta;
CREATE TABLE IF NOT EXISTS meta.etl_log (
    log_id       SERIAL PRIMARY KEY,
    run_id       TIMESTAMP NOT NULL,      -- start time of the ETL run
    step         TEXT      NOT NULL,      -- extract | load
    table_name   TEXT      NOT NULL,
    source_rows  INTEGER,
    loaded_rows  INTEGER,
    note         TEXT,
    logged_at    TIMESTAMP NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Dimensions (surrogate integer keys)
-- ---------------------------------------------------------------------

-- Hierarchy: year > quarter > month > day
CREATE TABLE dw.dim_date (
    date_key     INTEGER PRIMARY KEY,     -- yyyymmdd
    full_date    DATE    NOT NULL,
    day          SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    month_name   TEXT    NOT NULL,
    quarter      SMALLINT NOT NULL,
    year         SMALLINT NOT NULL,
    year_month   TEXT    NOT NULL,        -- 'YYYY-MM', handy for charts
    weekday      SMALLINT NOT NULL,       -- 1 = Monday … 7 = Sunday
    is_weekend   BOOLEAN NOT NULL
);

-- One row per real customer (customer_unique_id). Hierarchy: region > state > city
CREATE TABLE dw.dim_customer (
    customer_key        SERIAL PRIMARY KEY,
    customer_unique_id  TEXT NOT NULL UNIQUE,
    zip_code_prefix     TEXT,
    city                TEXT,
    state               CHAR(2),
    region              TEXT
);

-- Hierarchy: region > state > city
CREATE TABLE dw.dim_seller (
    seller_key       SERIAL PRIMARY KEY,
    seller_id        TEXT NOT NULL UNIQUE,
    zip_code_prefix  TEXT,
    city             TEXT,
    state            CHAR(2),
    region           TEXT
);

-- Hierarchy: category > product
CREATE TABLE dw.dim_product (
    product_key   SERIAL PRIMARY KEY,
    product_id    TEXT NOT NULL UNIQUE,
    category_pt   TEXT NOT NULL,
    category_en   TEXT NOT NULL,
    photos_qty    SMALLINT,
    weight_g      INTEGER,
    volume_cm3    INTEGER
);

-- ---------------------------------------------------------------------
-- Fact 1: sales — grain = one item in one order
-- Partitioned by purchase year (partitioning by time, lecture Ch.1).
-- ---------------------------------------------------------------------
CREATE TABLE dw.fact_sales (
    purchase_date_key  INTEGER NOT NULL REFERENCES dw.dim_date (date_key),
    customer_key       INTEGER NOT NULL REFERENCES dw.dim_customer (customer_key),
    seller_key         INTEGER NOT NULL REFERENCES dw.dim_seller (seller_key),
    product_key        INTEGER NOT NULL REFERENCES dw.dim_product (product_key),
    order_id           TEXT    NOT NULL,  -- degenerate dimension
    order_item_id      SMALLINT NOT NULL, -- degenerate dimension
    order_status       TEXT    NOT NULL,  -- degenerate dimension
    price              NUMERIC(10, 2) NOT NULL,  -- additive
    freight_value      NUMERIC(10, 2) NOT NULL,  -- additive
    total_value        NUMERIC(10, 2) NOT NULL,  -- additive (price + freight)
    PRIMARY KEY (order_id, order_item_id, purchase_date_key)
) PARTITION BY RANGE (purchase_date_key);

CREATE TABLE dw.fact_sales_2016 PARTITION OF dw.fact_sales FOR VALUES FROM (20160101) TO (20170101);
CREATE TABLE dw.fact_sales_2017 PARTITION OF dw.fact_sales FOR VALUES FROM (20170101) TO (20180101);
CREATE TABLE dw.fact_sales_2018 PARTITION OF dw.fact_sales FOR VALUES FROM (20180101) TO (20190101);

-- ---------------------------------------------------------------------
-- Fact 2: delivery — grain = one delivered order
-- Review and delivery dates belong to the whole order, not to an item,
-- so they cannot live in fact_sales without double counting.
-- seller_key / product_key = the order's main item (highest price).
-- ---------------------------------------------------------------------
CREATE TABLE dw.fact_delivery (
    order_id            TEXT    PRIMARY KEY,  -- degenerate dimension
    purchase_date_key   INTEGER NOT NULL REFERENCES dw.dim_date (date_key),
    delivered_date_key  INTEGER NOT NULL REFERENCES dw.dim_date (date_key),
    customer_key        INTEGER NOT NULL REFERENCES dw.dim_customer (customer_key),
    seller_key          INTEGER NOT NULL REFERENCES dw.dim_seller (seller_key),
    product_key         INTEGER NOT NULL REFERENCES dw.dim_product (product_key),
    n_items             SMALLINT NOT NULL,
    n_sellers           SMALLINT NOT NULL,
    order_value         NUMERIC(10, 2) NOT NULL,  -- sum of item prices
    freight_total       NUMERIC(10, 2) NOT NULL,
    delivery_days       SMALLINT NOT NULL,        -- purchase -> delivered
    estimated_days      SMALLINT NOT NULL,        -- purchase -> estimated date
    delay_days          SMALLINT NOT NULL,        -- delivered - estimated (>0 = late)
    is_late             SMALLINT NOT NULL,        -- 0/1
    review_score        SMALLINT,                 -- NULL if the order has no review
    is_bad_review       SMALLINT                  -- 1 if score <= 2
);

-- Indexes on foreign keys used for slicing/dicing
CREATE INDEX ON dw.fact_sales (customer_key);
CREATE INDEX ON dw.fact_sales (seller_key);
CREATE INDEX ON dw.fact_sales (product_key);
CREATE INDEX ON dw.fact_delivery (purchase_date_key);
CREATE INDEX ON dw.fact_delivery (customer_key);
CREATE INDEX ON dw.fact_delivery (seller_key);
CREATE INDEX ON dw.fact_delivery (product_key);
