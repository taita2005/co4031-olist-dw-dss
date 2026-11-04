# Olist DW & DSS — BTL CO4031 (HK261)

Kho dữ liệu (Data Warehouse) phân tích **bán hàng – giao hàng** và hệ hỗ trợ quyết định (DSS) giúp quản lý vận hành sàn TMĐT Olist trả lời:

> *Nên ưu tiên cải thiện giao hàng ở bang / danh mục nào, và cải thiện bao nhiêu, để giảm tỷ lệ đánh giá 1–2 sao?*

**Repo:** https://github.com/taita2005/co4031-olist-dw-dss

README này tập trung vào **code**: cách chạy, code nằm ở đâu, và cần review những gì. Các tài liệu khác nằm trong `docs/`:

| File | Nội dung | Khi nào đọc |
|---|---|---|
| [docs/proposal.md](docs/proposal.md) | Đề xuất đã duyệt: bài toán, thiết kế, ánh xạ với lecture, bảng thay đổi so với bản đầu | Muốn hiểu vì sao thiết kế như vậy |
| [docs/report.md](docs/report.md) | Bản báo cáo thô đầy đủ (5 section), mọi số liệu ở dạng bảng, đối chiếu với yêu cầu của đề | Viết báo cáo PDF chính thức và slide |
| [docs/handoff.md](docs/handoff.md) | Bàn giao tiến độ: việc đã xong, việc còn lại theo thứ tự, các quyết định đã chốt kèm lý do | Bắt đầu một phiên làm việc mới, hoặc cần biết bước tiếp theo |

---

## 1. Chạy project

Mọi thứ (Python 3.12, PostgreSQL 16, các package) được cài vào **môi trường riêng trong thư mục project** bằng micromamba. **Không cần cài sẵn Python, PostgreSQL hay Docker**, và không có gì bị cài vào hệ thống. Muốn gỡ sạch: xoá thư mục project (hoặc chỉ xoá `.tools/ .mamba/ .env-btl/ .pgdata/ models/`).

**Yêu cầu:** macOS (Apple Silicon hoặc Intel) hoặc Linux, có sẵn `git`, `curl`, kết nối Internet cho lần cài đầu. Cần khoảng 2GB trống (môi trường ~1GB, database ~650MB). Windows: chạy trong WSL (Ubuntu).

### 1.1 Lần đầu sau khi clone (~5 phút)

```bash
# 1. Lấy code
git clone https://github.com/taita2005/co4031-olist-dw-dss.git BTL
cd BTL

# 2. Tải dữ liệu Olist từ Kaggle và đặt các file CSV vào data/
#    (hướng dẫn chi tiết + danh sách file: data/README.md)
ls data/*.csv | wc -l          # phải ra 8 hoặc 9

# 3. Cài môi trường cục bộ: micromamba + Python + PostgreSQL + package (~3–5 phút)
bash scripts/setup_env.sh

# 4. Nạp biến môi trường cho terminal hiện tại (bash hoặc zsh)
source scripts/env.sh

# 5. Khởi tạo + bật PostgreSQL cục bộ (port 5433, user btl, database olist_dw)
bash scripts/db_start.sh

# 6. ETL: CSV -> staging -> dw  (~5 giây)
python src/etl/run_etl.py

# 7. Huấn luyện mô hình DSS (~2 giây) -> models/
python src/dss/train_model.py

# 8. Mở dashboard (trình duyệt tự mở http://localhost:8501)
streamlit run src/app/Home.py
```

Kết quả mong đợi ở bước 6: `dw.fact_sales 112,650 rows`, `dw.fact_delivery 96,470 rows`, và dòng cuối `25/25 checks passed`. Nếu có kiểm tra không đạt, script in `FAIL` kèm giá trị kỳ vọng / thực tế và thoát với mã 1.

Chạy test (cần DB đã bật và đã chạy ETL; nên chạy ETL 2 lần để có test "chạy lại cho cùng kết quả"):

```bash
python -m pytest tests -q
```

### 1.2 Những lần sau

Dữ liệu đã nằm trong PostgreSQL và model đã lưu, chỉ cần:

