"""Grain-safe native questions for the three local Metabase dashboards."""


def _filtered(view, *, category=False, grain=False):
    tags = ["start_date", "end_date", "customer_region", "customer_state"]
    where = ["s.ready", f"[[AND bi.{view}.purchase_date >= {{{{start_date}}}}]]",
             f"[[AND bi.{view}.purchase_date < {{{{end_date}}}}]]",
             "[[AND {{customer_region}}]]", "[[AND {{customer_state}}]]"]
    if category:
        tags.append("category")
        where.append("[[AND {{category}}]]")
    expr = " ".join(where)
    return f"WITH s AS (SELECT ready FROM bi.dataset_status), f AS (SELECT bi.{view}.* FROM bi.{view} CROSS JOIN s WHERE {expr})", tags, grain


def _card(key, name, view, query, display="table", *, category=False, grain=False, dimensions=None, metrics=None,
          settings=None):
    cte, filters, _ = _filtered(view, category=category, grain=grain)
    return {"key": key, "name": name, "view": view, "sql": cte + " " + query,
            "filters": filters + (["grain"] if grain else []), "display": display,
            "dimensions": dimensions or [], "metrics": metrics or [], "settings": settings or {}}


def dashboard_specs():
    sales, delivery = "sales_items", "delivery_orders"
    period = "CASE {{grain}} WHEN 'year' THEN date_trunc('year',purchase_date) " \
             "WHEN 'quarter' THEN date_trunc('quarter',purchase_date) " \
             "ELSE date_trunc('month',purchase_date) END::date AS period"
    late = "count(*) FILTER (WHERE is_late)::numeric / nullif(count(*),0)"
    review = "count(*) FILTER (WHERE is_bad_review)::numeric / nullif(count(review_score),0)"
    exec_cards = [
        _card("E1", "KPI doanh thu giá sản phẩm", sales, "SELECT sum(price) AS revenue_brl FROM f", "scalar",
              settings={'column_settings': {'["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("E2", "KPI số đơn bán hàng", sales, "SELECT count(DISTINCT order_id) AS orders FROM f", "scalar"),
        _card("E3", "Đường doanh thu theo thời gian", sales,
              f"SELECT {period},sum(price) AS revenue_brl FROM f GROUP BY 1 ORDER BY 1", "line",
              grain=True, dimensions=["period"], metrics=["revenue_brl"], settings={
                  "graph.colors": ["#2563EB"], "graph.x_axis.title_text": "Thời gian", "graph.y_axis.title_text": "Doanh thu (BRL)",
                  'column_settings': {'["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("E4", "Combo số đơn và AOV", sales,
              f"SELECT {period},count(DISTINCT order_id) AS orders, "
              "sum(price)/nullif(count(DISTINCT order_id),0) AS aov_brl FROM f GROUP BY 1 ORDER BY 1",
              "combo", grain=True, dimensions=["period"], metrics=["orders", "aov_brl"], settings={
                  "series_settings": {"orders": {"display": "bar"}, "aov_brl": {"display": "line"}},
                  "graph.y_axis.auto_split": True, "graph.colors": ["#2563EB", "#14B8A6"],
                  "graph.x_axis.title_text": "Thời gian", "graph.y_axis.title_text": "Số đơn / AOV (BRL)", 'column_settings': {
                      '["name","aov_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("E5", "Pareto doanh thu theo bang", sales,
              "SELECT customer_state,sum(price) AS revenue_brl, "
              "sum(sum(price)) OVER (ORDER BY sum(price) DESC,customer_state) / nullif(sum(sum(price)) OVER (),0) AS cumulative_share "
              "FROM f GROUP BY customer_state ORDER BY revenue_brl DESC,customer_state", "combo",
              dimensions=["customer_state"], metrics=["revenue_brl", "cumulative_share"], settings={
                  "series_settings": {"revenue_brl": {"display": "bar"}, "cumulative_share": {"display": "line"}},
                  "graph.y_axis.auto_split": True, "graph.colors": ["#2563EB", "#14B8A6"],
                  "graph.x_axis.title_text": "Bang", "column_settings": {
                      '["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"},
                      '["name","cumulative_share"]': {"number_style": "percent"}}}),
    ]
    sales_cards = [
        _card("S1", "Top 10 danh mục theo doanh thu", sales,
              "SELECT category,sum(price) AS revenue_brl FROM f GROUP BY category ORDER BY revenue_brl DESC,category LIMIT 10",
              "row", category=True, dimensions=["category"], metrics=["revenue_brl"], settings={
                  "graph.colors": ["#2563EB"], "graph.x_axis.title_text": "Doanh thu (BRL)",
                  'column_settings': {'["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("S2", "Xu hướng top 5 danh mục", sales,
              f", top5 AS (SELECT category FROM f GROUP BY category ORDER BY sum(price) DESC,category LIMIT 5) "
              f"SELECT {period},category,sum(price) AS revenue_brl FROM f JOIN top5 USING(category) GROUP BY 1,2 ORDER BY 1,2", "line",
              category=True, grain=True, dimensions=["period", "category"], metrics=["revenue_brl"], settings={
                  "graph.colors": ["#2563EB", "#F97316", "#14B8A6", "#A855F7", "#EAB308"],
                  "graph.x_axis.title_text": "Thời gian", "graph.y_axis.title_text": "Doanh thu (BRL)",
                  'column_settings': {'["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("S3", "Cơ cấu danh mục theo vùng", sales,
              ", top5 AS (SELECT category FROM f GROUP BY category ORDER BY sum(price) DESC,category LIMIT 5), "
              "g AS (SELECT customer_region,CASE WHEN category IN (SELECT category FROM top5) THEN category "
              "ELSE 'Danh mục khác trong bộ lọc' END AS category_group,sum(price) AS revenue_brl FROM f GROUP BY 1,2) "
              "SELECT customer_region,category_group,revenue_brl,revenue_brl/nullif(sum(revenue_brl) OVER (PARTITION BY customer_region),0) AS share "
              "FROM g ORDER BY 1,2", "bar", category=True, dimensions=["customer_region", "category_group"],
              metrics=["share"], settings={"stackable.stack_type": "normalized",
                  "graph.colors": ["#2563EB", "#F97316", "#14B8A6", "#A855F7", "#EAB308", "#94A3B8"],
                  'column_settings': {'["name","share"]': {"number_style": "percent"}}}),
        _card("S4", "Ma trận vùng × top 10 danh mục", sales,
              ", top10 AS (SELECT category FROM f GROUP BY category ORDER BY sum(price) DESC,category LIMIT 10) "
              "SELECT category, sum(price) FILTER (WHERE customer_region='North') AS north_brl, "
              "sum(price) FILTER (WHERE customer_region='Northeast') AS northeast_brl, "
              "sum(price) FILTER (WHERE customer_region='Central-West') AS central_west_brl, "
              "sum(price) FILTER (WHERE customer_region='Southeast') AS southeast_brl, "
              "sum(price) FILTER (WHERE customer_region='South') AS south_brl, "
              "sum(price) FILTER (WHERE customer_region='Unknown') AS unknown_brl "
              "FROM f WHERE category IN (SELECT category FROM top10) GROUP BY category ORDER BY sum(price) DESC,category", "table",
              category=True, settings={"column_settings": {
                  '["name","north_brl"]': {"number_style": "currency", "currency": "BRL"},
                  '["name","northeast_brl"]': {"number_style": "currency", "currency": "BRL"},
                  '["name","central_west_brl"]': {"number_style": "currency", "currency": "BRL"},
                  '["name","southeast_brl"]': {"number_style": "currency", "currency": "BRL"},
                  '["name","south_brl"]': {"number_style": "currency", "currency": "BRL"},
                  '["name","unknown_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
        _card("S5", "Doanh thu theo bang", sales,
              "SELECT customer_state,sum(price) AS revenue_brl FROM f GROUP BY customer_state ORDER BY revenue_brl DESC,customer_state",
              "row", category=True, dimensions=["customer_state"], metrics=["revenue_brl"], settings={
                  "graph.colors": ["#2563EB"], "graph.x_axis.title_text": "Doanh thu (BRL)",
                  'column_settings': {'["name","revenue_brl"]': {"number_style": "currency", "currency": "BRL"}}}),
    ]
    delivery_cards = [
        _card("D1", "Bảng KPI và mẫu số giao hàng", delivery,
              f"SELECT count(*) AS valid_delivered_orders,count(*) FILTER (WHERE is_late) AS late_orders, "
              f"count(review_score) AS reviewed_orders,count(*) FILTER (WHERE is_bad_review) AS bad_reviews, "
              f"{late} AS late_rate,{review} AS bad_review_rate FROM f", "table", settings={
                  'column_settings': {'["name","late_rate"]': {"column_title": "Tỷ lệ giao trễ", "number_style": "percent"},
                      '["name","bad_review_rate"]': {"column_title": "Tỷ lệ review xấu", "number_style": "percent"},
                      '["name","valid_delivered_orders"]': {"column_title": "Đơn giao đủ ngày"},
                      '["name","late_orders"]': {"column_title": "Đơn giao trễ"},
                      '["name","reviewed_orders"]': {"column_title": "Đơn có review"},
                      '["name","bad_reviews"]': {"column_title": "Review xấu (1–2 sao)"}}}),
        _card("D2", "Xu hướng giao trễ và review xấu", delivery,
              f"SELECT {period},{late} AS late_rate,{review} AS bad_review_rate FROM f GROUP BY 1 ORDER BY 1",
              "line", grain=True, dimensions=["period"], metrics=["late_rate", "bad_review_rate"], settings={
                  "graph.colors": ["#F97316", "#DC2626"], "graph.x_axis.title_text": "Thời gian",
                  'column_settings': {'["name","late_rate"]': {"number_style": "percent"},
                                      '["name","bad_review_rate"]': {"number_style": "percent"}}}),
        _card("D3", "Mức độ tập trung vấn đề theo bang", delivery,
              "SELECT customer_state,count(*) AS eligible_orders,count(*) FILTER (WHERE is_late) AS late_orders, "
              f"{late} AS late_rate FROM f GROUP BY customer_state HAVING count(*)>=50 ORDER BY customer_state",
              "scatter", dimensions=["eligible_orders", "customer_state"], metrics=["late_rate"],
              settings={"scatter.bubble": "late_orders", "graph.show_legend": False, "graph.colors": ["#F97316"],
                        "graph.x_axis.title_text": "Đơn giao đủ ngày", "graph.y_axis.title_text": "Tỷ lệ giao trễ",
                        'column_settings': {'["name","late_rate"]': {"number_style": "percent"}}}),
        _card("D4", "Phân bố ngày trễ", delivery,
              "SELECT delay_bucket,bucket_order,count(*) AS orders FROM f GROUP BY 1,2 ORDER BY bucket_order", "bar",
              dimensions=["delay_bucket"], metrics=["orders"], settings={"graph.colors": ["#F97316"]}),
        _card("D5", "Review xấu theo nhóm ngày trễ", delivery,
              "SELECT delay_bucket,bucket_order,count(*) AS total_orders,count(review_score) AS reviewed_orders, "
              "count(*) FILTER (WHERE is_bad_review) AS bad_reviews, "
              "count(*) FILTER (WHERE is_bad_review)::numeric/nullif(count(review_score),0) AS bad_review_rate "
              "FROM f GROUP BY 1,2 ORDER BY bucket_order", "combo", dimensions=["delay_bucket"],
              metrics=["bad_review_rate", "reviewed_orders"], settings={
                  "series_settings": {"bad_review_rate": {"display": "bar"}, "reviewed_orders": {"display": "line"}},
                  "graph.y_axis.auto_split": True, "graph.colors": ["#DC2626", "#F97316"],
                  "graph.x_axis.title_text": "Nhóm ngày trễ",
                  'column_settings': {'["name","bad_review_rate"]': {"number_style": "percent"}}}),
    ]
    status = {"key": "STATUS", "name": "Trạng thái dataset",
              "sql": "SELECT etl_run_id,check_count,failed_count,ready FROM bi.dataset_status",
              "filters": [], "display": "table", "dimensions": [], "metrics": [], "settings": {}}
    boards = {"Executive": {"cards": exec_cards, "status": status},
              "Sales OLAP": {"cards": sales_cards, "status": status},
              "Delivery Quality": {"cards": delivery_cards, "status": status}}
    labels = {
        "period": "Kỳ", "revenue_brl": "Doanh thu (BRL)", "orders": "Số đơn",
        "aov_brl": "Giá trị đơn trung bình (BRL)", "customer_state": "Bang",
        "cumulative_share": "Tỷ trọng lũy kế", "category": "Danh mục",
        "customer_region": "Vùng", "category_group": "Nhóm danh mục", "share": "Tỷ trọng",
        "north_brl": "Bắc", "northeast_brl": "Đông Bắc",
        "central_west_brl": "Trung Tây", "southeast_brl": "Đông Nam",
        "south_brl": "Nam", "unknown_brl": "Chưa rõ",
        "valid_delivered_orders": "Đơn giao đủ ngày", "late_orders": "Đơn giao trễ",
        "reviewed_orders": "Đơn có review", "bad_reviews": "Review xấu (1–2 sao)",
        "late_rate": "Tỷ lệ giao trễ", "bad_review_rate": "Tỷ lệ review xấu",
        "eligible_orders": "Đơn đủ điều kiện", "delay_bucket": "Nhóm ngày trễ",
        "bucket_order": "Thứ tự nhóm", "total_orders": "Tổng đơn",
    }
    currency = {"revenue_brl", "aov_brl", "north_brl", "northeast_brl", "central_west_brl",
                "southeast_brl", "south_brl", "unknown_brl"}
    percentages = {"cumulative_share", "share", "late_rate", "bad_review_rate"}
    visible_fields = {
        "E1": {"revenue_brl"}, "E2": {"orders"}, "E3": {"period", "revenue_brl"},
        "E4": {"period", "orders", "aov_brl"},
        "E5": {"customer_state", "revenue_brl", "cumulative_share"},
        "S1": {"category", "revenue_brl"}, "S2": {"period", "category", "revenue_brl"},
        "S3": {"customer_region", "category_group", "revenue_brl", "share"},
        "S4": {"category", "north_brl", "northeast_brl", "central_west_brl", "southeast_brl",
               "south_brl", "unknown_brl"},
        "S5": {"customer_state", "revenue_brl"},
        "D1": {"valid_delivered_orders", "late_orders", "reviewed_orders", "bad_reviews", "late_rate", "bad_review_rate"},
        "D2": {"period", "late_rate", "bad_review_rate"},
        "D3": {"customer_state", "eligible_orders", "late_orders", "late_rate"},
        "D4": {"delay_bucket", "bucket_order", "orders"},
        "D5": {"delay_bucket", "bucket_order", "total_orders", "reviewed_orders", "bad_reviews", "bad_review_rate"},
    }
    for board in boards.values():
        for card in board["cards"]:
            column_settings = dict(card["settings"].get("column_settings", {}))
            for field in visible_fields[card["key"]]:
                title = labels[field]
                key = f'["name","{field}"]'
                setting = dict(column_settings.get(key, {}))
                setting["column_title"] = title
                if field in currency:
                    setting.update({"number_style": "currency", "currency": "BRL"})
                elif field in percentages:
                    setting["number_style"] = "percent"
                column_settings[key] = setting
            card["settings"]["column_settings"] = column_settings
    return boards


def card_payload(spec, database_id, collection_id, fields):
    tags = {}
    for name in spec["filters"]:
        if name in ("start_date", "end_date"):
            tags[name] = {"id": name, "name": name, "display-name": "Ngày bắt đầu" if name == "start_date" else "Ngày kết thúc",
                          "type": "date", "default": "2017-01-01" if name == "start_date" else "2018-09-01"}
        elif name == "grain":
            tags[name] = {"id": name, "name": name, "display-name": "Nhóm thời gian", "type": "text",
                          "default": "month", "required": True}
        else:
            tags[name] = {"id": name, "name": name, "display-name": name.replace("_", " ").title(),
                          "type": "dimension", "dimension": ["field", fields[name], None],
                          "widget-type": "string/="}
    settings = dict(spec["settings"])
    if spec["display"] in ("line", "bar", "row", "combo", "scatter") and spec["dimensions"]:
        settings.setdefault("graph.dimensions", spec["dimensions"])
        settings.setdefault("graph.metrics", spec["metrics"])
    return {"name": spec["name"], "description": f"{spec['key']} — aggregate query; no order IDs returned.",
            "type": "question", "collection_id": collection_id, "display": spec["display"],
            "visualization_settings": settings,
            "dataset_query": {"database": database_id, "type": "native",
                              "native": {"query": spec["sql"], "template-tags": tags}}}


def dashboard_parameters(sales=False):
    params = [
        {"id": "start_date", "name": "Ngày bắt đầu", "slug": "start_date", "type": "date/single", "default": "2017-01-01"},
        {"id": "end_date", "name": "Ngày kết thúc (không gồm)", "slug": "end_date", "type": "date/single", "default": "2018-09-01"},
        {"id": "customer_region", "name": "Vùng", "slug": "customer_region", "type": "string/=", "isMultiSelect": True},
        {"id": "customer_state", "name": "Bang", "slug": "customer_state", "type": "string/=", "isMultiSelect": True},
    ]
    if sales:
        params.append({"id": "category", "name": "Danh mục", "slug": "category", "type": "string/=", "isMultiSelect": True})
    params.append({"id": "grain", "name": "Nhóm thời gian", "slug": "grain", "type": "string/=", "default": ["month"],
                   "values_source_type": "static-list", "values_source_config": {"values": [["month", "Tháng"], ["quarter", "Quý"], ["year", "Năm"]]}})
    return params
