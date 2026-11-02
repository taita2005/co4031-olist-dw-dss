# Proposal BTL CO4031 — DW & DSS cho giao hàng và sự hài lòng khách hàng (Olist)

## Context
Nhóm 3 người cần một đề tài BTL đáp ứng đủ 6 yêu cầu trong `CO4031_Assignment_HK261.pdf` (phân tích → thiết kế DW + ETL → backend/OLAP + frontend → DSS → đánh giá → thuyết trình), dùng bộ Olist trong `data/`, **đơn giản để kịp deadline 15/11/2026** và **bám sát thuật ngữ trong slide** để dễ trình bày với thầy. Stack: **Python + PostgreSQL + Streamlit**.

Ghi chú nguồn: các khái niệm đánh dấu *(slide)* có trong lecture; *(Kimball)* lấy từ giáo trình tham khảo [2] (slide không dạy nhưng là best practice — nói rõ khi trình bày).

> **Trạng thái:** đã hiện thực xong (02/11/2026). Cách chạy và bản đồ code: xem [README.md](../README.md).

### Thay đổi so với bản đề xuất ban đầu
| # | Bản đầu | Bản hiện thực | Lý do |
|---|---|---|---|
| 1 | PostgreSQL chạy bằng Docker, `requirements.txt` | Môi trường **micromamba cục bộ** trong project (`environment.yml`, `scripts/`) chứa Python 3.12 + PostgreSQL 16 | Máy không có Docker; không được đụng môi trường hệ thống |
| 2 | Thư mục `dataset/` | Đổi tên thành `data/` | Khớp cấu trúc nộp bài |
| 3 | Extract 9 CSV | Extract **8 CSV** (bỏ geolocation) | Geolocation 1M dòng, không dùng cho bài toán |
| 4 | `fact_delivery` chỉ có `seller_key` của item chính | Thêm **`product_key`** (item chính) và measure **`n_sellers`** | Cần để xếp hạng theo danh mục; `n_sellers` là yếu tố rủi ro mới phát hiện |
| 5 | Bảng log `dw.etl_log` | **`meta.etl_log`** (schema riêng) | `dw` bị xoá mỗi lần full refresh; metadata phải giữ lịch sử |
| 6 | Partition `fact_sales` theo năm (tuỳ chọn) | **Đã làm** (3 partition 2016/2017/2018) | Minh hoạ "partitioning by time" |
| 7 | Cây quyết định `max_depth=4` | Thêm `min_samples_leaf=200`, `class_weight="balanced"`, feature `n_sellers` | Tránh lá quá nhỏ; lớp review xấu là thiểu số |
| 8 | Xác suất lấy từ mô hình (chưa nói rõ) | Xác suất = **tỷ lệ review xấu thực tế của từng lá** (`leaf_rate`) | `class_weight` làm lệch `predict_proba`; tỷ lệ theo lá dễ giải thích |
| 9 | Xuất cây dạng text | Xuất **luật IF-THEN kèm P(review xấu) và số đơn** cho từng lá | Dễ trình bày |
| 10 | Goal seeking bằng tìm kiếm nhị phân | **Complete enumeration** từng 1% (0–100%) | Đơn giản, đúng thuật ngữ "blind search / complete enumeration" trong slide Ch7 |
| 11 | OLAP trên 1 fact | Trang OLAP **chọn được 1 trong 2 fact** dùng chung dimension; phân biệt measure cộng dồn / không cộng dồn | Minh hoạ fact constellation + additivity |
| 12 | 3 người chia nhau code | **1 người code, 2 người review**; cả 3 vẫn thuyết trình | Code ít file, chia 3 không hiệu quả |

---

## 1. Đề tài & bài toán quyết định (Yêu cầu 1 — Phân tích)

**Tên đề tài:** *Kho dữ liệu phân tích bán hàng – giao hàng và hệ hỗ trợ quyết định cải thiện sự hài lòng khách hàng cho sàn TMĐT Olist.*