```bash
cd BTL
source scripts/env.sh
bash scripts/db_start.sh
streamlit run src/app/Home.py
```

### 1.3 Khi xong

`Ctrl+C` để tắt Streamlit, rồi `bash scripts/db_stop.sh` để tắt PostgreSQL.

### 1.4 Lệnh hữu ích & xử lý sự cố

| Tình huống | Cách làm |
|---|---|
| Xem dữ liệu bằng SQL | sau `source scripts/env.sh`, gõ `psql` (đã trỏ sẵn vào `olist_dw`) |
| Xem kết quả kiểm tra dữ liệu | `psql -c "SELECT * FROM meta.check_result ORDER BY check_id DESC LIMIT 25"` |
| `pg_ctl: could not start server`, log ghi `could not open directory .../.env-btl/lib` | thư mục project đã bị di chuyển; `rm -rf .env-btl` rồi chạy lại `bash scripts/setup_env.sh` (dữ liệu trong `.pgdata/` vẫn giữ nguyên) |
| Sửa file SQL / ETL, muốn nạp lại | `python src/etl/run_etl.py` (full refresh, chạy lại bao nhiêu lần cũng được) rồi `python src/dss/train_model.py` |
| `command not found: python` / `psql` | quên `source scripts/env.sh` trong terminal này |
| `Missing source file: .../data/...csv` | chưa đặt CSV vào `data/` (xem `data/README.md`) |
| `connection refused` (port 5433) | chưa chạy `bash scripts/db_start.sh` |
| Dashboard vẫn hiện số cũ sau khi chạy lại ETL | trong Streamlit bấm menu ⋮ → *Clear cache*, rồi *Rerun* |
| Muốn xoá DB làm lại từ đầu | `bash scripts/db_stop.sh && rm -rf .pgdata` rồi chạy lại từ bước 5 |
| Cài môi trường bị lỗi giữa chừng | `rm -rf .env-btl` rồi chạy lại `bash scripts/setup_env.sh` |

---

## 2. Kiến trúc (Three-Tier)

```
┌─ Bottom tier ─────────────┐   ┌─ Middle tier ─────────────────────────┐   ┌─ Top tier ───────────┐
│ data/*.csv (8 file Olist) │──▶│ schema staging  (bảng thô, toàn TEXT) │   │ Streamlit            │
│                           │   │        │ Transform + Load (SQL)       │   │  Home   (KPI)        │
│ run_etl.py: COPY          │   │        ▼                              │──▶│  OLAP   (5 phép)     │
│                           │   │ schema dw  (fact constellation)       │   │  Delivery            │
│                           │   │ + materialized views (ROLAP)          │   │  DSS    (mô hình)    │
│                           │   │ schema meta (etl_log = metadata)      │   │                      │
└───────────────────────────┘   └───────────────────────────────────────┘   └──────────────────────┘
```

Ba schema trong cùng database `olist_dw`:

| Schema | Vai trò | Vòng đời |
|---|---|---|
| `staging` | Data staging area: bản sao y nguyên CSV | Xoá & tạo lại mỗi lần ETL |
| `dw` | Dimensional data store: dimension + fact + materialized view | Xoá & tạo lại mỗi lần ETL (full refresh) |
| `meta` | `etl_log`: lịch sử các lần chạy ETL ("history of extracts"); `check_result`: kết quả kiểm tra chất lượng dữ liệu của từng lần chạy | **Giữ lại** qua các lần chạy |

---

## 3. Bản đồ code

