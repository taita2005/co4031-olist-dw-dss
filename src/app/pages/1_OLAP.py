"""OLAP Explorer: roll-up, drill-down, slice, dice and pivot on the DW.

ROLAP: every interaction builds a GROUP BY query over a fact table joined
with the shared (conformed) dimensions. Only whitelisted expressions from
the config below are put into SQL; user-chosen values go in as parameters.
"""
import plotly.express as px
import streamlit as st

from common import run_query

st.set_page_config(page_title="OLAP Explorer", layout="wide")
st.title("OLAP Explorer")

# ---------------------------------------------------------------- Cube definition
# Dimension hierarchies, from the coarsest level to the finest
HIERARCHIES = {
    "Thời gian": [("Năm", "d.year::text"), ("Quý", "d.year || '-Q' || d.quarter"), ("Tháng", "d.year_month")],
    "Địa lý khách hàng": [("Vùng", "c.region"), ("Bang", "c.state"), ("Thành phố", "c.city")],
    "Địa lý người bán": [("Vùng", "s.region"), ("Bang", "s.state"), ("Thành phố", "s.city")],
    "Sản phẩm": [("Danh mục", "p.category_en")],
}

# Both facts share the same dimensions (fact constellation).
# additive=True means the measure can be summed across rows (so totals are valid).
FACTS = {
    "Bán hàng (fact_sales)": {
        "table": "dw.fact_sales",
        "date_key": "purchase_date_key",
        "filter": "f.order_status NOT IN ('canceled', 'unavailable')",
        "measures": {
            "Doanh thu (R$)": ("SUM(f.price)", True),
            "Phí vận chuyển (R$)": ("SUM(f.freight_value)", True),
            "Số sản phẩm bán": ("COUNT(*)", True),
            "Số đơn hàng": ("COUNT(DISTINCT f.order_id)", False),
            "Giá TB / sản phẩm (R$)": ("AVG(f.price)", False),
        },
    },
    "Giao hàng (fact_delivery)": {
        "table": "dw.fact_delivery",
        "date_key": "purchase_date_key",
        "filter": "TRUE",
        "measures": {
            "Số đơn đã giao": ("COUNT(*)", True),
            "Tỷ lệ giao trễ (%)": ("100 * AVG(f.is_late)", False),
            "Số ngày giao TB": ("AVG(f.delivery_days)", False),
            "Điểm review TB": ("AVG(f.review_score)", False),
            "Tỷ lệ review xấu (%)": ("100 * AVG(f.is_bad_review)", False),
        },
    },
}
NONE = "(không)"

# ---------------------------------------------------------------- Session state & callbacks
st.session_state.setdefault("row_dim", "Thời gian")
st.session_state.setdefault("row_level", 0)
st.session_state.setdefault("col_dim", NONE)
st.session_state.setdefault("col_level", 0)


def reset_level(prefix: str) -> None:
    st.session_state[f"{prefix}_level"] = 0


def drill(step: int) -> None:
    levels = HIERARCHIES[st.session_state.row_dim]
    st.session_state.row_level = min(max(st.session_state.row_level + step, 0), len(levels) - 1)


def pivot() -> None:
    if st.session_state.col_dim == NONE:
        return
    s = st.session_state
    s.row_dim, s.col_dim = s.col_dim, s.row_dim
    s.row_level, s.col_level = s.col_level, s.row_level


# ---------------------------------------------------------------- Controls
with st.sidebar:
    st.header("Khối dữ liệu")
    fact_name = st.radio("Bảng fact", list(FACTS))
    fact = FACTS[fact_name]
    measure_name = st.selectbox("Measure", list(fact["measures"]))
    measure_sql, additive = fact["measures"][measure_name]

    st.header("Slice")
    year = st.selectbox("Cố định năm", ["Tất cả", 2016, 2017, 2018])

    st.header("Dice")
    states = run_query("SELECT DISTINCT state FROM dw.dim_customer ORDER BY 1")["state"].tolist()
    categories = run_query("SELECT DISTINCT category_en FROM dw.dim_product ORDER BY 1")["category_en"].tolist()
    dice_states = st.multiselect("Bang của khách hàng", states)
    dice_categories = st.multiselect("Danh mục", categories)

c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
with c1:
    st.selectbox("Chiều theo hàng", list(HIERARCHIES), key="row_dim", on_change=reset_level, args=("row",))
    row_levels = HIERARCHIES[st.session_state.row_dim]
    st.selectbox("Cấp (hàng)", range(len(row_levels)), key="row_level", format_func=lambda i: row_levels[i][0])