**Vấn đề nghiệp vụ:** Doanh thu Olist tăng nhưng một tỷ lệ đáng kể đơn hàng bị đánh giá 1–2 sao, nguyên nhân chính nghi ngờ là giao hàng trễ. Ban quản lý vận hành cần biết **ưu tiên cải thiện logistics ở đâu (bang / danh mục / người bán)** và **cải thiện bao nhiêu thì đạt mục tiêu hài lòng**.

**Người ra quyết định:** Quản lý vận hành / logistics của sàn.
**Loại quyết định:** semi-structured *(slide Ch6: DSS hỗ trợ semi-structured)*.

**Câu hỏi phân tích (phần DW/OLAP trả lời):**
- Doanh thu, số đơn theo thời gian / vùng / danh mục?
- Tỷ lệ giao trễ, thời gian giao trung bình theo bang, theo danh mục?
- Điểm review trung bình thay đổi thế nào khi giao trễ?

**Câu hỏi quyết định (phần DSS trả lời):**
- Yếu tố nào dẫn đến review xấu? (mô hình cây quyết định)
- *What-if:* nếu giảm X% đơn trễ ở bang Y thì tỷ lệ review xấu giảm bao nhiêu?
- *Goal seeking:* cần giảm tỷ lệ trễ bao nhiêu để tỷ lệ review xấu ≤ mục tiêu T%?
- Xếp hạng bang/danh mục nên ưu tiên đầu tư.

**Khung trình bày theo quá trình ra quyết định của Simon** *(slide Ch5-cont)*:
| Pha | Trong project |
|---|---|
| Intelligence | Trang Home / OLAP / Delivery phát hiện vấn đề: bang/danh mục có tỷ lệ trễ & review xấu cao |
| Design | Tab "Mô hình": cây quyết định dự đoán review xấu + mô hình what-if |
| Choice | Tab "Xếp hạng ưu tiên", "What-if", "Goal seeking" |
| Implementation | Khung đề xuất hành động tự sinh trên trang DSS (đổi đơn vị vận chuyển, nới ngày giao dự kiến…) |
| Evaluation | Accuracy, precision/recall/F1, confusion matrix; hạn chế |

---

## 2. Thiết kế kho dữ liệu (Yêu cầu 2)

### 2.1 Kiến trúc — Three-Tier *(slide Ch2/Ch3)*
```
Bottom tier: 8 file CSV Olist ──Extract (COPY)──▶ schema `staging` (PostgreSQL, bảng thô, toàn TEXT)
                                     │ Transform (cleansing, mapping, business rules) — SQL
Middle tier: schema `dw` (DDS: fact constellation) + materialized views (ROLAP)
             schema `meta` (etl_log — metadata)
Top tier:    Streamlit — Home (KPI), OLAP, Delivery, DSS
```
- Hướng tiếp cận **Bottom-Up (Kimball)** *(slide Ch3)*: xây 1 data mart cho chủ đề Sales & Delivery.
- OLAP server kiểu **ROLAP** *(slide Ch3)*: lưu quan hệ trên PostgreSQL, trang OLAP sinh `GROUP BY` động; tổng hợp sẵn bằng materialized views (`mv_monthly_kpi`, `mv_sales_cube` dùng `GROUP BY CUBE`, `mv_delivery_by_state`).
- 4 đặc tính Inmon *(slide Ch1)*: subject-oriented (bán hàng–giao hàng), integrated (gộp 8 nguồn, chuẩn hoá mã), time-variant (dim_date, dữ liệu 2016–2018), non-volatile (chỉ load, không update).

### 2.2 Schema — Fact Constellation 2 bảng fact dùng chung dimension
Mô phỏng ví dụ *"sales and shipping data warehouse"* trong slide Ch3.

