"""DSS page: decision tree model, what-if, sensitivity, goal seeking and priority ranking.

Layout follows Simon's decision phases: Design (model) -> Choice (ranking,
what-if, goal seeking) -> Implementation (recommendation).
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from common import engine, fmt_pct
from dss import whatif
from dss.train_model import load_dataset, load_model

st.set_page_config(page_title="DSS", layout="wide")
st.title("Hệ hỗ trợ quyết định: giảm review xấu bằng cải thiện giao hàng")


@st.cache_resource(show_spinner="Đang nạp mô hình…")
def get_model():
    return load_model(engine())


@st.cache_data(show_spinner="Đang đọc dữ liệu từ kho…")
def get_data() -> pd.DataFrame:
    return load_dataset(engine())


@st.cache_data(show_spinner=False)
def get_ranking(_bundle, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    return whatif.priority_ranking(_bundle, df, group_col)


bundle, df = get_model(), get_data()
metrics = bundle["metrics"]
SCOPES = {"Toàn quốc": None, "Theo bang": "customer_state", "Theo danh mục": "category"}

tab_model, tab_rank, tab_whatif, tab_goal = st.tabs(
    ["1. Mô hình (Design)", "2. Xếp hạng ưu tiên (Choice)", "3. What-if & Sensitivity", "4. Goal seeking"]
)

# ---------------------------------------------------------------- 1. Model
with tab_model:
    st.markdown(
        "**Cây quyết định** (tiêu chí *entropy / information gain*, họ ID3/C4.5) dự đoán đơn hàng có bị "
        "review xấu (≤ 2★) hay không, dựa trên dữ liệu giao hàng trong `fact_delivery`. "
        "Mỗi lá của cây là một nhóm đơn hàng; tỷ lệ review xấu thực tế của nhóm đó được dùng làm "
        "**xác suất** trong các phân tích what-if (mô hình *under risk*)."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accuracy", fmt_pct(metrics["accuracy"]))
    c2.metric("Precision (review xấu)", fmt_pct(metrics["precision_bad"]))
    c3.metric("Recall (review xấu)", fmt_pct(metrics["recall_bad"]))
    c4.metric("F1 (review xấu)", f"{metrics['f1_bad']:.3f}")
    st.caption(f"Train {metrics['n_train']:,} / test {metrics['n_test']:,} đơn (80/20). "
               f"Tỷ lệ review xấu gốc: {fmt_pct(metrics['bad_review_rate'])}.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Luật IF-THEN (sắp theo rủi ro)")
        rules = pd.DataFrame(bundle["rules"])
        rules["conditions"] = rules["conditions"].apply(lambda c: " AND ".join(c))
        st.dataframe(
            rules.rename(columns={"conditions": "IF", "bad_rate": "P(review xấu)", "n_orders": "Số đơn (train)"})
                 .style.format({"P(review xấu)": "{:.1%}", "Số đơn (train)": "{:,}"}),
            use_container_width=True, hide_index=True,
        )
    with right:
        imp = pd.DataFrame(metrics["feature_importance"].items(), columns=["feature", "importance"])
        imp = imp[imp["importance"] > 0]
        st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h",
                               title="Độ quan trọng của thuộc tính"), use_container_width=True)
        cm = metrics["confusion_matrix"]
        st.markdown("**Confusion matrix (tập test)**")
        st.table(pd.DataFrame(cm, index=["Thực tế: tốt", "Thực tế: xấu"], columns=["Dự đoán: tốt", "Dự đoán: xấu"]))

    ig = metrics["information_gain_is_late"]
    st.markdown(
        f"**Ví dụ tính information gain cho thuộc tính `is_late`:** "
        f"Info(D) = {ig['info_D']:.4f}, Info_is_late(D) = {ig['info_A']:.4f} → "
        f"Gain(is_late) = {ig['gain']:.4f} bit."
    )

# ---------------------------------------------------------------- 2. Ranking
with tab_rank:
    st.markdown("Nếu **toàn bộ đơn trễ** trong một nhóm được giao đúng hạn, mô hình dự kiến tránh được bao nhiêu "
                "review xấu? Nhóm có con số lớn nhất là nơi nên ưu tiên đầu tư logistics.")
    group_label = st.radio("Xếp hạng theo", ["Bang của khách hàng", "Danh mục sản phẩm"], horizontal=True)
    group_col = "customer_state" if group_label.startswith("Bang") else "category"
    ranking = get_ranking(bundle, df, group_col)
    top = ranking.head(10)
    fig = px.bar(top, x=group_col, y="bad_reviews_avoided", color="late_rate", color_continuous_scale="Reds",
                 title="Top 10 nhóm theo số review xấu tránh được",
                 labels={group_col: group_label, "bad_reviews_avoided": "Review xấu tránh được",
                         "late_rate": "Tỷ lệ trễ"})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        ranking.rename(columns={
            group_col: group_label, "n_orders": "Số đơn", "late_rate": "Tỷ lệ trễ",
            "bad_review_rate": "Tỷ lệ review xấu", "bad_reviews_avoided": "Review xấu tránh được",
            "late_order_value": "Giá trị đơn trễ (R$)", "bad_rate_reduction_pts": "Giảm tỷ lệ review xấu",
        }).style.format({
            "Số đơn": "{:,}", "Tỷ lệ trễ": "{:.1%}", "Tỷ lệ review xấu": "{:.1%}",
            "Review xấu tránh được": "{:,.0f}", "Giá trị đơn trễ (R$)": "{:,.0f}", "Giảm tỷ lệ review xấu": "{:.1%}",
        }),
        use_container_width=True, hide_index=True,
    )
    best = ranking.iloc[0]
    st.success(
        f"**Đề xuất (Implementation):** ưu tiên **{best[group_col]}** — tỷ lệ trễ {fmt_pct(best.late_rate)}, "
        f"loại bỏ giao trễ dự kiến tránh được ~{best.bad_reviews_avoided:,.0f} review xấu "
        f"(giảm {fmt_pct(best.bad_rate_reduction_pts)} tỷ lệ review xấu trong nhóm). "
        "Hành động gợi ý: đổi/thêm đơn vị vận chuyển cho khu vực này, hoặc nới ngày giao dự kiến cho sát thực tế."
    )


def scope_picker(key: str) -> tuple[pd.Series, str]:
    """Let the user restrict a scenario to one state / category; returns (mask, label)."""
    c1, c2 = st.columns(2)
    scope_type = c1.selectbox("Phạm vi áp dụng", list(SCOPES), key=f"{key}_type")
    col = SCOPES[scope_type]
    if col is None:
        return pd.Series(True, index=df.index), "toàn quốc"
    options = df[col].value_counts().index.tolist()  # most orders first
    value = c2.selectbox(scope_type.replace("Theo ", "").capitalize(), options, key=f"{key}_value")
    return df[col] == value, value


# ---------------------------------------------------------------- 3. What-if
with tab_whatif:
    st.markdown("Thay đổi **biến quyết định** và xem **biến kết quả** (tỷ lệ review xấu kỳ vọng) thay đổi thế nào.")
    scope, scope_label = scope_picker("wi")
    c1, c2 = st.columns(2)
    late_reduction = c1.slider("Giảm bao nhiêu % số đơn trễ", 0, 100, 30, step=5) / 100
    days_faster = c2.slider("Rút ngắn thời gian giao (ngày) cho mọi đơn", 0, 10, 0)

    res = whatif.evaluate_scenario(bundle, df, scope, late_reduction, days_faster)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số đơn trong phạm vi", f"{res['n_orders_scope']:,}")
    c2.metric("Tỷ lệ giao trễ", fmt_pct(res["late_rate_after"]),
              delta=f"{(res['late_rate_after'] - res['late_rate_before']) * 100:+.1f} điểm %", delta_color="inverse")
    c3.metric("Tỷ lệ review xấu kỳ vọng", fmt_pct(res["bad_rate_after_scope"]),
              delta=f"{(res['bad_rate_after_scope'] - res['bad_rate_before_scope']) * 100:+.1f} điểm %",
              delta_color="inverse")
    c4.metric("Review xấu tránh được", f"{res['bad_reviews_avoided']:,.0f}")
    st.caption(f"Phạm vi: {scope_label}. Tỷ lệ review xấu thực tế: {fmt_pct(res['actual_bad_rate_scope'])}; "
               f"mô hình ước lượng hiện tại: {fmt_pct(res['bad_rate_before_scope'])}. "
               f"Toàn quốc: {fmt_pct(res['bad_rate_before_all'])} → {fmt_pct(res['bad_rate_after_all'])}.")

    st.subheader("Sensitivity analysis")
    sens = whatif.sensitivity(bundle, df, scope)
    fig = px.line(sens, x="late_reduction", y="bad_rate", markers=True,
                  title=f"Tỷ lệ review xấu kỳ vọng theo mức giảm đơn trễ ({scope_label})",
                  labels={"late_reduction": "Mức giảm đơn trễ", "bad_rate": "Tỷ lệ review xấu kỳ vọng"})
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- 4. Goal seeking
with tab_goal:
    st.markdown("Đặt **mục tiêu** cho tỷ lệ review xấu; hệ thống tìm (duyệt từng 1%) "
                "**mức giảm đơn trễ tối thiểu** cần đạt.")
    scope, scope_label = scope_picker("gs")
    current = whatif.evaluate_scenario(bundle, df, scope)["bad_rate_before_scope"]
    target = st.number_input("Mục tiêu tỷ lệ review xấu (%)", min_value=0.0, max_value=100.0,
                             value=round(max(current * 100 - 1.5, 0), 1), step=0.5) / 100
    st.caption(f"Hiện tại ({scope_label}): {fmt_pct(current)}")
    result = whatif.goal_seek(bundle, df, scope, target)
    if result is None:
        best_case = whatif.evaluate_scenario(bundle, df, scope, late_reduction=1.0)
        st.error(f"Không đạt được mục tiêu chỉ bằng giảm giao trễ: kể cả khi 100% đơn đúng hạn, "
                 f"tỷ lệ review xấu kỳ vọng vẫn là {fmt_pct(best_case['bad_rate_after_scope'])}. "
                 "Cần thêm giải pháp khác (chất lượng sản phẩm, đóng gói, giao 1 lần thay vì nhiều lần…).")
    else:
        st.success(
            f"Cần giảm **{result['late_reduction']:.0%}** số đơn trễ ({scope_label}): tỷ lệ trễ "
            f"{fmt_pct(result['late_rate_before'])} → {fmt_pct(result['late_rate_after'])}, "
            f"tỷ lệ review xấu kỳ vọng {fmt_pct(result['bad_rate_before_scope'])} → "
            f"{fmt_pct(result['bad_rate_after_scope'])} (≈ {result['bad_reviews_avoided']:,.0f} review xấu tránh được)."
        )
