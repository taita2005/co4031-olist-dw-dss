"""Execute all saved questions under representative filters and reconcile them to DW facts."""
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.metabase_provision import API, CATALOG, _auth, _runtime_owner  # noqa: E402
from src.bi.metabase import dashboard_specs  # noqa: E402

CASES = [
    {"name": "default", "start_date": "2017-01-01", "end_date": "2018-09-01", "grain": "month"},
    {"name": "filtered", "start_date": "2018-01-01", "end_date": "2019-01-01", "grain": "month",
     "customer_state": ["SP", "RJ"], "customer_region": ["Southeast"],
     "category": ["health_beauty", "watches_gifts"]},
    {"name": "quarter", "start_date": "2017-01-01", "end_date": "2018-09-01", "grain": "quarter"},
    {"name": "year", "start_date": "2017-01-01", "end_date": "2018-09-01", "grain": "year"},
    {"name": "month", "start_date": "2018-01-01", "end_date": "2018-02-01", "grain": "month"},
    {"name": "empty", "start_date": "2025-01-01", "end_date": "2025-02-01", "grain": "month"},
]


def _source(fact, case, sales):
    conditions = ["d.full_date >= %s", "d.full_date < %s"]
    values = [case["start_date"], case["end_date"]]
    if sales:
        conditions.append("f.order_status NOT IN ('canceled','unavailable')")
    for name, column in (("customer_state", "c.state"), ("customer_region", "c.region")):
        if name in case:
            conditions.append(column + " = ANY(%s)")
            values.append(case[name])
    query = (f" FROM dw.{fact} f JOIN dw.dim_date d ON d.date_key=f.purchase_date_key "
             "JOIN dw.dim_customer c ON c.customer_key=f.customer_key")
    if sales:
        query += " JOIN dw.dim_product p ON p.product_key=f.product_key"
        if "category" in case:
            conditions.append("p.category_en = ANY(%s)")
            values.append(case["category"])
    return query + " WHERE " + " AND ".join(conditions), values


def _canonical(field, value):
    value = value.isoformat() if hasattr(value, "isoformat") else value
    if field == "period" and isinstance(value, str):
        return value[:10]
    return value


def _assert_rows(actual, expected, key_fields, value_fields):
    def index(rows):
        result = {tuple(_canonical(field, row[field]) for field in key_fields): row for row in rows}
        assert len(result) == len(rows), "duplicate keys in question/source results"
        return result

    got, want = index(actual), index(expected)
    assert got.keys() == want.keys(), (got.keys(), want.keys())
    for key in want:
        for field in value_fields:
            left, right = got[key][field], want[key][field]
            if left is None or right is None:
                assert left is right, (key, field, left, right)
            else:
                tolerance = 1e-9 if field.endswith(("rate", "share")) else 1e-6
                assert abs(float(left) - float(right)) < tolerance, (key, field, left, right)