**Dimensions** (surrogate key kiểu int — *Kimball*):
| Bảng | Thuộc tính chính | Hierarchy *(slide Ch2)* | Số dòng |
|---|---|---|---|
| `dim_date` | date_key (yyyymmdd), day, month, quarter, year, year_month, weekday, is_weekend | year > quarter > month > day | 1,096 |
| `dim_customer` | customer_key, customer_unique_id, zip, city, state, region | region > state > city | 96,096 |
| `dim_seller` | seller_key, seller_id, zip, city, state, region | region > state > city | 3,095 |
| `dim_product` | product_key, product_id, category_pt, category_en, photos_qty, weight_g, volume_cm3 | category > product | 32,951 |

(`region` = 5 vùng Brazil North / Northeast / Central-West / Southeast / South, ánh xạ từ state — attribute construction.)

**Fact 1 — `fact_sales`** — grain: **1 dòng = 1 sản phẩm trong 1 đơn hàng** (112,650 dòng), partition theo năm mua
- FK: purchase_date_key, customer_key, seller_key, product_key
- Degenerate: order_id, order_item_id, order_status
- Measures (additive): price, freight_value, total_value (= price + freight)

**Fact 2 — `fact_delivery`** — grain: **1 dòng = 1 đơn hàng đã giao** (96,470 dòng)
- FK: purchase_date_key, delivered_date_key, customer_key, seller_key, product_key (seller/product của item chính = item giá cao nhất)
- Measures: n_items, n_sellers, order_value, freight_total, delivery_days, estimated_days, delay_days, is_late (0/1), review_score, is_bad_review (score ≤ 2)

Lý do 2 fact (**granularity** — *slide Ch2-cont*): review và ngày giao thuộc về cả đơn hàng, không thuộc từng item; gộp chung vào 1 fact sẽ gây đếm trùng.

---

## 3. ETL (Yêu cầu 2 + 3)
Python (psycopg2/SQLAlchemy) điều phối + SQL thực hiện; chạy 1 lệnh `python src/etl/run_etl.py` (~5 giây).

1. **Extract:** `COPY` 8 CSV vào schema `staging` y nguyên, mọi cột kiểu TEXT (data staging area — *slide Ch1*). File dịch danh mục có BOM → đọc `utf-8-sig`; review có xuống dòng trong comment → dùng CSV parser thật.
2. **Transform** *(slide Ch2: cleansing / mapping / business rules)* — toàn bộ trong `03_transform_load.sql`:
   - Cleansing: đơn có nhiều review → lấy review trả lời gần nhất; 610 sản phẩm thiếu category → `unknown`; 2 category thiếu bản dịch → bổ sung tay; zip giữ dạng text.
   - Mapping: dịch category PT→EN; timestamp → date_key; state → region.
   - Business rules: khách hàng thật = `customer_unique_id`; `fact_delivery` chỉ lấy đơn `delivered` có ngày giao; is_late = giao thực tế > ngày dự kiến; bad review = score ≤ 2.
   - Attribute construction *(slide Ch2-cont)*: delivery_days, estimated_days, delay_days, volume_cm3, region.
3. **Load:** full refresh vào schema `dw` (incremental load là hướng phát triển).
4. **Metadata** *(slide Ch2-cont: "history of extracts")*: `meta.etl_log` ghi mỗi lần chạy: bảng, số dòng nguồn → số dòng nạp, ghi chú (vd. "deduplicated to customer_unique_id").
5. Index theo các FK; partition `fact_sales` theo năm — *slide Ch1: partitioning by time*.

---

## 4. OLAP & Dashboard (Yêu cầu 3 — frontend)
Streamlit nhiều trang, truy vấn trực tiếp PostgreSQL:

