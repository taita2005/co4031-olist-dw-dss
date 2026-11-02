"""Delivery & satisfaction: where late deliveries happen and how they hurt reviews."""
import plotly.express as px
import streamlit as st

from common import fmt_pct, run_query

st.set_page_config(page_title="Giao hàng & hài lòng", layout="wide")
st.title("Giao hàng & sự hài lòng khách hàng")

year = st.selectbox("Năm mua hàng", ["Tất cả", 2016, 2017, 2018])
year_filter = "TRUE" if year == "Tất cả" else "d.year = :year"
params = {} if year == "Tất cả" else {"year": year}
BASE = f"""
FROM dw.fact_delivery f
JOIN dw.dim_date     d ON d.date_key     = f.purchase_date_key
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_product  p ON p.product_key  = f.product_key
WHERE {year_filter}
"""

# ---------------------------------------------------------------- KPIs
k = run_query(f"""SELECT COUNT(*) AS n, AVG(f.is_late) AS late, AVG(f.delivery_days) AS days,
                         AVG(f.review_score) AS review, AVG(f.is_bad_review) AS bad {BASE}""", params).iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Đơn đã giao", f"{int(k.n):,}")
c2.metric("Tỷ lệ đúng hạn", fmt_pct(1 - k.late))
c3.metric("Số ngày giao TB", f"{k.days:.1f}")
c4.metric("Điểm review TB", f"{k.review:.2f} ★")
c5.metric("Tỷ lệ review xấu", fmt_pct(k.bad))

# ---------------------------------------------------------------- Review vs delay (discretization)
by_delay = run_query(f"""
    SELECT CASE
             WHEN f.delay_days < -7  THEN '1. Sớm > 7 ngày'
             WHEN f.delay_days < 0   THEN '2. Sớm 1–7 ngày'
             WHEN f.delay_days = 0   THEN '3. Đúng ngày'
             WHEN f.delay_days <= 3  THEN '4. Trễ 1–3 ngày'
             WHEN f.delay_days <= 7  THEN '5. Trễ 4–7 ngày'
             WHEN f.delay_days <= 14 THEN '6. Trễ 8–14 ngày'
             ELSE '7. Trễ > 14 ngày'
           END AS delay_group,
           COUNT(*) AS n_orders, AVG(f.review_score) AS avg_review, AVG(f.is_bad_review) AS bad_rate
    {BASE}
    GROUP BY 1 ORDER BY 1
""", params)
left, right = st.columns(2)
with left:
    fig = px.bar(by_delay, x="delay_group", y="avg_review", text_auto=".2f",
                 title="Điểm review TB theo mức độ trễ", hover_data=["n_orders"],
                 labels={"delay_group": "Giao so với ngày dự kiến", "avg_review": "Điểm TB"})
    st.plotly_chart(fig, use_container_width=True)
with right:
    fig = px.bar(by_delay, x="delay_group", y="bad_rate", text_auto=".0%",
                 title="Tỷ lệ review xấu (≤2★) theo mức độ trễ", hover_data=["n_orders"],
                 labels={"delay_group": "Giao so với ngày dự kiến", "bad_rate": "Tỷ lệ review xấu"})
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- By state / category
by_state = run_query(f"""
    SELECT c.state, COUNT(*) AS n_orders, AVG(f.is_late) AS late_rate,
           AVG(f.delivery_days) AS avg_days, AVG(f.is_bad_review) AS bad_rate
    {BASE}
    GROUP BY c.state ORDER BY late_rate DESC
""", params)
fig = px.bar(by_state, x="state", y="late_rate", color="bad_rate", color_continuous_scale="Reds",
             hover_data=["n_orders", "avg_days"], title="Tỷ lệ giao trễ theo bang của khách (màu = tỷ lệ review xấu)",
             labels={"state": "Bang", "late_rate": "Tỷ lệ trễ", "bad_rate": "Review xấu"})
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

by_cat = run_query(f"""
    SELECT p.category_en AS category, COUNT(*) AS n_orders, AVG(f.is_late) AS late_rate,
           AVG(f.review_score) AS avg_review, AVG(f.is_bad_review) AS bad_rate
    {BASE}
    GROUP BY 1 HAVING COUNT(*) >= 500 ORDER BY bad_rate DESC
""", params)
st.subheader("Danh mục (≥ 500 đơn), sắp theo tỷ lệ review xấu")
st.dataframe(
    by_cat.style.format({"late_rate": "{:.1%}", "bad_rate": "{:.1%}", "avg_review": "{:.2f}", "n_orders": "{:,}"}),
    use_container_width=True, hide_index=True,
)
