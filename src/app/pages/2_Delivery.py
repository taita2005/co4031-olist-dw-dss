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

# ---------------------------------------------------------------- Scope: how many bad reviews are about lateness?
scope = run_query(f"""
    SELECT CASE WHEN f.is_late = 1 THEN 'Đơn giao trễ' ELSE 'Đơn đúng hạn' END AS kind,
           COUNT(*) AS n_orders, SUM(f.is_bad_review) AS n_bad
    {BASE} AND f.review_score IS NOT NULL
    GROUP BY 1 ORDER BY 1 DESC
""", params)
total_bad = scope["n_bad"].sum()
late_row = scope.set_index("kind").reindex(["Đơn giao trễ", "Đơn đúng hạn"]).fillna(0)
st.subheader("Giao trễ giải thích được bao nhiêu review xấu?")
left, right = st.columns([2, 3])
with left:
    s1, s2 = st.columns(2)
    s1.metric("Review xấu trên đơn trễ", f"{int(late_row.loc['Đơn giao trễ', 'n_bad']):,}",
              help="Đơn giao sau ngày dự kiến và bị review ≤ 2★")
    s2.metric("Review xấu trên đơn đúng hạn", f"{int(late_row.loc['Đơn đúng hạn', 'n_bad']):,}")
    share = late_row.loc["Đơn giao trễ", "n_bad"] / total_bad if total_bad else 0
    st.markdown(
        f"Chỉ **{share:.0%}** review xấu rơi vào đơn giao trễ. Cải thiện giao hàng (câu hỏi của DSS) chỉ tác động "
        "được phần này; phần còn lại do sản phẩm, người bán… nằm ngoài phạm vi."
    )
with right:
    scope["bad_rate"] = scope["n_bad"] / scope["n_orders"]
    fig = px.bar(scope, x="bad_rate", y="kind", orientation="h", text_auto=".0%",
                 hover_data={"n_orders": ":,", "n_bad": ":,"},
                 title="Tỷ lệ review xấu: đơn trễ so với đơn đúng hạn",
                 labels={"kind": "", "bad_rate": "Tỷ lệ review xấu", "n_orders": "Số đơn", "n_bad": "Review xấu"})
    fig.update_xaxes(tickformat=".0%")
    fig.update_traces(marker_color="#c0392b")
    fig.update_layout(height=230, margin=dict(t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

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

# ---------------------------------------------------------------- How late are the late orders?
late_days = run_query(f"""
    SELECT LEAST(f.delay_days, 31) AS days_late, COUNT(*) AS n_orders, AVG(f.is_bad_review) AS bad_rate
    {BASE} AND f.is_late = 1
    GROUP BY 1 ORDER BY 1
""", params)
st.subheader("Đơn trễ thì trễ bao nhiêu ngày?")
st.caption("Chỉ tính đơn giao trễ (đơn đúng hạn được tách riêng để không lấn át biểu đồ). Cột cuối gộp mọi đơn trễ > 30 ngày.")
late_days["label"] = late_days["days_late"].map(lambda d: "> 30" if d > 30 else str(d))
left, right = st.columns(2)
with left:
    fig = px.bar(late_days, x="label", y="n_orders", title="Số đơn theo số ngày trễ",
                 labels={"label": "Số ngày trễ", "n_orders": "Số đơn"})
    fig.update_traces(marker_color="#7f8c8d")
    st.plotly_chart(fig, use_container_width=True)
with right:
    shown = late_days[late_days["n_orders"] >= 30]
    fig = px.line(shown, x="label", y="bad_rate", markers=True, hover_data={"n_orders": ":,"},
                  title="Tỷ lệ review xấu theo số ngày trễ (chỉ mức có ≥ 30 đơn)",
                  labels={"label": "Số ngày trễ", "bad_rate": "Tỷ lệ review xấu", "n_orders": "Số đơn"})
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_traces(line_color="#c0392b")
    st.plotly_chart(fig, use_container_width=True)
if not late_days.empty:
    median_days = late_days.loc[late_days["n_orders"].cumsum() >= late_days["n_orders"].sum() / 2, "label"].iloc[0]
    rate = shown.set_index("days_late")["bad_rate"]
    week = (f" Tỷ lệ review xấu đi từ {rate[1]:.0%} (trễ 1 ngày) lên {rate[7]:.0%} (trễ 7 ngày): giảm số ngày trễ "
            "cũng có ích, không chỉ giảm số đơn trễ.") if {1, 7} <= set(rate.index) else ""
    st.caption(f"Một nửa số đơn trễ chỉ trễ ≤ {median_days} ngày.{week}")

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

st.markdown("**Bảng mẫu số theo bang**: mọi tỷ lệ ở trên đều là *tổng tử số / tổng mẫu số*, không phải trung bình "
            "của các tỷ lệ. Bang có ít đơn thì tỷ lệ dao động mạnh; đọc tỷ lệ cùng với số đơn.")
denom = run_query(f"""
    SELECT c.state AS "Bang", c.region AS "Vùng",
           COUNT(*) AS "Đơn đã giao",
           SUM(f.is_late) AS "Đơn trễ",
           SUM(f.is_late)::FLOAT / COUNT(*) AS "Tỷ lệ trễ",
           COUNT(f.review_score) AS "Đơn có review",
           SUM(f.is_bad_review) AS "Review xấu",
           SUM(f.is_bad_review)::FLOAT / NULLIF(COUNT(f.review_score), 0) AS "Tỷ lệ review xấu",
           SUM(f.is_bad_review * f.is_late) AS "Review xấu trên đơn trễ",
           AVG(f.delivery_days) AS "Số ngày giao TB"
    {BASE}
    GROUP BY c.state, c.region ORDER BY "Đơn đã giao" DESC
""", params)
denom["Ít đơn (< 500)"] = denom["Đơn đã giao"] < 500
st.dataframe(
    denom, use_container_width=True, hide_index=True,
    column_config={
        "Tỷ lệ trễ": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Tỷ lệ review xấu": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Số ngày giao TB": st.column_config.NumberColumn(format="%.1f"),
    },
)

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