def verify(api=None, conn=None, catalog_path=CATALOG, output=None):
    api = api or API(timeout=120)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    _auth(api, os.environ["METABASE_ADMIN_PASSWORD"], os.environ["METABASE_ADMIN_EMAIL"])
    own_connection = conn is None
    if own_connection:
        conn = psycopg2.connect(host=os.environ["PGHOST"], port=os.environ["PGPORT"],
            dbname=os.environ["PGDATABASE"], user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"])
    output = output or ROOT / ".runtime/metabase/acceptance"
    output.mkdir(parents=True, exist_ok=True)
    owner = _runtime_owner(output)
    os.chown(output, owner.st_uid, owner.st_gid)
    properties = api.call("GET", "session/properties")
    version = properties.get("version", {})
    evidence = {"verified_at_utc": datetime.now(timezone.utc).isoformat(),
                "metabase_version": version.get("tag") if isinstance(version, dict) else version,
                "cases": []}
    try:
        for case in CASES:
            rows_by_key = {}
            questions = []
            for board, definition in dashboard_specs().items():
                specs = [*definition["cards"], {**definition["status"], "key": "STATUS_" + board}]
                for spec in specs:
                    key = board + "/" + spec["key"]
                    params = []
                    for name in spec["filters"]:
                        if name not in case:
                            continue
                        dimension = name in ("customer_state", "customer_region", "category")
                        params.append({"id": name, "type": "string/=" if dimension else
                            ("date/single" if name.endswith("_date") else "category"),
                            "target": ["dimension" if dimension else "variable", ["template-tag", name]],
                            "value": case[name]})
                    result = api.call("POST", f"card/{catalog['cards'][key]}/query",
                                      {"parameters": params, "ignore_cache": True})
                    if result.get("status") != "completed":
                        raise RuntimeError(f"Question {key} failed in case {case['name']}")
                    columns = [column["name"] for column in result["data"]["cols"]]
                    rows = [dict(zip(columns, row)) for row in result["data"]["rows"]]
                    rows_by_key[spec["key"]] = rows
                    if spec["key"].startswith("STATUS_"):
                        assert len(rows) == 1 and rows[0]["ready"] is True
                        assert rows[0]["check_count"] == 43 and rows[0]["failed_count"] == 0
                    questions.append({"key": key, "rows": len(rows)})
                    if case["name"] == "default":
                        csv_path = output / (spec["key"] + ".csv")
                        with csv_path.open("w", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            writer.writerows(result["data"]["rows"])
                        os.chown(csv_path, owner.st_uid, owner.st_gid)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                etail, evalues = _source("fact_sales", case, False)
                etail += " AND f.order_status NOT IN ('canceled','unavailable')"
                cur.execute("SELECT sum(f.price) AS revenue,count(DISTINCT f.order_id) AS orders" + etail, evalues)
                expected = cur.fetchone()
                got = rows_by_key["E1"][0]["revenue_brl"]
                if got is None or expected["revenue"] is None:
                    assert got is None and expected["revenue"] is None
                else:
                    assert abs(float(got) - float(expected["revenue"])) < 1e-6
                assert rows_by_key["E2"][0]["orders"] == expected["orders"]
                period_sql = "date_trunc(%s,d.full_date)::date AS period"
                cur.execute("SELECT " + period_sql + ",sum(f.price) AS revenue_brl" + etail +
                            " GROUP BY 1 ORDER BY 1", [case["grain"], *evalues])
                _assert_rows(rows_by_key["E3"], cur.fetchall(), ["period"], ["revenue_brl"])
                cur.execute("SELECT " + period_sql + ",count(DISTINCT f.order_id) AS orders,"
                            "sum(f.price)/nullif(count(DISTINCT f.order_id),0) AS aov_brl" + etail +
                            " GROUP BY 1 ORDER BY 1", [case["grain"], *evalues])
                _assert_rows(rows_by_key["E4"], cur.fetchall(), ["period"], ["orders", "aov_brl"])
                cur.execute("SELECT c.state AS customer_state,sum(f.price) AS revenue_brl" + etail +
                            " GROUP BY 1 ORDER BY revenue_brl DESC,customer_state", evalues)
                _assert_rows(rows_by_key["E5"], cur.fetchall(), ["customer_state"], ["revenue_brl"])
                if rows_by_key["E5"]:
                    assert abs(float(rows_by_key["E5"][-1]["cumulative_share"]) - 1) < 1e-9

                stail, svalues = _source("fact_sales", case, True)
                cur.execute("SELECT sum(f.price) AS revenue" + stail, svalues)
                sales_total = cur.fetchone()["revenue"]
                assert abs(sum(float(row["revenue_brl"]) for row in rows_by_key["S3"]) - float(sales_total or 0)) < 1e-6
                by_region = {}
                for row in rows_by_key["S3"]:
                    by_region[row["customer_region"]] = by_region.get(row["customer_region"], 0) + float(row["share"] or 0)
                assert all(abs(value - 1) < 1e-9 for value in by_region.values())
                filtered_sales = ("filtered AS (SELECT f.order_id,f.price,d.full_date,p.category_en AS category,"
                                  "c.region AS customer_region,c.state AS customer_state" + stail + ")")
                cur.execute("WITH " + filtered_sales + ", top5 AS (SELECT category FROM filtered GROUP BY category "
                            "ORDER BY sum(price) DESC,category LIMIT 5), grouped AS (SELECT customer_region,"
                            "CASE WHEN category IN (SELECT category FROM top5) THEN category "
                            "ELSE 'Danh mục khác trong bộ lọc' END AS category_group,sum(price) AS revenue_brl "
                            "FROM filtered GROUP BY 1,2) SELECT customer_region,category_group,revenue_brl,"
                            "revenue_brl/nullif(sum(revenue_brl) OVER (PARTITION BY customer_region),0) AS share "
                            "FROM grouped", svalues)
                _assert_rows(rows_by_key["S3"], cur.fetchall(), ["customer_region", "category_group"],
                             ["revenue_brl", "share"])
                cur.execute("SELECT p.category_en AS category,sum(f.price) AS revenue_brl" + stail +
                            " GROUP BY 1 ORDER BY revenue_brl DESC,category LIMIT 10", svalues)
                _assert_rows(rows_by_key["S1"], cur.fetchall(), ["category"], ["revenue_brl"])
                cur.execute("WITH " + filtered_sales + ", top5 AS (SELECT category FROM filtered GROUP BY category "
                            "ORDER BY sum(price) DESC,category LIMIT 5) SELECT date_trunc(%s,full_date)::date AS period,"
                            "category,sum(price) AS revenue_brl FROM filtered JOIN top5 USING(category) "
                            "GROUP BY 1,2 ORDER BY 1,2", [*svalues, case["grain"]])
                _assert_rows(rows_by_key["S2"], cur.fetchall(), ["period", "category"], ["revenue_brl"])
                region_columns = {"north_brl": "North", "northeast_brl": "Northeast",
                                  "central_west_brl": "Central-West", "southeast_brl": "Southeast",
                                  "south_brl": "South", "unknown_brl": "Unknown"}
                pivots = ",".join(f"sum(price) FILTER (WHERE customer_region='{region}') AS {field}"
                                   for field, region in region_columns.items())
                cur.execute("WITH " + filtered_sales + ", top10 AS (SELECT category FROM filtered GROUP BY category "
                            "ORDER BY sum(price) DESC,category LIMIT 10) SELECT category," + pivots +
                            " FROM filtered WHERE category IN (SELECT category FROM top10) GROUP BY category "
                            "ORDER BY sum(price) DESC,category", svalues)
                _assert_rows(rows_by_key["S4"], cur.fetchall(), ["category"], list(region_columns))
                cur.execute("SELECT c.state AS customer_state,sum(f.price) AS revenue_brl" + stail +
                            " GROUP BY 1 ORDER BY revenue_brl DESC,customer_state", svalues)
                _assert_rows(rows_by_key["S5"], cur.fetchall(), ["customer_state"], ["revenue_brl"])

                dtail, dvalues = _source("fact_delivery", case, False)
                cur.execute("SELECT count(*) AS n,count(*) FILTER (WHERE f.is_late=1) AS late,"
                    "count(f.review_score) AS reviewed,count(*) FILTER (WHERE f.is_bad_review=1) AS bad" + dtail, dvalues)
                delivery = cur.fetchone()
                d1 = rows_by_key["D1"][0]
                for column, expected_column in (("valid_delivered_orders", "n"), ("late_orders", "late"),
                                                ("reviewed_orders", "reviewed"), ("bad_reviews", "bad")):
                    assert d1[column] == delivery[expected_column]
                expected_late = delivery["late"] / delivery["n"] if delivery["n"] else None
                expected_bad = delivery["bad"] / delivery["reviewed"] if delivery["reviewed"] else None
                for column, expected_rate in (("late_rate", expected_late), ("bad_review_rate", expected_bad)):
                    got_rate = d1[column]
                    assert got_rate is None if expected_rate is None else abs(float(got_rate) - expected_rate) < 1e-9
                cur.execute("SELECT date_trunc(%s,d.full_date)::date AS period,count(*) FILTER (WHERE f.is_late=1)::numeric/"
                            "nullif(count(*),0) AS late_rate,count(*) FILTER (WHERE f.is_bad_review=1)::numeric/"
                            "nullif(count(f.review_score),0) AS bad_review_rate" + dtail +
                            " GROUP BY 1 ORDER BY 1", [case["grain"], *dvalues])
                _assert_rows(rows_by_key["D2"], cur.fetchall(), ["period"], ["late_rate", "bad_review_rate"])
                cur.execute("SELECT c.state AS customer_state,count(*) AS eligible_orders,"
                            "count(*) FILTER (WHERE f.is_late=1) AS late_orders,"
                            "count(*) FILTER (WHERE f.is_late=1)::numeric/nullif(count(*),0) AS late_rate" + dtail +
                            " GROUP BY 1 HAVING count(*)>=50 ORDER BY 1", dvalues)
                _assert_rows(rows_by_key["D3"], cur.fetchall(), ["customer_state"],
                             ["eligible_orders", "late_orders", "late_rate"])
                assert all(row["eligible_orders"] >= 50 and
                           abs(float(row["late_rate"]) - row["late_orders"] / row["eligible_orders"]) < 1e-9
                           for row in rows_by_key["D3"])
                bucket = ("CASE WHEN f.delay_days<=0 THEN 'Đúng hạn hoặc sớm' "
                          "WHEN f.delay_days<=3 THEN '1–3 ngày' WHEN f.delay_days<=7 THEN '4–7 ngày' "
                          "WHEN f.delay_days<=14 THEN '8–14 ngày' ELSE '15+ ngày' END")
                cur.execute("SELECT " + bucket + " AS delay_bucket,count(*) AS orders" + dtail +
                            " GROUP BY 1 ORDER BY min(f.delay_days)", dvalues)
                _assert_rows(rows_by_key["D4"], cur.fetchall(), ["delay_bucket"], ["orders"])
                cur.execute("SELECT " + bucket + " AS delay_bucket,count(*) AS total_orders,"
                            "count(f.review_score) AS reviewed_orders,count(*) FILTER (WHERE f.is_bad_review=1) AS bad_reviews,"
                            "count(*) FILTER (WHERE f.is_bad_review=1)::numeric/nullif(count(f.review_score),0) AS bad_review_rate" +
                            dtail + " GROUP BY 1 ORDER BY min(f.delay_days)", dvalues)
                _assert_rows(rows_by_key["D5"], cur.fetchall(), ["delay_bucket"],
                             ["total_orders", "reviewed_orders", "bad_reviews", "bad_review_rate"])
                assert len({row["category"] for row in rows_by_key["S2"]}) <= 5
            evidence["cases"].append({"name": case["name"], "questions": questions,
                "reconciled_questions": ["E1", "E2", "E3", "E4", "E5", "S1", "S2", "S3", "S4", "S5",
                                         "D1", "D2", "D3", "D4", "D5"],
                "filters": {key: value for key, value in case.items() if key != "name"},
                "etl_run_id": rows_by_key["STATUS_Executive"][0]["etl_run_id"],
                "source_reconciliation": "PASS"})
        evidence["question_executions"] = sum(len(case["questions"]) for case in evidence["cases"])
        with (output / "verification.json").open("w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, ensure_ascii=False, default=str)
            f.write("\n")
        os.chown(output / "verification.json", owner.st_uid, owner.st_gid)
        return evidence
    finally:
        if own_connection:
            conn.close()
        if api.session:
            api.call("DELETE", "session", {"metabase-session-id": api.session})


if __name__ == "__main__":
    result = verify()
    print(json.dumps({"status": "PASS", "question_executions": result["question_executions"],
                      "cases": len(result["cases"])}, ensure_ascii=False))