1. **Home (KPI):** doanh thu, số đơn, giá trị TB/đơn, tỷ lệ giao trễ, điểm review TB, tỷ lệ review xấu; biểu đồ theo tháng; bảng metadata ETL.
2. **OLAP Explorer** — đủ 5 phép toán *(slide Ch3)*:
   - Chọn fact (`fact_sales` / `fact_delivery`) và measure; cả 2 fact dùng chung dimension.
   - Roll-up / Drill-down: nút bấm đổi cấp (Năm ↔ Quý ↔ Tháng, Vùng ↔ Bang ↔ Thành phố).
   - Slice: cố định năm. Dice: lọc nhiều bang + nhiều danh mục.
   - Pivot: nút đổi chiều hàng ↔ cột; bảng pivot + heatmap.
   - Hiện câu SQL được sinh ra; chỉ hiện dòng tổng cho measure cộng dồn được (SUM/COUNT), không cho COUNT DISTINCT / AVG / tỷ lệ.
   - Xem khối tổng hợp sẵn `mv_sales_cube` (GROUP BY CUBE).
3. **Delivery:** review TB & tỷ lệ review xấu theo nhóm mức trễ (discretization), tỷ lệ trễ theo bang, bảng danh mục.
4. **DSS** (mục 5).

---

## 5. Thành phần DSS (Yêu cầu 4)
**Phân loại:** Hybrid DSS = **data-driven** (OLAP trên DW) + **model-driven** (mô hình dự đoán + what-if) *(slide Ch4)*. Kiến trúc theo ví dụ "business analytics DSS" *(slide Ch6)*:
- **Data management subsystem:** DW PostgreSQL ở trên.
- **Model management subsystem** (`src/dss/`):
  1. **Decision Tree (ID3/C4.5, entropy / information gain)** — thuật toán có ví dụ tính tay trong *slide Ch5*. `DecisionTreeClassifier(criterion="entropy", max_depth=4, min_samples_leaf=200, class_weight="balanced")`, train/test 80/20 trên `fact_delivery`. Target: `is_bad_review`. Features: is_late, delay_days, delivery_days, estimated_days, n_items, n_sellers, freight_ratio, same_state, customer_region (one-hot). Xuất **luật IF-THEN kèm P(review xấu)**; tính information gain của `is_late` theo công thức slide.
  2. **Mô hình rủi ro:** mỗi lá cây = một nhóm đơn; tỷ lệ review xấu thực tế của lá (trên tập train) là xác suất review xấu của đơn rơi vào lá đó.
  3. **What-if analysis** *(slide Ch6/Ch7)*: chọn phạm vi (toàn quốc / bang / danh mục) + 2 biến quyết định: "giảm X% số đơn trễ" và "rút ngắn N ngày giao" → mô phỏng lại → dự đoán lại → tỷ lệ trễ, tỷ lệ review xấu kỳ vọng, số review xấu tránh được.
  4. **Sensitivity analysis:** đường tỷ lệ review xấu kỳ vọng theo mức giảm trễ 0–100%.
  5. **Goal seeking:** nhập mục tiêu "review xấu ≤ T%" → duyệt từng 1% (complete enumeration) tìm mức giảm trễ tối thiểu; báo không khả thi nếu 100% vẫn chưa đạt.
  6. **Xếp hạng ưu tiên (Choice):** bang/danh mục sắp theo số review xấu tránh được nếu hết trễ; kèm đề xuất hành động (Implementation).
- **User interface (dialog) subsystem:** trang DSS (4 tab) trên Streamlit.
- Mô hình **under risk** *(slide Ch7)*; decision variables = mức giảm trễ / số ngày rút ngắn; uncontrollable variables = hành vi khách (thể hiện qua tỷ lệ theo lá); result variable = tỷ lệ review xấu kỳ vọng *(slide Ch7)*.

---

## 6. Đánh giá (Yêu cầu 5)

