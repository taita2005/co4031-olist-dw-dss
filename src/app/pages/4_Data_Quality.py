"""Data quality and metadata: can the numbers on the other pages be trusted?

Reads only the metadata schema (meta.etl_log, meta.check_result) and
models/metrics.json. Nothing here changes data.
"""
import json

import pandas as pd
import streamlit as st

from common import run_query
from dss.train_model import MODEL_DIR

st.set_page_config(page_title="Chất lượng dữ liệu", layout="wide")
st.title("Chất lượng dữ liệu và metadata")
st.caption(
    "Mỗi lần chạy `run_etl.py` ghi số dòng từng bước vào `meta.etl_log` và kết quả kiểm tra vào "
    "`meta.check_result`. Hai bảng này nằm ngoài schema `dw` nên không bị xóa khi nạp lại kho."
)

CATEGORY_LABEL = {
    "source": "Nguồn CSV (trước khi nạp)",
    "grain": "Grain (không trùng dòng)",
    "reconciliation": "Đối chiếu staging ↔ dw",
    "domain": "Miền giá trị và quy tắc nghiệp vụ",
    "coverage": "Độ phủ (dim_date, mapping)",
    "aggregate": "Materialized view ↔ fact",
}

runs = run_query("""
    SELECT r.run_id,
           COUNT(*)                         AS n_checks,
           COUNT(*) FILTER (WHERE NOT passed) AS n_failed,
           (SELECT note FROM meta.etl_log l WHERE l.run_id = r.run_id AND l.step = 'run' LIMIT 1) AS duration,
           (SELECT loaded_rows FROM meta.etl_log l
             WHERE l.run_id = r.run_id AND l.table_name = 'dw.fact_sales')   AS fact_sales_rows,
           (SELECT loaded_rows FROM meta.etl_log l
             WHERE l.run_id = r.run_id AND l.table_name = 'dw.fact_delivery') AS fact_delivery_rows
    FROM meta.check_result r
    WHERE r.run_id > '2000-01-01'          -- 1999 marker runs come from rolled-back tests
    GROUP BY r.run_id
    ORDER BY r.run_id DESC
""")
if runs.empty:
    st.warning("Chưa có lần chạy ETL nào ghi kết quả kiểm tra. Chạy `python src/etl/run_etl.py`.")
    st.stop()

latest = runs.iloc[0]
run_id = latest.run_id

# ---------------------------------------------------------------- Latest run
c1, c2, c3, c4 = st.columns(4)
c1.metric("Lần ETL gần nhất", pd.Timestamp(run_id).strftime("%d/%m/%Y %H:%M"))
c2.metric("Thời gian chạy", latest.duration or "không ghi")
c3.metric("Kiểm tra đạt", f"{latest.n_checks - latest.n_failed} / {latest.n_checks}")
c4.metric("Số lần chạy đã lưu", f"{len(runs)}")
if latest.n_failed:
    st.error(f"{latest.n_failed} kiểm tra KHÔNG đạt ở lần chạy này. Số liệu trên các trang khác có thể sai.")
else:
    st.success("Mọi kiểm tra đều đạt: dữ liệu trong kho khớp với file nguồn.")

checks = run_query("""
    SELECT category, check_name, expected, actual, passed, note
    FROM meta.check_result WHERE run_id = :run ORDER BY check_id
""", {"run": run_id})

st.subheader("Kết quả kiểm tra theo nhóm")
st.caption(
    "Giá trị **kỳ vọng** được tính lại trực tiếp từ staging (hoặc từ file CSV với nhóm *Nguồn*), không dùng lại "
    "logic transform, nên một lỗi trong `03_transform_load.sql` sẽ hiện ra thành chênh lệch."
)
summary = (checks.assign(group=checks["category"].map(CATEGORY_LABEL).fillna(checks["category"]))
           .groupby("group", sort=False)
           .agg(n=("passed", "size"), passed=("passed", "sum"))
           .reindex([g for g in CATEGORY_LABEL.values() if g in set(checks["category"].map(CATEGORY_LABEL))]))
