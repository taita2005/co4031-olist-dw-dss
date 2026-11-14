# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a university group assignment (CO4031 – Data Warehouse & Decision Support Systems, HCMUT, semester 261). The code is complete and verified; the remaining work is the report, slides and submission. **Start with `docs/handoff.md`**, which lists what is done, what remains in order, and the decisions already made.

Other docs, all in Vietnamese: `docs/proposal.md` (the approved design and how it changed), `docs/report.md` (the full raw report with every figure as a table), `docs/metabase.md` (the optional Docker + Metabase path), and `README.md` (how to run, code map, review checklist).

Repo: https://github.com/taita2005/co4031-olist-dw-dss. `lectures/` (lecture slides) and `data/*.csv` exist locally but are git-ignored.

In short:
- **Stack:** Python + PostgreSQL + Streamlit, with scikit-learn for the DSS model, all in a project-local micromamba env. An optional Docker Compose path (added later, `docs/metabase.md`) runs the same pipeline plus three Metabase dashboards; the micromamba path stays the primary one, and report metrics are not derived from Metabase.
- **Architecture:** a three-tier DW. CSVs are loaded into a `staging` schema, then into a `dw` schema that has a fact constellation (`fact_sales` at order-item grain, `fact_delivery` at delivered-order grain) sharing `dim_date`, `dim_customer`, `dim_seller` and `dim_product`.
- **Frontend:** a Streamlit OLAP dashboard.
- **DSS:** a decision tree (entropy) that predicts bad reviews (score ≤ 2), plus what-if, sensitivity and goal-seeking analysis on late-delivery rate, and a budget optimiser. Decision question: with a limited budget, which states to prioritise to avoid the most bad reviews, and does that priority hold when cost assumptions change (`robustness()` is the main answer; see `docs/plan.md` §1).
- **Terminology:** follow the lecture slides (Inmon characteristics, three-tier, ROLAP, the 5 OLAP operations, the Simon decision phases, DSS subsystems), because the team must present it to the lecturer.

## Commands

Everything runs from a project-local micromamba env. Never install into the system Python.

```bash
bash scripts/setup_env.sh        # one-time: micromamba + env (.env-btl/) from environment.yml
source scripts/env.sh            # every new shell: PATH + PG* vars (port 5433, user btl, db olist_dw)
bash scripts/db_start.sh         # initdb into .pgdata/ on first run, then start PostgreSQL
python src/etl/run_etl.py        # validate CSVs, full refresh data/*.csv -> staging -> dw (+ meta.etl_log, meta.check_result); exit 1 if a check fails
python src/dss/train_model.py    # writes models/decision_tree.joblib, rules.txt, metrics.json, options.csv, experiments.json (~25 s)
streamlit run src/app/Home.py    # dashboard
python -m pytest tests -q        # unit + DB tests (DB tests skip if the DB is down)
python -m pytest tests/test_optimizer.py -q -k robustness   # single file / single test
bash scripts/db_stop.sh
```

Optional Docker Compose path (details and backup/restore in `docs/metabase.md`):

```bash
docker compose build
docker compose run --rm --no-deps bootstrap      # one-time: writes .env (0600) with random passwords, creates .runtime/
docker compose up -d                             # db-init -> etl-init -> train-init, metabase-init, then app
docker compose run --rm tools python -m pytest tests -q           # tests inside Compose (also gets METABASE_RO_PASSWORD)
docker compose run --rm tools python scripts/metabase_verify.py   # reconcile 18 Metabase questions against the DW
docker compose run --rm tools python scripts/metabase_provision.py --upgrade   # deliberately overwrite managed cards (backs up first)
docker compose down                              # keeps volumes; never `down -v` unless you mean to wipe DW, Metabase and models
```

Streamlit is on 127.0.0.1:8501 and Metabase on 127.0.0.1:3000; PostgreSQL is not published to the host. Never commit `.env` or the output of `docker compose config`.