### Kết quả hiện thực
- **ETL:** số dòng staging = số dòng CSV cho cả 8 file; `SUM(price)` staging = `dw.fact_sales` = 13,591,643.70; chạy lại cho cùng kết quả.
- **Dữ liệu:** tỷ lệ giao trễ 6.8%; tỷ lệ review xấu 12.8%; review TB đơn trễ 2.27★ so với đơn đúng hạn 4.29★.
- **Mô hình (tập test 19,165 đơn):** accuracy 79.7%; lớp review xấu: precision 32.9%, recall 56.8%, F1 0.417.
- **Luật nổi bật:** trễ 5.5–34.5 ngày → P(review xấu) 79.7%; đơn nhiều sản phẩm từ nhiều người bán → 45–54% dù không trễ; đơn 1 sản phẩm giao ≤ 9 ngày đúng hạn → 6.0%. `delay_days` chiếm ~72% độ quan trọng. Gain(is_late) = 0.0728 bit.
- **DSS:** giảm 50% đơn trễ toàn quốc → review xấu kỳ vọng 12.9% → 11.2%; muốn ≤ 11% cần giảm 58% đơn trễ. Ưu tiên: SP (~805 review xấu tránh được, do quy mô) và RJ (~769, tỷ lệ trễ 11.9% — gấp ~2.7 lần SP).

### Hạn chế
Dữ liệu chỉ 2016–2018 (tháng đầu/cuối rất ít đơn); 97% khách mua 1 lần; review có thể do nguyên nhân khác ngoài giao hàng nên precision thấp; what-if giả định giao trễ là nguyên nhân; full refresh thay vì incremental; chưa dùng geolocation/SCD.

### Hướng phát triển
Incremental load, SCD type 2, bản đồ địa lý, dự báo nhu cầu, tối ưu hoá chọn đơn vị vận chuyển (LP).

## 7. Phương pháp phát triển *(slide Ch8)*
**Prototyping (iterative / evolutionary, RAD)**: vòng 1 DW + dashboard tối thiểu → vòng 2 thêm DSS → vòng 3 hoàn thiện theo feedback review.

---

## 8. Phân công (1 người code, 2 người review — cả 3 thuyết trình)
| Thành viên | Vai trò | Phần thuyết trình |
|---|---|---|
| A | Hiện thực toàn bộ code; review chéo báo cáo | Bài toán, kiến trúc, schema, ETL |
| B | Review DW/ETL/OLAP (`src/sql`, `src/etl`, trang 1–3); viết phần DW trong báo cáo | Demo OLAP 5 phép toán, insight |
| C | Review DSS (`src/dss`, trang DSS); viết phần DSS + đánh giá; làm slide | Mô hình, what-if, goal seeking, đánh giá |

## 9. Lịch (02/11 → 15/11)
| Ngày | Việc |
|---|---|
| 02/11 | ✅ Chốt đề tài; hiện thực DW, ETL, dashboard, DSS |
| 03–07/11 | Review code (B, C), sửa theo góp ý |
| 08–12/11 | Viết báo cáo, chụp hình dashboard |
| 13–14/11 | Slide, quay video (nếu cần) |
| 15/11 | Đóng gói ZIP, nộp |

## 10. Cấu trúc repo (khớp yêu cầu nộp `src/`, `data/`)
```
environment.yml             # Python 3.12 + PostgreSQL 16 + packages (micromamba, cục bộ trong project)
scripts/                    # setup_env.sh, env.sh, db_start.sh, db_stop.sh
data/                       # 9 CSV Olist (bộ đầy đủ; .gitignore bỏ qua CSV, ghi link Kaggle)
src/db.py                   # kết nối DB dùng chung
src/sql/01_staging.sql  02_dw_schema.sql  03_transform_load.sql  04_olap_views.sql
src/etl/run_etl.py          # Extract → Transform → Load + ghi meta.etl_log
src/dss/train_model.py      # train cây quyết định, lưu model + luật
src/dss/whatif.py           # what-if / sensitivity / goal seeking / xếp hạng
src/app/Home.py  common.py  pages/1_OLAP.py  2_Delivery.py  3_DSS.py
models/                     # (sinh ra) decision_tree.joblib, rules.txt, metrics.json
docs/proposal.md  README.md
report/  slides/            # (nhóm bổ sung khi viết báo cáo)
```