cols = st.columns(len(summary))
for col, (group, row) in zip(cols, summary.iterrows()):
    col.metric(group, f"{int(row.passed)} / {int(row.n)}",
               delta=None if row.passed == row.n else f"{int(row.n - row.passed)} lỗi", delta_color="inverse")

only_failed = st.toggle("Chỉ hiện kiểm tra không đạt", value=False)
view = checks[~checks["passed"]] if only_failed else checks
view = view.assign(
    category=view["category"].map(CATEGORY_LABEL).fillna(view["category"]),
    passed=view["passed"].map({True: "✅ đạt", False: "❌ lỗi"}),
)
st.dataframe(
    view.rename(columns={"category": "Nhóm", "check_name": "Kiểm tra", "expected": "Kỳ vọng",
                         "actual": "Thực tế", "passed": "Kết quả", "note": "Ghi chú"}),
    use_container_width=True, hide_index=True,
    column_config={"Kỳ vọng": st.column_config.NumberColumn(format="%.2f"),
                   "Thực tế": st.column_config.NumberColumn(format="%.2f")},
)

# ---------------------------------------------------------------- Lineage: CSV -> staging -> dw
st.subheader("Số dòng qua từng bước: CSV → staging → dw")
log = run_query("""
    SELECT step, table_name, source_rows, loaded_rows, note
    FROM meta.etl_log WHERE run_id = :run AND step IN ('extract', 'load') ORDER BY log_id
""", {"run": run_id})
log["diff"] = log["loaded_rows"] - log["source_rows"]
st.dataframe(
    log.rename(columns={"step": "Bước", "table_name": "Bảng", "source_rows": "Dòng nguồn",
                        "loaded_rows": "Dòng đã nạp", "diff": "Chênh lệch", "note": "Lý do chênh lệch"}),
    use_container_width=True, hide_index=True,
)
st.caption(
    "Bước *extract*: nguồn là file CSV, phải khớp tuyệt đối. Bước *load*: nguồn là bảng staging tương ứng; "
    "chênh lệch là do quy tắc nghiệp vụ (ví dụ `dim_customer` gộp theo `customer_unique_id`, `fact_delivery` "
    "chỉ giữ đơn đã giao có ngày giao). Mỗi chênh lệch đó đều có một kiểm tra *đối chiếu* tính lại từ staging."
)

# ---------------------------------------------------------------- History
st.subheader("Lịch sử các lần chạy")
hist = runs.assign(
    run_id=runs["run_id"].dt.strftime("%d/%m/%Y %H:%M:%S"),
    same=(runs[["fact_sales_rows", "fact_delivery_rows"]]
          .eq(runs[["fact_sales_rows", "fact_delivery_rows"]].shift(-1)).all(axis=1)
          .map({True: "giống", False: "KHÁC"})),
)
hist.loc[hist.index[-1], "same"] = "—"   # oldest run: nothing to compare with
st.dataframe(
    hist.rename(columns={"run_id": "Lần chạy", "n_checks": "Số kiểm tra", "n_failed": "Không đạt",
                         "duration": "Thời gian", "fact_sales_rows": "fact_sales", "fact_delivery_rows": "fact_delivery",
                         "same": "Giống lần trước"}),
    use_container_width=True, hide_index=True,
)
st.caption("Nạp lại toàn bộ từ cùng file nguồn phải cho cùng kết quả (idempotent); "
           "`tests/test_etl_checks.py` so sánh hai lần chạy gần nhất.")