with c2:
    col_options = [NONE] + [d for d in HIERARCHIES if d != st.session_state.row_dim]
    if st.session_state.col_dim not in col_options:
        st.session_state.col_dim = NONE
    st.selectbox("Chiều theo cột", col_options, key="col_dim", on_change=reset_level, args=("col",))
    if st.session_state.col_dim != NONE:
        col_levels = HIERARCHIES[st.session_state.col_dim]
        st.selectbox("Cấp (cột)", range(len(col_levels)), key="col_level", format_func=lambda i: col_levels[i][0])
with c3:
    st.write("")
    st.button("⬇ Drill-down (hàng)", on_click=drill, args=(1,), use_container_width=True,
              disabled=st.session_state.row_level >= len(row_levels) - 1)
    st.button("⬆ Roll-up (hàng)", on_click=drill, args=(-1,), use_container_width=True,
              disabled=st.session_state.row_level == 0)
with c4:
    st.write("")
    st.button("🔄 Pivot (đổi hàng ↔ cột)", on_click=pivot, use_container_width=True,
              disabled=st.session_state.col_dim == NONE)

# ---------------------------------------------------------------- Query
row_label, row_expr = row_levels[st.session_state.row_level]
has_cols = st.session_state.col_dim != NONE
select = [f"{row_expr} AS row_val"]
if has_cols:
    col_label, col_expr = HIERARCHIES[st.session_state.col_dim][st.session_state.col_level]
    select.append(f"{col_expr} AS col_val")

where, params = [fact["filter"]], {}
if year != "Tất cả":
    where.append("d.year = :year")
    params["year"] = year
if dice_states:
    where.append("c.state = ANY(:states)")
    params["states"] = dice_states
if dice_categories:
    where.append("p.category_en = ANY(:categories)")
    params["categories"] = dice_categories

group_by = "1, 2" if has_cols else "1"
sql = f"""SELECT {', '.join(select)}, {measure_sql} AS value
FROM {fact['table']} f
JOIN dw.dim_date     d ON d.date_key     = f.{fact['date_key']}
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_seller   s ON s.seller_key   = f.seller_key
JOIN dw.dim_product  p ON p.product_key  = f.product_key
WHERE {' AND '.join(where)}
GROUP BY {group_by}
ORDER BY {group_by}"""

result = run_query(sql, params)
if result.empty:
    st.warning("Không có dữ liệu cho bộ lọc này.")
    st.stop()
result["value"] = result["value"].astype(float)

# ---------------------------------------------------------------- Display
st.subheader(f"{measure_name} theo {row_label.lower()}"
             + (f" × {col_label.lower()}" if has_cols else ""))
if has_cols:
    table = result.pivot_table(index="row_val", columns="col_val", values="value", aggfunc="sum")
    if additive:
        table["Tổng"] = table.sum(axis=1)
        table.loc["Tổng"] = table.sum()
    table.index.name, table.columns.name = row_label, col_label
    st.dataframe(table.style.format("{:,.2f}", na_rep="–"), use_container_width=True)
    heat = table.drop(index="Tổng", columns="Tổng", errors="ignore")
    if heat.shape[0] <= 60 and heat.shape[1] <= 60:
        fig = px.imshow(heat, aspect="auto", color_continuous_scale="Blues",
                        labels={"x": col_label, "y": row_label, "color": measure_name})
        st.plotly_chart(fig, use_container_width=True)
else:
    shown = result.rename(columns={"row_val": row_label, "value": measure_name})
    if len(shown) > 40:  # e.g. city level: show the top values only
        shown = shown.nlargest(40, measure_name)
        st.caption("Hiển thị 40 giá trị lớn nhất.")
    st.plotly_chart(px.bar(shown, x=row_label, y=measure_name), use_container_width=True)
    st.dataframe(shown, use_container_width=True, hide_index=True)

if not additive:
    st.info("Measure này **không cộng dồn được** (đếm distinct / trung bình / tỷ lệ), "
            "nên không hiển thị dòng tổng; muốn có tổng phải tính lại từ fact ở cấp cao hơn (roll-up).")

with st.expander("SQL được sinh ra (ROLAP)"):
    st.code(sql, language="sql")
    if params:
        st.write("Tham số:", params)

with st.expander("Khối tổng hợp sẵn: dw.mv_sales_cube (GROUP BY CUBE năm × vùng × danh mục)"):
    cube = run_query("""
        SELECT COALESCE(year::text, 'Tất cả') AS year,
               COALESCE(customer_region, 'Tất cả') AS region,
               COALESCE(category, 'Tất cả') AS category,
               revenue, n_items
        FROM dw.mv_sales_cube
        WHERE category IS NULL
        ORDER BY year, region
    """)
    st.caption("Các dòng 'Tất cả' là subtotal do CUBE sinh ra (ở đây lọc category = Tất cả cho gọn).")
    st.dataframe(cube, use_container_width=True, hide_index=True)