```
README.md              file này
CLAUDE.md              hướng dẫn cho Claude Code (lệnh, kiến trúc, đặc điểm dữ liệu)
CO4031_Assignment_HK261.pdf   đề bài tập lớn
.gitignore             bỏ qua CSV, lectures/, môi trường, database, models/
scripts/
  env.sh               biến môi trường dùng chung (đường dẫn env, PGPORT=5433…)
  setup_env.sh         tải micromamba + tạo env từ environment.yml
  db_start.sh / db_stop.sh   initdb (lần đầu) + bật/tắt PostgreSQL cục bộ
environment.yml        danh sách package (thay cho requirements.txt)

src/
  db.py                tạo kết nối SQLAlchemy + hàm query() trả DataFrame — dùng chung
  sql/
    01_staging.sql     tạo bảng staging (toàn TEXT)
    02_dw_schema.sql   tạo dimension, fact, index, partition, meta.etl_log
    03_transform_load.sql   toàn bộ logic Transform + Load (đọc file này kỹ nhất)
    04_olap_views.sql  3 materialized view tổng hợp sẵn
    05_checks.sql      25 kiểm tra chất lượng dữ liệu (grain, đối chiếu staging-dw, miền giá trị, MV) -> meta.check_result
  etl/run_etl.py       điều phối: chạy 5 file SQL theo thứ tự + COPY CSV + ghi etl_log + in kết quả kiểm tra
  dss/
    train_model.py     đọc fact_delivery -> train cây quyết định -> lưu models/
    whatif.py          what-if, sensitivity, goal seeking, xếp hạng ưu tiên
    optimizer.py       tối ưu ngân sách: bảng lợi ích bang x mức, 0-1 integer programming (scipy milp), greedy, khuyến nghị
  app/
    common.py          cache kết nối/truy vấn cho Streamlit
    Home.py            trang chủ: KPI + xu hướng theo tháng + metadata ETL
    pages/1_OLAP.py    OLAP Explorer (roll-up, drill-down, slice, dice, pivot)
    pages/2_Delivery.py   phân tích giao hàng & review
    pages/3_DSS.py     giao diện DSS

tests/
  conftest.py          fixture dùng chung (tự skip test cần DB nếu DB chưa bật)
  test_whatif_unit.py  unit test simulate() trên dữ liệu tự tạo (không cần DB)
  test_etl_checks.py   lần ETL mới nhất đạt mọi kiểm tra; cố tình làm hỏng DW (rollback) để chắc kiểm tra bắt được lỗi; chạy lại cho cùng kết quả
  test_dss_model.py    what-if giảm đơn điệu, goal seeking trả mức nhỏ nhất, xếp hạng đúng thứ tự
  test_optimizer.py    MILP khớp với vét cạn trên bài toán nhỏ ngẫu nhiên; greedy khả thi và không vượt tối ưu; options.csv khớp mô hình
config/
  cost_assumptions.csv 2 tham số GIẢ ĐỊNH của chi phí: phụ phí (% phí ship) và hệ số theo mức (xem config/README.md)
models/                (sinh ra, không có trên GitHub) decision_tree.joblib, rules.txt, metrics.json, options.csv
data/README.md         link tải dữ liệu Olist + danh sách CSV cần đặt vào data/ (CSV không có trên GitHub)
docs/
  proposal.md          đề xuất đã duyệt (+ bảng thay đổi so với bản đầu)
  report.md            bản báo cáo thô đầy đủ, số liệu dạng bảng
  handoff.md           bàn giao: đã xong / còn lại / quyết định đã chốt
```

---

## 4. Thiết kế kho dữ liệu

### Schema: fact constellation (2 fact dùng chung dimension)

```
                 dim_date ──────────────┐
                    │                   │ (purchase_date_key, delivered_date_key)
 dim_customer ── fact_sales          fact_delivery ── dim_customer
 dim_seller   ──┘   │                   │  └──────── dim_seller
 dim_product  ──────┘                   └─────────── dim_product
```

| Bảng | Grain (1 dòng =) | Số dòng | Ghi chú |
|---|---|---|---|
| `dim_date` | 1 ngày | 1,096 | 2016-01-01 → 2018-12-31; hierarchy year > quarter > month > day |
| `dim_customer` | 1 khách hàng thật (`customer_unique_id`) | 96,096 | hierarchy region > state > city |
| `dim_seller` | 1 người bán | 3,095 | hierarchy region > state > city |
| `dim_product` | 1 sản phẩm | 32,951 | category (EN) > product |
| `fact_sales` | 1 sản phẩm trong 1 đơn hàng | 112,650 | measures: price, freight_value, total_value; partition theo năm |
| `fact_delivery` | 1 đơn hàng **đã giao** | 96,470 | measures: delivery_days, delay_days, is_late, review_score, is_bad_review… |