To check pages headlessly, use `streamlit.testing.v1.AppTest` with `src/app` on `sys.path`.

If the project folder is moved, the micromamba env breaks (PostgreSQL has its install path compiled in): `rm -rf .env-btl && bash scripts/setup_env.sh`. `.pgdata/` is unaffected.

## Code architecture

- **Source contracts:** `src/etl/contracts.py` validates every CSV before COPY (header must match exactly, else the run stops; value rules become `source` checks in `meta.check_result`). Update the contract if a source file changes.
- **SQL files run in order from `run_etl.py`.** `01` and `02` drop and recreate the `staging` and `dw` schemas. `meta.etl_log` lives outside `dw` so it survives refreshes. All cleansing and business rules are in `03_transform_load.sql`. `04` builds the materialized views. `05_checks.sql` writes data quality checks to `meta.check_result`; its expected values are recomputed from staging, never by reusing the transform logic. Add a check there (and a breakage case in `tests/test_etl_checks.py`) whenever you add a business rule. `06_bi_views.sql` runs last, inside the same transaction as the load (before commit), and rebuilds the `bi` schema.
- **BI quality gate (`bi` schema):** `bi.dataset_status.ready` is true only if the latest run has every check, by exact name, in its hard-coded list (27 SQL + 16 source checks), plus a run marker, and none failed; otherwise `bi.sales_items` / `bi.delivery_orders` return no rows. **Renaming or adding a check in `05_checks.sql` or `contracts.py` means updating that list in `06_bi_views.sql`**, or Metabase goes empty. Metabase reads only these views as the `metabase_ro` role (created by `scripts/docker_bootstrap_db.py`, granted in `06`). The two facts are never joined directly.
- **Metabase (`src/bi/metabase.py`, `scripts/metabase_provision.py`):** card SQL is generated from `dashboard_specs()` (3 dashboards: Executive E1–E5, Sales OLAP S1–S5, Delivery Quality D1–D5); every query starts from `bi.dataset_status`. Provisioning is idempotent: it keeps manual edits unless you pass `--upgrade`, and stores object IDs in `.runtime/metabase/catalog.json` (it stops rather than create duplicates if IDs go stale). Verified results are in `docs/metabase_acceptance.md` and `docs/evidence/metabase/`.
- **Compose init jobs (`scripts/docker_pipeline.py`):** ETL runs only when both facts are missing. It is skipped when both exist and the latest quality gate passed, and stops (fail-closed) on a partial DW or a failed gate. Training runs only when the model is missing or carries an older `etl_run_id`.
- **Shared code:** `src/db.py` is used by the ETL, the DSS and the app. Entry scripts add `src/` to `sys.path`; the Streamlit pages do this through `src/app/common.py`, which they must import first.
- **DSS risk model:** whatif.py does not use `predict_proba` (it is skewed by `class_weight="balanced"`). Probabilities come from `bundle["leaf_rate"]`, the training bad-review rate of each tree leaf. Scenarios pick which late orders to fix using the fixed `rand` column from `load_dataset()`, so results are deterministic and monotone.
- **Budget optimiser (`src/dss/optimizer.py`):** `train_model.py` pre-computes `models/options.csv` (benefit per state x level from `evaluate_scenario`); cost (BRL) = `freight_fixed` (real freight of the late orders fixed, from the DW) x `surcharge` x `tier[level]`; only those two parameters (`config/cost_assumptions.csv`) are assumptions. `surcharge` only rescales the budget (tested); `tier` shapes the plan (`tier_sensitivity()`). `solve()` is an exact MILP (scipy `milp`/HiGHS); HiGHS prints debug lines to fd 1, silenced by `_quiet_native_output()`. `greedy()` is an incremental (upgrade) greedy baseline; keep it a fair baseline. `robustness()` re-solves under 2 cost models (`COST_MODELS`: real freight / uniform) x 3 tiers x `ROBUST_BUDGETS` and ranks states by the first budget where they are chosen under >= 2/3 of the assumption sets.
- **Model selection:** `TREE_PARAMS` (4 / 200) vs `PARAM_GRID` is evaluated by `tree_experiments()` (5-fold CV on the training set only) into `models/experiments.json`; `leaf_check()` stores train-vs-test leaf rates in `metrics.json`.
- **OLAP page:** it builds SQL only from the whitelisted `HIERARCHIES`, `FACTS` and `measures` dicts; user values are passed as bind parameters. Keep that pattern when adding dimensions or measures.
- **Lineage:** `metrics.json` stores `etl_run_id`; the Data Quality page warns when the model was trained on an older ETL run.
- **Language:** the UI and README are in Vietnamese; code comments are in English.

