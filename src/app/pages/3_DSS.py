"""DSS page: decision tree model, what-if, sensitivity, goal seeking, ranking and budget optimisation.

Decision problem: with a limited budget for improving delivery, which states
should be prioritised to avoid the most 1-2 star reviews, and does that
priority still hold when the cost assumptions change?

Layout follows Simon's decision phases: Design (model) -> Choice (ranking,
what-if, goal seeking, budget optimisation) -> Implementation (recommendation).
"""
import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import engine, fmt_pct
from dss import optimizer, whatif
from dss.train_model import MODEL_DIR, load_dataset, load_model

st.set_page_config(page_title="DSS", layout="wide")
st.title("Hệ hỗ trợ quyết định: ưu tiên cải thiện giao hàng ở bang nào?")


@st.cache_resource(show_spinner="Đang nạp mô hình…")
def get_model():
    return load_model(engine())


@st.cache_data(show_spinner="Đang đọc dữ liệu từ kho…")
def get_data() -> pd.DataFrame:
    return load_dataset(engine())


@st.cache_data(show_spinner=False)
def get_ranking(_bundle, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    return whatif.priority_ranking(_bundle, df, group_col)


@st.cache_data(show_spinner=False)
def get_experiments() -> dict | None:
    path = MODEL_DIR / "experiments.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data(show_spinner=False)
def get_options() -> pd.DataFrame:
    return optimizer.load_options()


@st.cache_data(show_spinner="Đang chạy các kịch bản giả định…")
def get_robustness(options: pd.DataFrame, surcharge: float):
    return optimizer.robustness(options, surcharge)


bundle, df = get_model(), get_data()
metrics = bundle["metrics"]
SCOPES = {"Toàn quốc": None, "Theo bang": "customer_state", "Theo danh mục": "category"}

bad = df[df["is_bad_review"] == 1]
st.markdown(
    "**Câu hỏi quyết định:** nếu Olist đầu tư cải thiện giao hàng với ngân sách có hạn, nên ưu tiên "
    "**những bang nào** để giảm review 1–2★ nhiều nhất, và thứ tự ưu tiên đó có còn đúng khi giả định về chi phí "
    "thay đổi không?"
)
st.caption(
    f"Phạm vi: trong {len(bad):,} review xấu, {int(bad['is_late'].sum()):,} "
    f"({bad['is_late'].mean():.0%}) thuộc đơn giao trễ. DSS này chỉ xử lý phần do giao trễ; "
    "phần còn lại (chất lượng sản phẩm, đóng gói…) nằm ngoài phạm vi."
)

tab_model, tab_rank, tab_whatif, tab_goal, tab_opt = st.tabs(
    ["1. Mô hình (Design)", "2. Xếp hạng ưu tiên", "3. What-if & Sensitivity", "4. Goal seeking",
     "5. Tối ưu ngân sách (Choice)"]
)

# ---------------------------------------------------------------- 1. Model
with tab_model:
    st.markdown(
        "**Cây quyết định** (tiêu chí *entropy / information gain*; scikit-learn cài đặt theo CART, tách nhị phân) "
        "dự đoán đơn hàng có bị "
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

    experiments = get_experiments()
    if experiments:
        st.subheader("Thực nghiệm chọn tham số")
        st.markdown(
            f"So sánh {len(experiments['rows'])} cặp tham số bằng **cross-validation 5-fold trên tập train** "
            "(tập test không dùng ở đây). Hai nhóm chỉ số vì cây được dùng theo hai cách: phân loại "
            "(F1…) và **mô hình rủi ro** (tỷ lệ của lá làm xác suất, đo bằng Brier / log-loss: càng thấp càng tốt; "
            "AUC: càng cao càng tốt). DSS dùng cách thứ hai."
        )
        exp = pd.DataFrame(experiments["rows"])
        st.dataframe(
            exp[["max_depth", "min_samples_leaf", "n_leaves", "cv_f1", "cv_recall", "cv_precision",
                 "cv_brier", "cv_log_loss", "cv_auc", "chosen"]]
            .rename(columns={"n_leaves": "Số lá", "chosen": "Đang dùng"})
            .style.format({c: "{:.4f}" for c in ["cv_f1", "cv_recall", "cv_precision", "cv_brier", "cv_log_loss",
                                                 "cv_auc"]})
            .highlight_max(subset=["cv_f1", "cv_auc"], color="#c8e6c9")
            .highlight_min(subset=["cv_brier", "cv_log_loss"], color="#c8e6c9"),
            use_container_width=True, hide_index=True,
        )
        st.caption("Depth 3 có F1 cao nhất nhưng xác suất kém nhất (AUC thấp nhất). Depth 4 cho xác suất gần bằng "
                   "depth 5–6 mà chỉ có khoảng 15 lá, nên luật IF-THEN vẫn đọc được. min_samples_leaf ít ảnh hưởng; "
                   "200 giữ mỗi lá đủ lớn để tỷ lệ ổn định.")

    lc = metrics.get("leaf_check")
    if lc:
        st.subheader("Kiểm tra mô hình rủi ro trên tập test")
        st.markdown(
            f"Tỷ lệ review xấu của từng lá học trên tập train, đem áp lên **{lc['n_test']:,} đơn tập test** chưa thấy: "
            f"mô hình dự kiến **{lc['expected_bad_test']:,.0f}** review xấu, thực tế **{lc['actual_bad_test']:,}**. "
            f"Chênh lệch trung bình (có trọng số) giữa tỷ lệ train và test: "
            f"**{lc['weighted_mean_abs_diff_pts'] * 100:.1f} điểm %**."
        )
        leaves = pd.DataFrame(lc["leaves"])
        fig = go.Figure()
        fig.add_bar(x=leaves["leaf"].astype(str), y=leaves["rate_train"], name="Train")
        fig.add_bar(x=leaves["leaf"].astype(str), y=leaves["rate_test"], name="Test")
        fig.update_layout(barmode="group", title="Tỷ lệ review xấu theo lá: train so với test",
                          xaxis_title="Lá (sắp theo rủi ro giảm dần)", yaxis_title="Tỷ lệ review xấu",
                          yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
        worst = leaves.dropna(subset=["rate_test"]).assign(
            diff=lambda d: (d["rate_train"] - d["rate_test"]).abs()).nlargest(1, "diff").iloc[0]
        st.caption(f"Lá lệch nhiều nhất: {worst['rate_train']:.1%} trên train, {worst['rate_test']:.1%} trên test "
                   f"(chỉ {int(worst['n_test'])} đơn test). Lá nhỏ dao động nhiều hơn; các lá lớn gần như trùng nhau.")

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
    st.caption("Xếp hạng này theo **tổng** số review xấu tránh được và chưa tính chi phí, nên bang lớn (nhiều đơn trễ) "
               "đứng đầu. Khi ngân sách có hạn, điều cần so là review xấu tránh được **trên mỗi BRL**: thứ tự có thể "
               "khác, xem tab 5.")


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

# ---------------------------------------------------------------- 5. Budget optimisation
LEVEL_FMT = "{:.0%}"
TIER_LABELS = {"flat": "Phẳng (1 / 1 / 1 / 1)", "default": "Mặc định (1 / 1,2 / 1,5 / 2)",
               "steep": "Dốc (1 / 1,5 / 2,25 / 3,5)"}
COST_LABELS = {"freight": "Theo phí ship thật của bang", "uniform": "Đồng đều (mọi đơn trễ cùng giá)"}

with tab_opt:
    options = get_options()
    surcharge0, tier0 = optimizer.load_cost_assumptions()
    base = metrics["optimizer_baseline"]

    st.info(
        "**Cái gì là dữ liệu, cái gì là giả định.** "
        "Lợi ích (review xấu tránh được) do cây quyết định ước lượng, giả định giao trễ là nguyên nhân gây review xấu. "
        "Chi phí (BRL) = phí ship **thật** của các đơn trễ được sửa × phụ phí × hệ số theo mức. "
        "Phụ phí và hệ số theo mức là **giả định** (Olist không có dữ liệu chi phí can thiệp). "
        "Phí ship chỉ phản ánh logistics ở bang đó đắt hay rẻ; trả phí ship cao hơn **không** làm giao nhanh hơn "
        "(đã kiểm tra, xem `config/README.md`)."
    )

    # ---- robust conclusion first
    st.subheader("Kết luận không phụ thuộc giả định")
    runs, summary = get_robustness(options, surcharge0)
    budgets = list(optimizer.ROBUST_BUDGETS)
    n_sets = len(optimizer.COST_MODELS) * len(optimizer.TIER_SCENARIOS)
    st.markdown(
        f"Giải bài toán tối ưu với **{n_sets} bộ giả định** (2 cách tính chi phí × 3 kịch bản hệ số theo mức) ở "
        f"**{len(budgets)} mức ngân sách** ({', '.join(f'{b:,}' for b in budgets)} BRL), tổng "
        f"{n_sets * len(budgets)} kịch bản. Một bang thuộc **ưu tiên k** nếu ở mức ngân sách thứ k nó đã được chọn "
        f"trong ít nhất {int(round(2 / 3 * n_sets))}/{n_sets} bộ giả định."
    )
    groups = summary.dropna(subset=["priority"]).groupby("priority")["state"].apply(list)
    for prio, states in groups.items():
        st.markdown(f"- **Ưu tiên {int(prio)}** (từ {budgets[int(prio) - 1]:,} BRL): {', '.join(states)}")
    never = summary[summary["priority"].isna()]["state"].tolist()
    if never:
        st.markdown(f"- **Ít khi được chọn:** {', '.join(never)}")

    table = summary.copy()
    table["Mức giảm đơn trễ"] = [
        "—" if pd.isna(lo) else (LEVEL_FMT.format(lo) if lo == hi else f"{lo:.0%}–{hi:.0%}")
        for lo, hi in zip(table["min_level"], table["max_level"])
    ]
    show = {"state": "Bang", "region": "Vùng", "priority": "Ưu tiên",
            **{f"n_at_{b}": f"Được chọn ở {b:,} BRL (/{n_sets})" for b in budgets},
            "Mức giảm đơn trễ": "Mức giảm đơn trễ (khi được chọn)"}
    st.dataframe(table[list(show)].rename(columns=show).style.format({"Ưu tiên": "{:.0f}"}, na_rep="—"),
                 use_container_width=True, hide_index=True)
    st.caption("Thứ tự ưu tiên vững qua các giả định; **mức giảm cụ thể** ở từng bang thì phụ thuộc giả định chi phí, "
               "nên chỉ ghi khoảng. Trong thực tế, người quản lý thay giả định bằng báo giá thật của hãng vận chuyển.")

    # ---- one detailed plan under chosen assumptions
    st.subheader("Phương án chi tiết với một bộ giả định")
    c1, c2, c3, c4 = st.columns(4)
    budget = c1.number_input("Ngân sách (BRL)", min_value=0, max_value=300_000, value=40_000, step=5_000)
    k = c2.number_input("Số bang tối đa (0 = không giới hạn)", min_value=0, max_value=len(options["state"].unique()),
                        value=0, step=1)
    tier_name = c3.selectbox("Hệ số theo mức", list(TIER_LABELS), index=1, format_func=TIER_LABELS.get)
    cost_name = c4.selectbox("Cách tính chi phí", list(COST_LABELS), format_func=COST_LABELS.get)
    max_states = None if k == 0 else int(k)
    tier = tier0 if tier_name == "default" else optimizer.TIER_SCENARIOS[tier_name]
    costed = optimizer.COST_MODELS[cost_name](options, surcharge0, tier)

    plan, base_plan = optimizer.solve(costed, budget, max_states), optimizer.greedy(costed, budget, max_states)
    st.success("**Khuyến nghị (Implementation):** "
               + optimizer.recommend(plan, budget, base["n_reviews"], base["expected_bad_before"]))

    c1, c2, c3 = st.columns(3)
    c1.metric("Review xấu tránh được (tối ưu)", f"{plan.benefit:,.0f}")
    gap = 0.0 if plan.benefit == 0 else (plan.benefit - base_plan.benefit) / plan.benefit
    c2.metric("Greedy (heuristic)", f"{base_plan.benefit:,.0f}", delta=f"-{gap:.1%} so với tối ưu",
              delta_color="off")
    c3.metric("Số bang được chọn", f"{len(plan.selected)}", help=f"Giải trong {plan.seconds:.2f} giây")

    sel = plan.selected.rename(columns={
        "state": "Bang", "region": "Vùng", "level": "Mức giảm đơn trễ", "late_fixed": "Số đơn trễ được sửa",
        "freight_fixed": "Phí ship của các đơn đó (BRL)", "cost": "Chi phí (BRL)", "benefit": "Review xấu tránh được"})
    st.dataframe(sel.style.format({"Mức giảm đơn trễ": "{:.0%}", "Số đơn trễ được sửa": "{:,}",
                                   "Phí ship của các đơn đó (BRL)": "{:,.0f}", "Chi phí (BRL)": "{:,.0f}",
                                   "Review xấu tránh được": "{:,.1f}"}),
                 use_container_width=True, hide_index=True)
    st.download_button("Tải phương án (CSV)", plan.selected.to_csv(index=False).encode("utf-8"),
                       file_name=f"phuong_an_{budget}.csv", mime="text/csv")

    st.subheader("Đường cong ngân sách – lợi ích")
    full_cost = costed[costed["level"] == costed["level"].max()]["cost"].sum()
    grid = [round(x, -3) for x in np.linspace(0, full_cost, 17)]
    fr = optimizer.frontier(costed, grid, max_states)
    fig = go.Figure()
    fig.add_scatter(x=fr["budget"], y=fr["optimal_benefit"], mode="lines+markers", name="Tối ưu (MILP)")
    fig.add_scatter(x=fr["budget"], y=fr["greedy_benefit"], mode="lines+markers", name="Greedy",
                    line={"dash": "dash"})
    fig.add_vline(x=budget, line_dash="dot", annotation_text="Ngân sách đang chọn")
    fig.update_layout(xaxis_title="Ngân sách (BRL)", yaxis_title="Review xấu tránh được")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Đường cong cong dần: những đồng đầu tiên tránh được nhiều review xấu nhất (lợi ích cận biên giảm dần). "
               "Greedy gần tối ưu khi không giới hạn số bang, kém rõ hơn khi giới hạn số bang.")

    st.subheader("Độ nhạy theo hệ số theo mức")
    sens = optimizer.tier_sensitivity(options, budget, surcharge0, max_states=max_states,
                                      attach=optimizer.COST_MODELS[cost_name])
    st.dataframe(sens.assign(scenario=sens["scenario"].map(TIER_LABELS)).rename(columns={
        "scenario": "Kịch bản", "tier": "Hệ số", "benefit": "Review xấu tránh được", "cost": "Chi phí (BRL)",
        "n_states": "Số bang", "late_fixed": "Đơn trễ được sửa", "plan": "Phương án"})
        .style.format({"Review xấu tránh được": "{:,.0f}", "Chi phí (BRL)": "{:,.0f}", "Đơn trễ được sửa": "{:,}"}),
        use_container_width=True, hide_index=True)
    st.caption("Chi phí sửa sâu tăng nhanh (dốc) → nên dàn mỏng ra nhiều bang; không tăng (phẳng) → dồn vào ít bang.")