**Vì sao 2 fact?** (vấn đề granularity) Review và ngày giao thuộc về *cả đơn hàng*, không thuộc từng sản phẩm. Nếu nhét vào `fact_sales` (grain = item), một đơn 3 sản phẩm sẽ bị đếm review 3 lần.

`fact_delivery` lấy `seller_key` / `product_key` của **sản phẩm giá cao nhất** trong đơn (“item chính”) để có thể phân tích theo người bán / danh mục.

### Quy tắc Transform (trong [03_transform_load.sql](src/sql/03_transform_load.sql))

| Loại | Quy tắc |
|---|---|
| Cleansing | Đơn có nhiều review → lấy review trả lời gần nhất. 610 sản phẩm thiếu danh mục → `unknown`. 2 danh mục thiếu bản dịch → bổ sung tay. Chuỗi rỗng → NULL khi ép kiểu. (Riêng BOM ở đầu CSV dịch danh mục được xử lý ở bước Extract trong `run_etl.py`, đọc bằng `utf-8-sig`.) |
| Mapping | Tên danh mục PT → EN; timestamp → `date_key` (yyyymmdd); bang → vùng (5 vùng Brazil). Zip code giữ dạng TEXT (có số 0 đầu). |
| Business rules | Khách hàng thật = `customer_unique_id` (vì `customer_id` sinh mới mỗi đơn). `fact_delivery` chỉ gồm đơn `delivered` có ngày giao. `is_late` = giao thực tế > ngày dự kiến. Review xấu = điểm ≤ 2. |
| Attribute construction | `delivery_days`, `estimated_days`, `delay_days`, `volume_cm3`, `region`. |

### OLAP (ROLAP)
- Dữ liệu chi tiết ở bảng quan hệ; trang OLAP sinh câu `GROUP BY` động (xem expander “SQL được sinh ra” trên trang).
- Tổng hợp sẵn bằng materialized view: `mv_monthly_kpi`, `mv_sales_cube` (`GROUP BY CUBE`), `mv_delivery_by_state`.
- Trang OLAP phân biệt measure **cộng dồn được** (SUM, COUNT) với **không cộng dồn được** (COUNT DISTINCT, AVG, tỷ lệ) — chỉ hiện dòng tổng cho loại đầu.

---

## 5. Thành phần DSS

Hybrid DSS = **data-driven** (OLAP trên DW) + **model-driven** (mô hình dưới đây).

**Mô hình:** cây quyết định `DecisionTreeClassifier(criterion="entropy", max_depth=4, min_samples_leaf=200, class_weight="balanced")` — tiêu chí information gain như ID3/C4.5 trong lecture Ch.5.
- Input: `is_late, delay_days, delivery_days, estimated_days, n_items, n_sellers, freight_ratio, same_state, region_*`
- Target: `is_bad_review`
- Chia train/test 80/20 (stratified, `random_state=42`).

**Mẹo quan trọng để hiểu `whatif.py`:** cây được dùng như *mô hình rủi ro*. Mỗi lá = một nhóm đơn hàng; **tỷ lệ review xấu thực tế của nhóm đó trên tập train** (`leaf_rate`) là xác suất review xấu của mọi đơn rơi vào lá đó. (Không dùng `predict_proba` vì `class_weight="balanced"` làm lệch xác suất.)

| Chức năng | Hàm | Cách làm |
|---|---|---|
| What-if | `simulate()` + `evaluate_scenario()` | Biến quyết định: `late_reduction` (biến X% đơn trễ thành đúng hạn — đơn được chọn theo cột `rand` cố định nên kết quả ổn định) và `days_faster` (rút ngắn N ngày cho mọi đơn). Dự đoán lại → tỷ lệ review xấu kỳ vọng mới. |
| Sensitivity | `sensitivity()` | Quét `late_reduction` 0% → 100%, vẽ đường tỷ lệ review xấu. |
| Goal seeking | `goal_seek()` | Duyệt `late_reduction` từng 1% (complete enumeration), trả về mức nhỏ nhất đạt mục tiêu; `None` nếu không đạt. |
| Xếp hạng (Choice) | `priority_ranking()` | Với mỗi bang/danh mục: giả sử hết trễ → tổng số review xấu tránh được; sắp giảm dần. |
| Tối ưu ngân sách (Choice) | `optimizer.solve()` | Mỗi bang chọn 1 mức giảm đơn trễ (25/50/75/100%) hoặc không làm, để tối đa review xấu tránh được với tổng chi phí ≤ ngân sách và ≤ K bang (0-1 integer programming). Lợi ích lấy từ mô hình (tính sẵn trong `models/options.csv`). Chi phí (BRL) = phí ship **thực tế** của các đơn trễ được sửa × phụ phí × hệ số theo mức; chỉ 2 tham số cuối là **giả định** (`config/`). So sánh với `greedy()`; `tier_sensitivity()` kiểm tra độ nhạy theo hệ số; `recommend()` sinh khuyến nghị bằng lời. |