## What the assignment requires

The deliverable is a complete system built around a data warehouse:
1. Business requirements analysis and a concrete decision problem (e-commerce domain, based on the dataset).
2. A multidimensional DW design (star or snowflake schema) plus an ETL process.
3. A working backend (database, ETL, OLAP) and frontend (dashboard / query UI).
4. A DSS component built on top of the DW (the course covers modeling and analysis in lectures ch. 5–8).
5. Evaluation, limitations, and future work.

Submission is one ZIP containing: report (PDF), source code in `src/` (SQL scripts, Python/R, frontend, ETL; GitHub preferred), sample data in `data/`, slides (PDF), and a video link on the report cover if presenting by video. **Deadline: 23:59, 15/11/2026.** Lay out new code to match that `src/` / `data/` structure.

## Source data: Brazilian E-Commerce (Olist), `data/`

There are 9 CSVs covering about 99k orders, with purchase timestamps from 2016-09-04 to 2018-10-17. How they relate:

- `orders` (order_id, customer_id, status, 5 lifecycle timestamps) is the hub.
- `order_items` is keyed by (order_id, order_item_id) and links to `products` and `sellers`. Its grain (one row per item, with `price` and `freight_value`) is the natural sales fact grain.
- `order_payments` is keyed by (order_id, payment_sequential). An order can have several payments (voucher plus card, for example), so summing payments by joining them directly to items double-counts.
- `order_reviews` links to orders by order_id.
- `customers` and `sellers` link to `geolocation` via zip_code_prefix.
- `product_category_name_translation` maps Portuguese category names to English.

Data quirks the ETL must handle:
- **`customer_id` is per-order.** Use `customer_unique_id` to identify a real customer (99,441 customer_ids map to 96,096 unique customers). Repeat-purchase or RFM analysis must use `customer_unique_id`.
- **`geolocation` is not unique by zip prefix.** It has about 1M rows for 19,015 prefixes, so aggregate it (for example, mean lat/lng per prefix) before joining, or the joins will multiply rows. Some customer and seller zips are missing from it.
- **Reviews:** `review_id` and `order_id` are both non-unique in reviews (99,224 rows, 98,410 review_ids, 98,673 order_ids). Comment fields are mostly empty, are in Portuguese, and contain embedded newlines, so use a real CSV parser.
- **Products:** 610 products have no category. Two categories (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) are missing from the translation table. Column names are misspelled in the source (`product_name_lenght`, `product_description_lenght`).
- `product_category_name_translation.csv` starts with a UTF-8 BOM, so read it with `utf-8-sig`.
- **Order status:** about 97% of orders are `delivered`. The other statuses are shipped, canceled, unavailable, invoiced, processing, created, and approved. 2,965 orders have no `order_delivered_customer_date`, so delivery-time measures (actual vs. `order_estimated_delivery_date`) apply only to delivered orders.
- **Payment types:** credit_card, boleto, voucher, debit_card, and `not_defined` (3 rows).
- **Zip prefixes** are 5-digit strings with leading zeros (for example "01037"). Keep them as text, not integers.
- City names are lowercase and inconsistently accented. State is a 2-letter UF code.