# ---------------------------------------------------------------- Rules
st.subheader("Quy tắc làm sạch và nghiệp vụ trong ETL")
RULES = pd.DataFrame([
    ("Nguồn", "Hợp đồng CSV: đúng header; khóa không trống, không trùng; số, ngày giờ, điểm, mã bang, zip đúng "
     "định dạng", "src/etl/contracts.py", "<file>: vi phạm hợp đồng; rows: <file> = staging.<bảng>"),
    ("Cleansing", "Danh mục sản phẩm trống → 'unknown'", "03 (dim_product)", "rows: staging.products = dim_product"),
    ("Cleansing", "Thêm 2 danh mục thiếu trong bảng dịch (pc_gamer, portateis_cozinha_…)", "03 (ref_category)",
     "products with a source category but no English name"),
    ("Cleansing", "Một đơn có nhiều review → giữ câu trả lời mới nhất", "03 (latest_review)",
     "fact_delivery: duplicate order_id; delivered orders with a review = …"),
    ("Mapping", "Tên danh mục tiếng Bồ Đào Nha → tiếng Anh", "03 (dim_product)",
     "products with a source category but no English name"),
    ("Mapping", "Bang (UF) → vùng của Brazil", "03 (ref_state_region)", "customers/sellers with a state but no region"),
    ("Business rule", "Khách hàng thật = customer_unique_id (customer_id chỉ là mã theo đơn)", "03 (dim_customer)",
     "dim_customer: duplicate customer_unique_id; rows: distinct customer_unique_id = dim_customer"),
    ("Business rule", "fact_delivery chỉ gồm đơn 'delivered' có ngày giao", "03 (fact_delivery)",
     "rows: delivered orders with a delivery date = fact_delivery"),
    ("Business rule", "Giao trễ = ngày giao > ngày dự kiến; review xấu = điểm ≤ 2", "03 (fact_delivery)",
     "late orders: staging = SUM(is_late); is_late / is_bad_review inconsistent …"),
    ("Business rule", "Doanh thu không tính đơn canceled / unavailable", "04_olap_views.sql",
     "mv_sales_cube grand total = …; SUM(mv_monthly_kpi.revenue) = …"),
    ("Attribute construction", "Số ngày giao, số ngày dự kiến, số ngày trễ", "03 (fact_delivery)",
     "delay_days <> delivery_days - estimated_days; negative delivery_days …"),
    ("Attribute construction", "Thể tích = dài × cao × rộng", "03 (dim_product)", "chưa có kiểm tra riêng"),
], columns=["Loại", "Quy tắc", "Ở đâu (03 = 03_transform_load.sql)", "Kiểm tra bảo vệ quy tắc này"])
st.dataframe(RULES, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Model lineage
st.subheader("Mô hình DSS được train từ lần ETL nào?")
metrics_path = MODEL_DIR / "metrics.json"
if not metrics_path.exists():
    st.info("Chưa có mô hình. Chạy `python src/dss/train_model.py`.")
else:
    m = json.loads(metrics_path.read_text(encoding="utf-8"))
    model_run = m.get("etl_run_id")
    latest_load = run_query("SELECT MAX(run_id) AS r FROM meta.etl_log WHERE step = 'load'")["r"].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Train lúc", m.get("trained_at", "không ghi"))
    c2.metric("Từ lần ETL", pd.Timestamp(model_run).strftime("%d/%m/%Y %H:%M") if model_run else "không ghi")
    c3.metric("Số đơn dùng để train + test", f"{m['n_rows']:,}" if "n_rows" in m else "không ghi")
    if model_run is None:
        st.warning("metrics.json chưa có `etl_run_id` (mô hình cũ). Chạy lại `python src/dss/train_model.py`.")
    elif pd.Timestamp(model_run) != pd.Timestamp(latest_load):
        st.warning("Kho đã được nạp lại sau khi train. Dữ liệu nguồn giống nhau thì kết quả không đổi, "
                   "nhưng trước khi chốt số liệu hãy chạy lại `python src/dss/train_model.py`.")
    else:
        st.success("Mô hình được train trên đúng dữ liệu đang có trong kho.")
    st.caption(f"Tham số cây: {m.get('params')}. Mọi con số trong báo cáo phải truy ngược được về `etl_run_id` này.")