### Kết quả hiện tại (dữ liệu đầy đủ)
- Accuracy 79.7%, precision (review xấu) 32.9%, recall 56.8%, F1 0.417.
- `delay_days` chiếm ~72% độ quan trọng; đơn trễ 5–34 ngày có P(review xấu) ≈ 80%, đơn đúng hạn 1 sản phẩm giao ≤ 9 ngày chỉ ≈ 6%.
- Đơn nhiều sản phẩm từ nhiều người bán cũng rủi ro cao (~45–54%) dù không trễ → gợi ý nguyên nhân giao tách nhiều lần.
- Gain(is_late) = 0.0728 bit.
- Giảm 50% đơn trễ toàn quốc: review xấu kỳ vọng 12.9% → 11.2%. Muốn ≤ 11% cần giảm 58% đơn trễ.
- Ưu tiên theo số review xấu tránh được: SP (~805), RJ (~769, nhưng tỷ lệ trễ RJ 11.9% gấp ~2.7 lần SP).

---

## 6. Gợi ý review

**Thứ tự đọc:** `02_dw_schema.sql` → `03_transform_load.sql` → `run_etl.py` → `train_model.py` → `whatif.py` → các trang trong `src/app/`.

**Checklist:**
- [ ] Grain của 2 fact có hợp lý? Có join nào gây nhân dòng không (đặc biệt `order_reviews`, `order_items`)?
- [ ] Các business rule (định nghĩa trễ, review xấu, khách hàng thật) có đúng ý nhóm?
- [ ] `run_etl.py` chạy lại nhiều lần có ra cùng kết quả? `meta.etl_log` có tăng thêm 1 lượt mỗi lần?
- [ ] Đối chiếu: `SELECT SUM(price::numeric) FROM staging.order_items` = `SELECT SUM(price) FROM dw.fact_sales` (đều 13,591,643.70). Đã tự động hoá trong `05_checks.sql`; đọc lại xem còn thiếu kiểm tra nào không.
- [ ] `python -m pytest tests -q` chạy xanh.
- [ ] Trang OLAP: thử drill-down Năm → Quý → Tháng, pivot, dice theo bang; mở expander SQL để đối chiếu.
- [ ] `whatif.simulate`: thao tác trên đơn trễ có đúng (`delivery_days = estimated_days`, `delay_days = 0`)?
- [ ] Kéo slider what-if: tỷ lệ review xấu phải giảm khi tăng mức giảm trễ.

---

## 7. Hạn chế & hướng phát triển
- Dữ liệu 2016–2018, các tháng đầu/cuối rất ít đơn (dashboard chỉ vẽ 2017-01 → 2018-08).
- Không nạp `olist_geolocation_dataset.csv` (1 triệu dòng, không cần cho bài toán) → chưa có bản đồ.
- Full refresh thay vì incremental load; chưa dùng SCD (khách đổi địa chỉ chỉ giữ địa chỉ của đơn gần nhất).
- What-if giả định giao trễ là *nguyên nhân* của review xấu; thực tế còn chất lượng sản phẩm, đóng gói…
- Precision của mô hình còn thấp (review xấu có nhiều nguyên nhân ngoài dữ liệu giao hàng).
- Hướng phát triển: incremental ETL, SCD type 2, bản đồ địa lý, mô hình tối ưu (LP) chọn đơn vị vận chuyển.
