"""Home page: overall KPIs and monthly trends (Intelligence phase).

Run:  streamlit run src/app/Home.py
"""
import plotly.express as px
import streamlit as st

from common import FULL_MONTHS, fmt_money, fmt_pct, run_query

st.set_page_config(page_title="Olist DW & DSS", layout="wide")
st.title("Olist — Kho dữ liệu bán hàng, giao hàng & DSS")
st.caption(
    "Dashboard trên kho dữ liệu PostgreSQL (fact constellation: fact_sales + fact_delivery). "
    "Chọn trang ở thanh bên: **OLAP** để phân tích đa chiều, **Delivery** để xem hiệu suất giao hàng, "
    "**DSS** để chạy mô hình hỗ trợ quyết định, **Data Quality** để xem dữ liệu có đáng tin không."
)

# ---------------------------------------------------------------- KPIs
kpi = run_query("""
    SELECT SUM(revenue) AS revenue, SUM(n_orders) AS n_orders, SUM(n_items) AS n_items
    FROM dw.mv_monthly_kpi
""").iloc[0]
delivery = run_query("""
    SELECT AVG(is_late) AS late_rate, AVG(delivery_days) AS delivery_days,
           AVG(review_score) AS review, AVG(is_bad_review) AS bad_rate
    FROM dw.fact_delivery
""").iloc[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Doanh thu", fmt_money(kpi.revenue))
c2.metric("Số đơn hàng", f"{int(kpi.n_orders):,}")
c3.metric("Giá trị TB / đơn", fmt_money(kpi.revenue / kpi.n_orders))
c4.metric("Tỷ lệ giao trễ", fmt_pct(delivery.late_rate))
c5.metric("Điểm review TB", f"{delivery.review:.2f} ★")
c6.metric("Tỷ lệ review xấu (≤2★)", fmt_pct(delivery.bad_rate))
st.caption("Doanh thu = tổng giá sản phẩm (không gồm phí ship), loại đơn canceled/unavailable.")

# ---------------------------------------------------------------- Trends
monthly = run_query(
    "SELECT * FROM dw.mv_monthly_kpi WHERE year_month BETWEEN :start AND :end ORDER BY year_month",
    {"start": FULL_MONTHS[0], "end": FULL_MONTHS[1]},
)
left, right = st.columns(2)
with left:
    fig = px.bar(monthly, x="year_month", y="revenue", title="Doanh thu theo tháng",
                 labels={"year_month": "Tháng", "revenue": "Doanh thu (R$)"})
    st.plotly_chart(fig, use_container_width=True)
with right:
    trend = monthly.melt(id_vars="year_month", value_vars=["late_rate", "bad_review_rate"],
                         var_name="metric", value_name="rate")
    trend["metric"] = trend["metric"].map({"late_rate": "Tỷ lệ giao trễ", "bad_review_rate": "Tỷ lệ review xấu"})
    fig = px.line(trend, x="year_month", y="rate", color="metric", markers=True,
                  title="Giao trễ và review xấu đi cùng nhau",
                  labels={"year_month": "Tháng", "rate": "Tỷ lệ", "metric": ""})
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
st.caption(f"Chỉ hiển thị {FULL_MONTHS[0]} → {FULL_MONTHS[1]}: các tháng đầu/cuối bộ dữ liệu có rất ít đơn.")

# ---------------------------------------------------------------- Freshness
fresh = run_query("""
    SELECT (SELECT MAX(run_id) FROM meta.check_result WHERE run_id > '2000-01-01') AS run_id,
           (SELECT MIN(full_date) FROM dw.dim_date d JOIN dw.fact_sales f ON f.purchase_date_key = d.date_key) AS first_day,
           (SELECT MAX(full_date) FROM dw.dim_date d JOIN dw.fact_sales f ON f.purchase_date_key = d.date_key) AS last_day
""").iloc[0]
checks = run_query(
    "SELECT COUNT(*) AS n, COUNT(*) FILTER (WHERE passed) AS ok FROM meta.check_result WHERE run_id = :r",
    {"r": fresh.run_id},
).iloc[0]
status = "✅" if checks.ok == checks.n else "❌"
st.info(
    f"Dữ liệu đơn hàng từ {fresh.first_day:%d/%m/%Y} đến {fresh.last_day:%d/%m/%Y}. "
    f"ETL lần cuối {fresh.run_id:%d/%m/%Y %H:%M}, {status} {checks.ok}/{checks.n} kiểm tra chất lượng đạt "
    "(chi tiết ở trang **Data Quality**)."
)
