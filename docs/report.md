# BÁO CÁO BÀI TẬP LỚN — CO4031 Kho dữ liệu & Hệ hỗ trợ Quyết định (HK261)

> **Bản raw.** Tài liệu này chứa toàn bộ nội dung và số liệu của project. Nó là nguồn để viết báo cáo chính thức (PDF) và slide thuyết trình.
> - Mọi số liệu đều lấy từ kho dữ liệu (PostgreSQL) và từ mô hình đã huấn luyện, trên dữ liệu Olist đầy đủ. Số liệu gốc lấy ngày 02/11/2026. Ngày 14/11/2026 đã chạy lại ETL và train lại mô hình: số dòng, tổng tiền và metrics mô hình không đổi. Cũng trong lần cập nhật này, nhóm bổ sung các phần mới: kiểm soát chất lượng dữ liệu (§2.5), thực nghiệm chọn tham số (§4.2.2), kiểm tra mô hình rủi ro trên tập test (§4.3) và tối ưu ngân sách (§4.4.7).
> - Số liệu được trình bày dưới dạng bảng để vẽ biểu đồ sau. Gợi ý loại biểu đồ ghi trong ngoặc *(biểu đồ: …)*.
> - Chỗ nhóm cần tự điền được đánh dấu **[TODO]**. Chỗ cần chèn ảnh chụp màn hình được đánh dấu **[HÌNH]**.

---

## Trang bìa

| Mục | Nội dung |
|---|---|
| Trường / Khoa | Trường Đại học Bách khoa – ĐHQG TP.HCM, Khoa Khoa học và Kỹ thuật Máy tính |
| Môn học | CO4031 – Kho dữ liệu và Hệ hỗ trợ Quyết định, HK261 (2026–2027) |
| Giảng viên | Đỗ Thanh Thái |
| Tên đề tài | **Kho dữ liệu phân tích bán hàng – giao hàng và hệ hỗ trợ quyết định cải thiện sự hài lòng khách hàng cho sàn TMĐT Olist** |
| Nhóm | [TODO] số nhóm |
| Link mã nguồn (GitHub) | https://github.com/taita2005/co4031-olist-dw-dss |
| Link dữ liệu (Google Drive) | [TODO] (hoặc Kaggle: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) |
| Link video thuyết trình | [TODO] (chỉ khi thuyết trình qua video — bắt buộc theo §4.3, §5.1 của đề) |

### Thành viên & phân công

| Thành viên | MSSV | Vai trò | Công việc cụ thể | Phần thuyết trình | Đóng góp |
|---|---|---|---|---|---|
| [TODO] A | [TODO] | Phát triển hệ thống | Hiện thực toàn bộ mã nguồn: DW, ETL, OLAP dashboard, DSS; review chéo báo cáo | Section 1–2 (bài toán, dữ liệu, kho dữ liệu, ETL) | [TODO] % |
| [TODO] B | [TODO] | Review DW / OLAP, viết báo cáo | Review `src/sql`, `src/etl`, các trang Home / OLAP / Delivery; viết Section 2–3 | Section 3 (demo OLAP, insight) | [TODO] % |
| [TODO] C | [TODO] | Review DSS, viết báo cáo, slide | Review `src/dss`, trang DSS; viết Section 4–5; làm slide | Section 4–5 (DSS, đánh giá) | [TODO] % |

---

## Mục lục

1. Giới thiệu
2. Kho dữ liệu & ETL
3. OLAP & Dashboard
4. Hệ hỗ trợ quyết định (DSS)
5. Đánh giá & kết luận

Tài liệu tham khảo · Phụ lục A–E

---

# 1. Giới thiệu

## 1.1 Bài toán

**Bối cảnh.** Olist là sàn thương mại điện tử của Brazil. Sàn kết nối các người bán nhỏ với khách hàng trên toàn quốc, còn việc giao hàng do các đơn vị vận chuyển đảm nhận. Sau khi nhận hàng, khách hàng chấm điểm đơn hàng từ 1 đến 5 sao. Điểm thấp ảnh hưởng trực tiếp đến uy tín của sàn và của người bán.

**Vấn đề.** Trong dữ liệu 2016–2018, **12.81%** đơn đã giao bị đánh giá 1–2 sao (gọi là *review xấu*). Phân tích ban đầu cho thấy giao trễ là nghi phạm chính:

| Nhóm đơn đã giao | Số đơn | Điểm review TB | Tỷ lệ review xấu |
|---|---|---|---|
| Giao đúng hạn hoặc sớm | 89,936 | 4.290 | 9.27% |
| Giao trễ (sau ngày dự kiến) | 6,534 | 2.270 | 62.42% |
| **Tổng** | **96,470** | **4.156** | **12.81%** |

*(biểu đồ: cột đôi)*

**Người ra quyết định:** quản lý vận hành / logistics của sàn.

**Loại quyết định:** *semi-structured*. Dữ liệu cho biết hiện trạng, nhưng chọn nơi đầu tư và mức đầu tư vẫn cần phán đoán của quản lý (slide Ch.6: DSS hỗ trợ các quyết định semi-structured và unstructured).

**Câu hỏi phân tích** (DW / OLAP trả lời, Section 2–3):
1. Doanh thu và số đơn biến động thế nào theo thời gian, vùng, danh mục?
2. Tỷ lệ giao trễ và thời gian giao trung bình theo bang và danh mục?
3. Điểm review thay đổi thế nào theo mức độ trễ?

**Câu hỏi quyết định** (DSS trả lời, Section 4):
1. Yếu tố nào dẫn đến review xấu?
2. *What-if:* nếu giảm X% đơn trễ (hoặc rút ngắn N ngày giao) ở một bang hay danh mục, tỷ lệ review xấu giảm bao nhiêu?
3. *Goal seeking:* cần giảm bao nhiêu % đơn trễ để tỷ lệ review xấu không vượt mục tiêu T%?
4. Nên ưu tiên đầu tư logistics cho bang hay danh mục nào?
5. *Tối ưu:* với một ngân sách giới hạn, nên chọn những bang nào và giảm bao nhiêu % đơn trễ ở mỗi bang để tránh được nhiều review xấu nhất? Thứ tự ưu tiên đó có còn đúng khi giả định chi phí thay đổi không? **Đây là câu hỏi quyết định chính**, được trả lời ở §4.4.7.

## 1.2 Dữ liệu (Dataset)

**Nguồn:** *Brazilian E-Commerce Public Dataset by Olist*, Kaggle (dữ liệu mở; thoả §3.1b của đề). Dữ liệu là đơn hàng thật đã được ẩn danh, với ngày mua từ **2016-09-04** đến **2018-10-17**.

| File CSV | Số dòng | Nội dung | Dùng trong project |
|---|---|---|---|
| olist_orders_dataset | 99,441 | Đơn hàng: khách, trạng thái, 5 mốc thời gian | ✅ |
| olist_order_items_dataset | 112,650 | Sản phẩm trong đơn: giá, phí ship, người bán | ✅ |
| olist_order_payments_dataset | 103,886 | Thanh toán (một đơn có thể có nhiều lần thanh toán) | ✅ nạp vào staging (chưa dùng trong DW) |
| olist_order_reviews_dataset | 99,224 | Đánh giá 1–5 sao | ✅ |
| olist_customers_dataset | 99,441 | Khách hàng: zip, thành phố, bang | ✅ |
| olist_sellers_dataset | 3,095 | Người bán: zip, thành phố, bang | ✅ |
| olist_products_dataset | 32,951 | Sản phẩm: danh mục, kích thước, khối lượng | ✅ |
| product_category_name_translation | 71 | Dịch tên danh mục Bồ Đào Nha → Anh | ✅ |
| olist_geolocation_dataset | 1,000,163 | Toạ độ theo zip code | ❌ không cần cho bài toán |

**Quan hệ giữa các bảng nguồn:** `orders` là bảng trung tâm.
- `order_items`, `order_payments`, `order_reviews` nối với `orders` qua `order_id`.
- `order_items` nối với `products` và `sellers`.
- `orders` nối với `customers` qua `customer_id`.

[HÌNH] ERD dữ liệu nguồn.

**Trạng thái đơn hàng:**

| order_status | Số đơn | Tỷ lệ |
|---|---|---|
| delivered | 96,478 | 97.02% |
| shipped | 1,107 | 1.11% |
| canceled | 625 | 0.63% |
| unavailable | 609 | 0.61% |
| invoiced | 314 | 0.32% |
| processing | 301 | 0.30% |
| created | 5 | 0.01% |
| approved | 2 | 0.00% |

**Phương thức thanh toán** (bảng payments):

| payment_type | Số lượt | Giá trị (R$) |
|---|---|---|
| credit_card | 76,795 | 12,542,084.19 |
| boleto | 19,784 | 2,869,361.27 |
| voucher | 5,775 | 379,436.87 |
| debit_card | 1,529 | 217,989.79 |
| not_defined | 3 | 0.00 |

**Khảo sát chất lượng dữ liệu (data profiling).** Đây là cơ sở cho các quy tắc làm sạch ở Section 2.2:

| # | Vấn đề | Số liệu | Cách xử lý |
|---|---|---|---|
| 1 | `customer_id` được sinh mới cho mỗi đơn, không định danh khách thật | 99,441 customer_id ứng với 96,096 `customer_unique_id`; 2,997 khách mua > 1 lần | Dimension khách hàng dùng `customer_unique_id` |
| 2 | Review trùng | 99,224 dòng, 98,410 review_id, 98,673 đơn; 547 đơn có > 1 review | Mỗi đơn giữ review trả lời gần nhất |
| 3 | Sản phẩm thiếu danh mục | 610 sản phẩm | Gán `unknown` |
| 4 | Danh mục thiếu bản dịch | 2 danh mục (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) | Bổ sung bản dịch thủ công |
| 5 | Sản phẩm thiếu khối lượng / kích thước | 2 sản phẩm | Để NULL |
| 6 | Đơn chưa có ngày giao | 2,965 đơn; trong đó 8 đơn trạng thái `delivered` | Loại khỏi `fact_delivery` |
| 7 | Một đơn có nhiều lần thanh toán | 2,961 đơn | Không cộng thanh toán theo item (tránh đếm trùng) |
| 8 | Một đơn có nhiều người bán | 1,278 đơn | Lưu `n_sellers`; chọn “người bán chính” |
| 9 | File dịch danh mục có ký tự BOM đầu file | — | Đọc bằng `utf-8-sig` |
| 10 | Zip code có số 0 đầu (vd. `01037`) | — | Lưu dạng TEXT |
| 11 | Comment review chứa xuống dòng | — | Dùng CSV parser thật (`COPY … CSV`, `csv.reader`) |
| 12 | Geolocation không duy nhất theo zip | 1,000,163 dòng / 19,015 zip | Không nạp |

## 1.3 Giải pháp và tính năng

Nhóm xây dựng một **data mart chủ đề Bán hàng & Giao hàng** theo **kiến trúc ba tầng** (slide Ch.2–3). Phía trên data mart là một dashboard OLAP và một DSS.

```
┌─ Bottom tier ─────────────┐   ┌─ Middle tier ─────────────────────────┐   ┌─ Top tier ───────────┐
│ 8 file CSV Olist          │──▶│ schema staging (bảng thô, toàn TEXT)  │   │ Streamlit            │
│ (kiểm tra hợp đồng nguồn, │   │      │ Transform + Load (SQL)         │   │  Home   (KPI)        │
│  rồi Extract: COPY)       │   │      ▼                                │──▶│  OLAP   (5 phép)     │
│                           │   │ schema dw (fact constellation)        │   │  Delivery            │
│                           │   │ + materialized views (ROLAP)          │   │  DSS    (5 tab)      │
│                           │   │ schema meta (etl_log, check_result)   │   │  Data Quality        │
└───────────────────────────┘   └───────────────────────────────────────┘   └──────────────────────┘
```

[HÌNH] Vẽ lại sơ đồ kiến trúc.

**Tính năng ↔ câu hỏi nghiệp vụ:**

| Tính năng | Nơi hiện thực | Trả lời câu hỏi |
|---|---|---|
| ETL tự động CSV → staging → DW, ghi metadata | `src/etl/run_etl.py`, `src/sql/*.sql` | Nền tảng dữ liệu tích hợp |
| Kiểm tra hợp đồng nguồn và 43 kiểm tra chất lượng sau mỗi lần nạp | `src/etl/contracts.py`, `src/sql/05_checks.sql`, trang **Data Quality** | Độ tin cậy của dữ liệu |
| Dashboard KPI và xu hướng theo tháng | trang **Home** | Phân tích 1 |
| OLAP Explorer: roll-up, drill-down, slice, dice, pivot trên 2 fact | trang **OLAP** | Phân tích 1, 2 |
| Phân tích giao hàng và review theo mức trễ, bang, danh mục | trang **Delivery** | Phân tích 2, 3 |
| Cây quyết định và luật IF-THEN về review xấu | trang **DSS**, tab 1 | Quyết định 1 |
| Xếp hạng ưu tiên bang / danh mục và đề xuất hành động | trang **DSS**, tab 2 | Quyết định 4 |
| What-if (2 biến quyết định) và sensitivity analysis | trang **DSS**, tab 3 | Quyết định 2 |
| Goal seeking | trang **DSS**, tab 4 | Quyết định 3 |
| Tối ưu phân bổ ngân sách (quy hoạch nguyên 0-1) và phân tích độ vững theo giả định chi phí | trang **DSS**, tab 5 | Quyết định 5 |

## 1.4 Công nghệ

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| CSDL / DW | PostgreSQL 16 | Partitioning, materialized view, `GROUP BY CUBE` |
| ETL | Python 3.12 (psycopg2, SQLAlchemy) + SQL | Python điều phối, SQL biến đổi |
| Mô hình DSS | scikit-learn 1.5, pandas | `DecisionTreeClassifier` (entropy) |
| Tối ưu | SciPy (`milp`, solver HiGHS) | Giải chính xác bài toán phân bổ ngân sách |
| Kiểm thử | pytest | 102 test: unit + kiểm tra trên CSDL thật |
| Giao diện | Streamlit 1.39, Plotly | Web app nhiều trang |
| Môi trường | micromamba (cục bộ trong project) | Cài Python + PostgreSQL mà không đụng hệ thống; cài bằng 1 lệnh |

**Phương pháp phát triển:** *prototyping* (iterative / evolutionary, RAD). Theo slide Ch.8, đây là cách DSS thường được phát triển. Vòng 1 làm DW và dashboard tối thiểu, vòng 2 thêm DSS, vòng 3 hoàn thiện theo góp ý review.

---

# 2. Kho dữ liệu & ETL

> **Lý thuyết áp dụng (slide Ch.1–3).** Theo Inmon, kho dữ liệu là *“a subject-oriented, integrated, time-variant, and non-volatile collection of data in support of management's decision-making process”*. Thiết kế đi qua các mức: khái niệm (data cube) → logic (star / snowflake / fact constellation) → vật lý. Hai quyết định thiết kế quan trọng nhất là **granularity** và **partitioning** (slide Ch.2-cont).

## 2.1 Thiết kế kho dữ liệu

### 2.1.1 Bốn đặc tính Inmon trong project

| Đặc tính | Thể hiện |
|---|---|
| Subject-oriented | Chỉ tập trung vào chủ đề bán hàng – giao hàng – hài lòng |
| Integrated | Gộp 8 nguồn và chuẩn hoá: khách hàng thật, danh mục tiếng Anh, vùng địa lý, khoá ngày thống nhất |
| Time-variant | Chiều `dim_date` (2016–2018) và mọi fact đều gắn khoá ngày |
| Non-volatile | DW chỉ được nạp (load), không bị cập nhật bởi giao dịch |

**Hướng tiếp cận:** *Bottom-Up (Kimball)*: xây trước một data mart cho một chủ đề (slide Ch.3).

### 2.1.2 Mức khái niệm — Data cube

| Thành phần | Nội dung |
|---|---|
| Chiều (dimensions) | Thời gian, Khách hàng (địa lý), Người bán (địa lý), Sản phẩm (danh mục) |
| Measures — khối Bán hàng | doanh thu (price), phí vận chuyển, số sản phẩm, số đơn |
| Measures — khối Giao hàng | số ngày giao, số ngày trễ, có trễ không, điểm review, có review xấu không |

### 2.1.3 Mức logic — Fact constellation

Schema gồm **2 bảng fact dùng chung 4 dimension**. Đây là *fact constellation* (galaxy schema), giống ví dụ *“sales and shipping data warehouse”* trong slide Ch.3.

```
                 dim_date ──────────────┐
                    │                   │ (purchase_date_key, delivered_date_key)
 dim_customer ── fact_sales          fact_delivery ── dim_customer
 dim_seller   ──┘   │                   │  └──────── dim_seller
 dim_product  ──────┘                   └─────────── dim_product
```

[HÌNH] Vẽ lại schema bằng dbdiagram.io hoặc chụp từ DBeaver.

**Grain (granularity):**

| Fact | Grain (1 dòng =) | Lý do |
|---|---|---|
| `fact_sales` | 1 sản phẩm trong 1 đơn hàng | Mức chi tiết nhất của doanh thu; phân tích được theo sản phẩm và người bán |
| `fact_delivery` | 1 đơn hàng **đã giao** | Ngày giao và review thuộc về **cả đơn**, không thuộc từng sản phẩm |

**Vì sao không gộp thành 1 fact?** Nếu đặt review vào `fact_sales`, một đơn có 3 sản phẩm sẽ lặp review 3 lần. Khi đó điểm trung bình và tỷ lệ review xấu sẽ bị tính sai (đếm trùng). Đây chính là vấn đề granularity nêu trong slide Ch.2-cont.

### 2.1.4 Các bảng dimension

Mọi dimension dùng **surrogate key** kiểu số nguyên tự tăng *(Kimball)*.

| Dimension | Khoá | Thuộc tính | Hierarchy | Số dòng |
|---|---|---|---|---|
| `dim_date` | date_key (yyyymmdd) | full_date, day, month, month_name, quarter, year, year_month, weekday, is_weekend | year > quarter > month > day | 1,096 |
| `dim_customer` | customer_key | customer_unique_id, zip_code_prefix, city, state, region | region > state > city | 96,096 |
| `dim_seller` | seller_key | seller_id, zip_code_prefix, city, state, region | region > state > city | 3,095 |
| `dim_product` | product_key | product_id, category_pt, category_en, photos_qty, weight_g, volume_cm3 | category > product | 32,951 |

`region` là 5 vùng hành chính của Brazil, được ánh xạ từ bang (state):

| Vùng | Các bang |
|---|---|
| North | AC, AP, AM, PA, RO, RR, TO |
| Northeast | AL, BA, CE, MA, PB, PE, PI, RN, SE |
| Central-West | DF, GO, MT, MS |
| Southeast | ES, MG, RJ, SP |
| South | PR, RS, SC |

### 2.1.5 Các bảng fact

**`fact_sales`** — 112,650 dòng

| Cột | Loại | Ý nghĩa |
|---|---|---|
| purchase_date_key, customer_key, seller_key, product_key | FK | Khoá tới 4 dimension |
| order_id, order_item_id, order_status | Degenerate dimension | Thông tin đơn hàng, không cần bảng riêng |
| price | Measure, additive | Giá sản phẩm |
| freight_value | Measure, additive | Phí vận chuyển |
| total_value | Measure, additive | price + freight_value |

**`fact_delivery`** — 96,470 dòng

| Cột | Loại | Ý nghĩa |
|---|---|---|
| order_id | Degenerate, PK | Mã đơn |
| purchase_date_key, delivered_date_key | FK → dim_date | Dùng chiều ngày 2 lần (ngày mua, ngày giao) |
| customer_key | FK | Khách hàng |
| seller_key, product_key | FK | Người bán và sản phẩm của **item chính** (item giá cao nhất trong đơn) |
| n_items, n_sellers | Measure, additive | Số sản phẩm, số người bán trong đơn |
| order_value, freight_total | Measure, additive | Tổng giá, tổng phí ship |
| delivery_days | Measure | Số ngày từ lúc mua đến lúc giao |
| estimated_days | Measure | Số ngày từ lúc mua đến ngày giao dự kiến |
| delay_days | Measure | Ngày giao − ngày dự kiến (> 0 là trễ) |
| is_late | Measure 0/1 | 1 nếu giao trễ |
| review_score | Measure | Điểm 1–5 (NULL nếu đơn không có review) |
| is_bad_review | Measure 0/1 | 1 nếu điểm ≤ 2 |

**Phân loại measure:** tổng tiền, số sản phẩm, số đơn đã giao là **additive** (cộng dồn được). Trung bình, tỷ lệ và số đơn *distinct* là **non-additive**: không lấy tổng của các nhóm con được, phải tính lại từ fact. Trang OLAP thể hiện rõ sự khác biệt này (Section 3.2).

## 2.2 Quy trình ETL

> **Lý thuyết (slide Ch.2).** *Extract* lấy dữ liệu mà không làm gián đoạn hệ thống nguồn. *Transform* gồm data cleansing, data mapping và business rules application. *Load* có thể nạp incremental hoặc full refresh. Dữ liệu đi qua **data staging area** (slide Ch.1).

Toàn bộ ETL chạy bằng **1 lệnh**: `python src/etl/run_etl.py`, mất khoảng 12 giây (gồm cả bước kiểm tra hợp đồng nguồn và kiểm tra chất lượng).

| Bước | File | Việc làm |
|---|---|---|
| 0. Kiểm tra nguồn | `contracts.py` | Đọc từng CSV bằng CSV parser trước khi nạp. Thiếu file hoặc header sai thì **dừng hẳn**, chưa động vào CSDL. Vi phạm về giá trị được ghi thành check (§2.5) |
| 1. Extract | `01_staging.sql` + `run_etl.py` | Tạo schema `staging`, mỗi CSV một bảng, **mọi cột kiểu TEXT** (giữ nguyên nguồn); nạp hàng loạt bằng `COPY … FORMAT csv` |
| 2. Tạo schema DW | `02_dw_schema.sql` | Xoá và tạo lại schema `dw`: 4 dimension, 2 fact, index, partition; tạo `meta.etl_log` nếu chưa có |
| 3. Transform + Load | `03_transform_load.sql` | Làm sạch, ánh xạ, áp quy tắc nghiệp vụ, nạp vào dimension rồi fact |
| 4. Tổng hợp sẵn | `04_olap_views.sql` | Tạo 3 materialized view |
| 5. Metadata | `run_etl.py` | Ghi số dòng nguồn → đích của từng bảng vào `meta.etl_log` |
| 6. Kiểm tra chất lượng | `05_checks.sql` | Ghi 27 kiểm tra trên DW vào `meta.check_result` (§2.5). Cả 6 bước chạy trong **1 transaction**: lỗi thì rollback toàn bộ. Có check không đạt thì lệnh trả mã lỗi 1 |

**Các quy tắc Transform** (đều nằm trong `03_transform_load.sql`):

| Nhóm (slide Ch.2) | Quy tắc |
|---|---|
| **Data cleansing** | Đơn có nhiều review → giữ review có `review_answer_timestamp` mới nhất · danh mục rỗng → `unknown` · bổ sung bản dịch cho 2 danh mục thiếu · ép kiểu TEXT → DATE / NUMERIC / INTEGER, chuỗi rỗng → NULL |
| **Data mapping** | Danh mục PT → EN · timestamp → `date_key` (yyyymmdd) · bang → vùng · zip giữ dạng TEXT |
| **Business rules** | Khách hàng thật = `customer_unique_id`; giữ địa chỉ của đơn gần nhất · `fact_delivery` chỉ gồm đơn `delivered` có ngày giao · `is_late = 1` khi ngày giao > ngày dự kiến · review xấu = điểm ≤ 2 · item chính = item giá cao nhất (hoà thì lấy `order_item_id` nhỏ nhất) · `fact_sales` giữ mọi trạng thái đơn; các phân tích doanh thu loại `canceled` / `unavailable` |
| **Attribute construction** (slide Ch.2-cont) | `delivery_days`, `estimated_days`, `delay_days`, `is_late`, `is_bad_review`, `n_items`, `n_sellers`, `volume_cm3` = dài × rộng × cao, `region` |
| **Discretization** (dùng ở tầng phân tích) | Nhóm mức trễ: sớm > 7 ngày / sớm 1–7 / đúng ngày / trễ 1–3 / 4–7 / 8–14 / > 14 ngày |

**Load:** dùng *full refresh*: mỗi lần chạy, `staging` và `dw` được xoá và nạp lại. Cách này đơn giản và chạy lại bao nhiêu lần cũng cho cùng kết quả. *Incremental load* là hướng phát triển.

## 2.3 Thiết kế vật lý & metadata

| Kỹ thuật | Hiện thực | Mục đích |
|---|---|---|
| Surrogate key | `SERIAL` cho dim_customer / seller / product; `date_key` dạng yyyymmdd | Khoá gọn, độc lập với khoá nguồn |
| Partitioning theo thời gian (slide Ch.1) | `fact_sales` có `PARTITION BY RANGE (purchase_date_key)`, chia 3 partition 2016 / 2017 / 2018 | Truy vấn theo năm chỉ quét partition cần thiết |
| Index | Index trên các FK của 2 fact | Tăng tốc join / slice / dice |
| Materialized views | `mv_monthly_kpi`, `mv_sales_cube`, `mv_delivery_by_state` | Tổng hợp sẵn (ROLAP, Section 3.1) |
| Metadata (slide Ch.2-cont: “history of extracts”) | `meta.etl_log(run_id, step, table_name, source_rows, loaded_rows, note)` đặt ở schema riêng nên **không bị xoá** khi full refresh | Truy vết từng lần nạp |
| Metadata chất lượng | `meta.check_result(run_id, category, check_name, expected, actual, passed)` | Lưu kết quả kiểm tra của từng lần nạp |
| Lineage dữ liệu → mô hình | `models/metrics.json` lưu `etl_run_id` của lần ETL dùng để train | Trang Data Quality cảnh báo khi mô hình được train từ dữ liệu cũ |

**Số dòng mỗi partition:**

| Partition | Số dòng |
|---|---|
| fact_sales_2016 | 370 |
| fact_sales_2017 | 50,864 |
| fact_sales_2018 | 61,416 |
| **Tổng** | **112,650** |

**Dung lượng trên đĩa (gồm index):**

| Bảng | Dung lượng |
|---|---|
| fact_delivery | 24 MB |
| dim_customer | 17 MB |
| fact_sales_2018 / 2017 / 2016 | 14 MB / 11 MB / 168 kB |
| dim_product | 6.8 MB |
| dim_seller | 680 kB |
| dim_date | 144 kB |
| mv_sales_cube / mv_monthly_kpi / mv_delivery_by_state | 136 kB / 16 kB / 16 kB |

## 2.4 Kết quả ETL

**Nội dung `meta.etl_log` của lần chạy gần nhất:**

| Bước | Bảng | Dòng nguồn | Dòng nạp | Ghi chú |
|---|---|---|---|---|
| extract | staging.orders | 99,441 | 99,441 | |
| extract | staging.order_items | 112,650 | 112,650 | |
| extract | staging.order_payments | 103,886 | 103,886 | |
| extract | staging.order_reviews | 99,224 | 99,224 | |
| extract | staging.customers | 99,441 | 99,441 | |
| extract | staging.sellers | 3,095 | 3,095 | |
| extract | staging.products | 32,951 | 32,951 | |
| extract | staging.category_translation | 71 | 71 | |
| load | dw.dim_date | — | 1,096 | sinh lịch 2016–2018 |
| load | dw.dim_customer | 99,441 | 96,096 | gộp về customer_unique_id |
| load | dw.dim_seller | 3,095 | 3,095 | |
| load | dw.dim_product | 32,951 | 32,951 | |
| load | dw.fact_sales | 112,650 | 112,650 | |
| load | dw.fact_delivery | 99,441 | 96,470 | chỉ đơn delivered có ngày giao |

**Kiểm tra tính đúng đắn:**

| Kiểm tra | Kết quả |
|---|---|
| Số dòng staging = số dòng CSV (đếm bằng CSV parser) | Khớp cả 8 file |
| `SUM(price)` staging = `SUM(price)` `dw.fact_sales` | 13,591,643.70 = 13,591,643.70 ✅ |
| `fact_delivery` = số đơn delivered − số đơn delivered thiếu ngày giao | 96,478 − 8 = 96,470 ✅ |
| Chạy lại ETL lần 2 | Cùng số dòng; `etl_log` có thêm 1 lượt chạy ✅ |
| Thời gian chạy | ~5 giây cho riêng phần nạp (4.6–4.9 s, đo ngày 02/11); ~12 giây khi gồm cả kiểm tra hợp đồng nguồn và kiểm tra chất lượng (12.3 s, đo ngày 14/11) |

## 2.5 Kiểm soát chất lượng dữ liệu

Mỗi lần chạy ETL đều tự kiểm tra lại dữ liệu và lưu kết quả vào `meta.check_result`. Nhờ vậy, người dùng dashboard và mô hình DSS biết dữ liệu có đáng tin hay không mà không cần kiểm tra tay.

**Nguyên tắc.** Giá trị kỳ vọng của mỗi kiểm tra được **tính lại độc lập từ staging**, không dùng lại logic transform. Nếu tính kỳ vọng bằng chính logic transform thì một lỗi trong transform sẽ tự “khớp” với chính nó và không bị phát hiện.

**Hai lớp kiểm tra:**

| Lớp | File | Khi nào chạy | Nội dung |
|---|---|---|---|
| Hợp đồng nguồn (*source contract*) | `src/etl/contracts.py` | Trước khi nạp | Mỗi CSV phải có đúng header như mô tả; khoá có mặt và không trùng; số và thời gian đọc được; điểm review 1–5; bang là mã UF 2 chữ; zip đủ 5 chữ số |
| Kiểm tra trên DW | `src/sql/05_checks.sql` | Sau khi nạp | Grain, đối chiếu staging ↔ DW, miền giá trị, độ phủ, tổng của materialized view |

**Kết quả lần chạy 14/11/2026: 43/43 kiểm tra đạt.**

| Nhóm | Số kiểm tra | Ví dụ |
|---|---|---|
| source | 16 | Mỗi file trong 8 CSV: không vi phạm hợp đồng; số dòng CSV = số dòng staging |
| grain | 3 | Không trùng `(order_id, order_item_id)` trong `fact_sales`; không trùng `order_id` trong `fact_delivery`; không trùng `customer_unique_id` |
| reconciliation | 10 | Số dòng, `SUM(price)`, `SUM(freight_value)` giữa staging và `fact_sales`; số đơn trễ; số đơn có review |
| domain | 7 | `review_score` trong 1..5; `is_bad_review` nhất quán với điểm ≤ 2; `delay_days = delivery_days − estimated_days`; `total_value = price + freight_value` |
| coverage | 3 | Mọi ngày mua / giao nằm trong `dim_date`; mọi danh mục có tên tiếng Anh; mọi bang có vùng |
| aggregate | 4 | Tổng của `mv_sales_cube`, `mv_monthly_kpi`, `mv_delivery_by_state` khớp với fact; các tỷ lệ nằm trong [0, 1] |
| **Tổng** | **43** | |

**Trang Data Quality** trên dashboard hiển thị:
- kết quả kiểm tra theo nhóm;
- số dòng qua từng bước CSV → staging → dw;
- lịch sử các lần chạy;
- các quy tắc làm sạch đang áp dụng;
- mô hình DSS đang dùng được train từ lần ETL nào.

[HÌNH] Trang Data Quality.

**Kiểm thử tự động.** Thư mục `tests/` có 102 test (pytest), gồm unit test và test chạy trên CSDL thật. Với mỗi quy tắc nghiệp vụ, `tests/test_etl_checks.py` cố tình làm hỏng dữ liệu để xác nhận kiểm tra tương ứng báo lỗi. Lần chạy 14/11: **100 test đạt, 2 test bỏ qua**. Một test cần ETL chạy 2 lần; test còn lại chỉ chạy trong môi trường Docker.

---

# 3. OLAP & Dashboard

> **Lý thuyết (slide Ch.3).** Các phép toán OLAP gồm **roll-up** (lên cấp tổng quát hơn trong hierarchy), **drill-down** (xuống cấp chi tiết hơn), **slice** (cố định một chiều), **dice** (lọc trên nhiều chiều) và **pivot** (xoay trục). Kiến trúc OLAP server có 3 loại: **ROLAP** (lưu trên CSDL quan hệ), **MOLAP** (lưu dạng mảng đa chiều) và **HOLAP** (kết hợp hai loại trên).

## 3.1 Kiến trúc ROLAP

- Dữ liệu chi tiết nằm trong bảng quan hệ của PostgreSQL. Mỗi thao tác OLAP được dịch thành 1 câu `SELECT … GROUP BY` nối fact với các dimension, tức là kiến trúc **ROLAP**.
- Các phép tổng hợp hay dùng được **tính sẵn** bằng materialized view:

| Materialized view | Nội dung | Dùng ở |
|---|---|---|
| `mv_monthly_kpi` | Theo tháng: doanh thu, phí ship, số sản phẩm, số đơn, số đơn giao, tỷ lệ trễ, số ngày giao TB, review TB, tỷ lệ review xấu (kết hợp 2 fact) | Home |
| `mv_sales_cube` | `GROUP BY CUBE (year, customer_region, category)`: mọi tổ hợp cùng các dòng tổng phụ (NULL = “Tất cả”) | OLAP |
| `mv_delivery_by_state` | Theo bang: số đơn, tỷ lệ trễ, ngày giao TB, review TB, tỷ lệ review xấu, doanh thu | Delivery |

## 3.2 OLAP Explorer (trang OLAP)

**Định nghĩa khối dữ liệu trong ứng dụng:**

| Thành phần | Lựa chọn |
|---|---|
| Fact | `fact_sales` hoặc `fact_delivery` (2 fact dùng chung dimension → minh hoạ fact constellation) |
| Measures — fact_sales | Doanh thu (SUM price) · Phí vận chuyển (SUM) · Số sản phẩm (COUNT) · Số đơn (COUNT DISTINCT) · Giá TB / sản phẩm (AVG) |
| Measures — fact_delivery | Số đơn đã giao (COUNT) · Tỷ lệ giao trễ (%) · Số ngày giao TB · Điểm review TB · Tỷ lệ review xấu (%) |
| Hierarchy Thời gian | Năm → Quý → Tháng |
| Hierarchy Địa lý khách hàng / người bán | Vùng → Bang → Thành phố |
| Hierarchy Sản phẩm | Danh mục |

**Cách hiện thực từng phép toán:**

| Phép toán | Thao tác trên giao diện | SQL tương ứng |
|---|---|---|
| Roll-up | Nút “⬆ Roll-up” (vd. Tháng → Quý → Năm) | `GROUP BY` theo cột cấp cao hơn |
| Drill-down | Nút “⬇ Drill-down” (vd. Năm → Quý → Tháng) | `GROUP BY` theo cột cấp thấp hơn |
| Slice | Chọn “Cố định năm” = 2017 | `WHERE d.year = :year` |
| Dice | Chọn nhiều bang và nhiều danh mục | `WHERE c.state = ANY(:states) AND p.category_en = ANY(:categories)` |
| Pivot | Nút “🔄 Pivot” đổi chiều hàng ↔ cột | Đổi vai trò 2 cột trong `GROUP BY 1, 2` + `pivot_table` |

Một số chi tiết khác của trang:
- **Hiển thị:** bảng pivot kèm heatmap (khi có chiều cột), hoặc biểu đồ cột (khi chỉ có chiều hàng).
- **SQL sinh ra:** hiện trong mục “SQL được sinh ra”.
- **Additive vs non-additive:** chỉ measure additive mới có dòng / cột “Tổng”. Với measure non-additive, trang hiện ghi chú vì sao không cộng dồn được.
- **An toàn SQL:** chỉ các biểu thức có sẵn trong cấu hình (whitelist) mới được đưa vào SQL; giá trị người dùng chọn được truyền qua tham số.

[HÌNH] Mỗi phép toán một ảnh: roll-up, drill-down, slice, dice, pivot. Thêm 1 ảnh mục “SQL được sinh ra” và 1 ảnh khi chọn fact_delivery.

### 3.2.1 Ví dụ kết quả các phép toán

**Roll-up về cấp cao nhất** (doanh thu theo năm; dòng “Tất cả” do `CUBE` sinh ra). Doanh thu ở đây là tổng giá sản phẩm, loại đơn canceled / unavailable.

| Năm | Doanh thu (R$) | Số sản phẩm | Số đơn | Giá trị TB / đơn (R$) |
|---|---|---|---|---|
| 2016 | 44,726.06 | 348 | 293 | 152.65 |
| 2017 | 6,108,492.27 | 50,617 | 44,375 | 137.66 |
| 2018 | 7,341,182.41 | 61,136 | 53,531 | 137.14 |
| **Tất cả** | **13,494,400.74** | **112,101** | **98,199** | **137.42** |

*(biểu đồ: cột)*

**Drill-down Năm → Quý:**

| Quý | Doanh thu (R$) | Số đơn |
|---|---|---|
| 2016-Q3 | 207.86 | 2 |
| 2016-Q4 | 44,518.20 | 291 |
| 2017-Q1 | 733,398.94 | 5,122 |
| 2017-Q2 | 1,286,918.78 | 9,222 |
| 2017-Q3 | 1,681,949.00 | 12,445 |
| 2017-Q4 | 2,406,225.55 | 17,586 |
| 2018-Q1 | 2,764,402.78 | 20,979 |
| 2018-Q2 | 2,849,730.26 | 19,897 |
| 2018-Q3 | 1,727,049.37 | 12,655 |

Ghi chú: dữ liệu 2018-Q3 chỉ đến hết tháng 8, và tháng 9/2018 chỉ có 1 đơn.

**Drill-down tiếp 2018-Q1 → Tháng:**

| Tháng | Doanh thu (R$) |
|---|---|
| 2018-01 | 945,456.29 |
| 2018-02 | 837,895.43 |
| 2018-03 | 981,051.06 |

**Slice năm 2017, theo vùng khách hàng:**

| Vùng | Doanh thu 2017 (R$) |
|---|---|
| Southeast | 3,930,293.30 |
| South | 881,752.70 |
| Northeast | 727,528.43 |
| Central-West | 400,781.10 |
| North | 168,136.74 |

**Pivot vùng × năm** (doanh thu, R$). Đổi trục sẽ cho bảng năm × vùng.

| Vùng \ Năm | 2016 | 2017 | 2018 | Tổng |
|---|---|---|---|---|
| Southeast | 27,700.71 | 3,930,293.30 | 4,866,163.13 | 8,824,157.14 |
| South | 7,455.89 | 881,752.70 | 1,047,635.66 | 1,936,844.25 |
| Northeast | 6,013.32 | 727,528.43 | 804,697.84 | 1,538,239.59 |
| Central-West | 2,355.95 | 400,781.10 | 458,089.53 | 861,226.58 |
| North | 1,200.19 | 168,136.74 | 164,596.25 | 333,933.18 |
| **Tổng** | 44,726.06 | 6,108,492.27 | 7,341,182.41 | 13,494,400.74 |

*(biểu đồ: heatmap / cột chồng)*

**Dice: bang ∈ {SP, RJ}, danh mục ∈ {health_beauty, bed_bath_table}** (doanh thu, R$):

| Năm | Bang | bed_bath_table | health_beauty |
|---|---|---|---|
| 2016 | RJ | 59.90 | 1,237.79 |
| 2016 | SP | 29.90 | 1,079.04 |
| 2017 | RJ | 80,141.28 | 64,378.98 |
| 2017 | SP | 207,777.67 | 157,016.53 |
| 2018 | RJ | 67,562.26 | 79,176.36 |
| 2018 | SP | 270,371.52 | 302,498.32 |

**Top 10 bang theo doanh thu:**

| Bang | Doanh thu (R$) | Số đơn |
|---|---|---|
| SP | 5,165,781.70 | 41,130 |
| RJ | 1,811,484.23 | 12,698 |
| MG | 1,573,269.18 | 11,493 |
| RS | 742,639.78 | 5,415 |
| PR | 675,928.19 | 4,980 |
| SC | 518,276.28 | 3,600 |
| BA | 506,878.84 | 3,342 |
| DF | 300,085.75 | 2,117 |
| GO | 288,157.45 | 1,997 |
| ES | 273,622.03 | 2,019 |

**Top 10 danh mục theo doanh thu:**

| Danh mục | Doanh thu (R$) | Số sản phẩm | Số đơn |
|---|---|---|---|
| health_beauty | 1,255,695.13 | 9,634 | 8,800 |
| watches_gifts | 1,198,185.21 | 5,970 | 5,604 |
| bed_bath_table | 1,035,964.06 | 11,097 | 9,399 |
| sports_leisure | 979,740.92 | 8,590 | 7,673 |
| computers_accessories | 904,322.02 | 7,781 | 6,654 |
| furniture_decor | 727,465.05 | 8,298 | 6,425 |
| housewares | 626,825.80 | 6,915 | 5,847 |
| cool_stuff | 620,770.49 | 3,779 | 3,616 |
| auto | 586,585.73 | 4,204 | 3,872 |
| garden_tools | 481,009.94 | 4,328 | 3,505 |

## 3.3 Dashboard Home & Delivery

### 3.3.1 Home — KPI tổng

| KPI | Giá trị |
|---|---|
| Doanh thu (giá sản phẩm, loại canceled / unavailable) | R$ 13,494,400.74 |
| Phí vận chuyển | R$ 2,241,126.29 |
| Số đơn hàng | 98,199 |
| Số sản phẩm bán | 112,101 |
| Giá trị TB / đơn | R$ 137.42 |
| Khách hàng có mua / người bán có bán / sản phẩm đã bán | 95,420 / 3,095 / 32,951 |
| Số đơn đã giao | 96,470 |
| Tỷ lệ giao trễ | 6.77% |
| Số ngày giao TB / số ngày dự kiến TB | 12.50 / 24.37 ngày |
| Điểm review TB | 4.156 ★ |
| Tỷ lệ review xấu (≤ 2★) | 12.81% |
| Đơn đã giao không có review | 646 |

[HÌNH] Trang Home.

### 3.3.2 Home — Xu hướng theo tháng

Dashboard chỉ vẽ giai đoạn 2017-01 → 2018-08, vì các tháng ở hai đầu có rất ít đơn (2016-09: 2 đơn, 2016-12: 1 đơn, 2018-09: 1 đơn; tháng 2016-11 không có đơn).

| Tháng | Doanh thu (R$) | Số đơn | Đơn đã giao | Tỷ lệ trễ | Ngày giao TB | Review TB | Tỷ lệ review xấu |
|---|---|---|---|---|---|---|---|
| 2016-10 | 44,507.30 | 290 | 265 | 0.75% | 19.63 | 4.011 | 16.41% |
| 2017-01 | 120,098.27 | 787 | 750 | 2.93% | 12.75 | 4.198 | 12.01% |
| 2017-02 | 244,959.35 | 1,718 | 1,653 | 2.96% | 13.30 | 4.203 | 11.08% |
| 2017-03 | 368,341.32 | 2,617 | 2,546 | 4.56% | 13.04 | 4.187 | 11.24% |
| 2017-04 | 353,842.98 | 2,377 | 2,303 | 6.56% | 15.02 | 4.135 | 12.93% |
| 2017-05 | 503,159.19 | 3,640 | 3,545 | 2.99% | 11.43 | 4.236 | 10.07% |
| 2017-06 | 429,916.61 | 3,205 | 3,135 | 3.03% | 12.01 | 4.223 | 10.74% |
| 2017-07 | 492,287.30 | 3,946 | 3,872 | 2.79% | 11.49 | 4.260 | 9.94% |
| 2017-08 | 568,245.79 | 4,272 | 4,193 | 2.91% | 11.02 | 4.313 | 9.39% |
| 2017-09 | 621,415.91 | 4,227 | 4,150 | 4.39% | 11.72 | 4.268 | 10.27% |
| 2017-10 | 660,179.62 | 4,547 | 4,478 | 4.18% | 11.73 | 4.205 | 11.07% |
| 2017-11 | 1,003,862.14 | 7,421 | 7,288 | 12.40% | 15.07 | 3.989 | 16.57% |
| 2017-12 | 742,183.79 | 5,618 | 5,513 | 7.46% | 15.31 | 4.088 | 14.43% |
| 2018-01 | 945,456.29 | 7,187 | 7,069 | 5.70% | 14.01 | 4.109 | 13.70% |
| 2018-02 | 837,895.43 | 6,624 | 6,555 | 14.13% | 16.87 | 3.881 | 19.38% |
| 2018-03 | 981,051.06 | 7,168 | 7,003 | 18.96% | 16.24 | 3.813 | 21.17% |
| 2018-04 | 993,592.98 | 6,919 | 6,798 | 4.50% | 11.42 | 4.206 | 11.79% |
| 2018-05 | 992,871.75 | 6,833 | 6,749 | 6.56% | 11.34 | 4.236 | 10.76% |
| 2018-06 | 863,265.53 | 6,145 | 6,096 | 1.16% | 9.16 | 4.307 | 9.98% |
| 2018-07 | 878,044.27 | 6,233 | 6,156 | 3.38% | 8.89 | 4.317 | 9.68% |
| 2018-08 | 848,860.10 | 6,421 | 6,351 | 6.19% | 7.66 | 4.310 | 9.54% |

*(biểu đồ: cột doanh thu + đường tỷ lệ trễ và tỷ lệ review xấu)*

**Insight:**
- Tỷ lệ trễ và tỷ lệ review xấu **tăng giảm cùng nhau**. Hai đỉnh là 11/2017 (trễ 12.4% → review xấu 16.6%; tháng có Black Friday, số đơn tăng vọt lên 7,421) và 02–03/2018 (trễ 14.1–19.0% → review xấu 19.4–21.2%).
- Các tháng trễ thấp (06/2018: 1.16%) có tỷ lệ review xấu thấp nhất (~10%).

### 3.3.3 Delivery — Review theo mức độ trễ (discretization)

| Giao so với ngày dự kiến | Số đơn | Review TB | Tỷ lệ review xấu |
|---|---|---|---|
| Sớm > 7 ngày | 71,303 | 4.317 | 8.97% |
| Sớm 1–7 ngày | 17,341 | 4.201 | 10.24% |
| Đúng ngày | 1,292 | 4.034 | 12.42% |
| Trễ 1–3 ngày | 1,870 | 3.291 | 32.13% |
| Trễ 4–7 ngày | 1,802 | 2.103 | 67.68% |
| Trễ 8–14 ngày | 1,478 | 1.671 | 80.15% |
| Trễ > 14 ngày | 1,384 | 1.724 | 78.35% |

*(biểu đồ: cột — đây là biểu đồ “đắt” nhất để thuyết trình)*

**Phân bố điểm review: đúng hạn vs trễ** (đơn có review):

| Điểm | Đúng hạn | Trễ |
|---|---|---|
| 1★ | 5,920 | 3,431 |
| 2★ | 2,369 | 552 |
| 3★ | 7,222 | 694 |
| 4★ | 18,239 | 649 |
| 5★ | 55,693 | 1,055 |
| Tổng | 89,443 | 6,381 |

*(biểu đồ: cột chồng 100%)* Với đơn trễ, **53.8%** là 1★ (3,431 / 6,381). Với đơn đúng hạn, **62.3%** là 5★ (55,693 / 89,443).

### 3.3.4 Delivery — Theo vùng và theo bang

| Vùng khách hàng | Số đơn | Tỷ lệ trễ | Ngày giao TB | Review TB | Tỷ lệ review xấu |
|---|---|---|---|---|---|
| Northeast | 9,045 | 12.71% | 19.94 | 3.970 | 16.74% |
| North | 1,797 | 8.57% | 22.54 | 4.031 | 15.17% |
| Central-West | 5,619 | 6.50% | 14.95 | 4.129 | 13.12% |
| Southeast | 66,197 | 6.12% | 10.69 | 4.179 | 12.38% |
| South | 13,812 | 5.90% | 13.98 | 4.191 | 11.82% |

**Theo bang** (sắp theo tỷ lệ trễ giảm dần):

| Bang | Vùng | Số đơn | Tỷ lệ trễ | Ngày giao TB | Review TB | Tỷ lệ review xấu |
|---|---|---|---|---|---|---|
| AL | Northeast | 397 | 21.41% | 24.50 | 3.848 | 21.32% |
| MA | Northeast | 720 | 17.36% | 21.48 | 3.835 | 19.86% |
| SE | Northeast | 336 | 15.18% | 21.42 | 3.907 | 18.86% |
| PI | Northeast | 476 | 13.87% | 19.39 | 3.994 | 16.14% |
| CE | Northeast | 1,281 | 13.74% | 21.18 | 3.946 | 17.10% |
| RR | North | 41 | 12.20% | 29.34 | 3.902 | 14.63% |
| BA | Northeast | 3,254 | 12.17% | 19.28 | 3.931 | 17.01% |
| RJ | Southeast | 12,351 | 12.11% | 15.24 | 3.965 | 18.33% |
| PA | North | 946 | 11.21% | 23.73 | 3.914 | 17.90% |
| ES | Southeast | 1,996 | 10.72% | 15.73 | 4.079 | 13.81% |
| PB | Northeast | 515 | 10.29% | 20.37 | 4.082 | 14.71% |
| TO | North | 274 | 9.85% | 17.60 | 4.154 | 12.09% |
| MS | Central-West | 700 | 9.71% | 15.54 | 4.160 | 13.32% |
| PE | Northeast | 1,592 | 9.67% | 18.38 | 4.080 | 14.89% |
| RN | Northeast | 474 | 9.28% | 19.22 | 4.151 | 12.95% |
| SC | South | 3,547 | 8.20% | 14.90 | 4.135 | 12.95% |
| GO | Central-West | 1,956 | 6.49% | 15.53 | 4.106 | 13.16% |
| MT | Central-West | 886 | 6.09% | 18.01 | 4.147 | 12.74% |
| RS | South | 5,344 | 6.08% | 15.25 | 4.185 | 11.92% |
| DF | Central-West | 2,077 | 5.58% | 12.89 | 4.134 | 13.16% |
| MG | Southeast | 11,351 | 4.58% | 11.95 | 4.192 | 11.76% |
| SP | Southeast | 40,499 | 4.49% | 8.70 | 4.246 | 10.69% |
| PR | South | 4,921 | 4.04% | 11.94 | 4.239 | 10.90% |
| AC | North | 80 | 3.75% | 21.00 | 4.088 | 15.00% |
| AP | North | 67 | 2.99% | 27.18 | 4.242 | 6.06% |
| RO | North | 244 | 2.87% | 19.28 | 4.165 | 11.93% |
| AM | North | 145 | 2.76% | 26.36 | 4.243 | 13.19% |

*(biểu đồ: cột tỷ lệ trễ theo bang, tô màu theo tỷ lệ review xấu)*

**Insight:**
- Vùng Northeast trễ nhiều nhất (12.7%).
- **RJ** đáng chú ý: là bang lớn thứ 2 (12,351 đơn) nhưng trễ 12.1% và có tỷ lệ review xấu cao nhất trong nhóm bang lớn (18.3%).
- SP giao nhanh nhất (8.7 ngày) và ít trễ (4.5%).

### 3.3.5 Delivery — Theo danh mục (≥ 500 đơn, sắp theo tỷ lệ review xấu)

| Danh mục | Số đơn | Tỷ lệ trễ | Review TB | Tỷ lệ review xấu |
|---|---|---|---|---|
| office_furniture | 1,251 | 8.07% | 3.647 | 21.92% |
| unknown | 1,358 | 7.14% | 4.041 | 16.53% |
| bed_bath_table | 9,184 | 7.48% | 4.008 | 15.82% |
| furniture_decor | 6,188 | 7.24% | 4.078 | 14.85% |
| computers_accessories | 6,511 | 6.40% | 4.083 | 14.51% |
| telephony | 4,073 | 7.14% | 4.059 | 13.93% |
| baby | 2,761 | 8.11% | 4.122 | 13.76% |
| watches_gifts | 5,476 | 7.41% | 4.123 | 13.65% |
| electronics | 2,502 | 7.67% | 4.129 | 13.05% |
| auto | 3,792 | 7.33% | 4.153 | 12.80% |
| construction_tools_construction | 724 | 7.46% | 4.152 | 12.66% |
| garden_tools | 3,400 | 6.62% | 4.200 | 11.74% |
| perfumery | 3,069 | 6.58% | 4.268 | 11.57% |
| housewares | 5,680 | 5.42% | 4.204 | 11.57% |
| musical_instruments | 608 | 7.57% | 4.243 | 11.46% |
| health_beauty | 8,613 | 7.54% | 4.233 | 11.35% |
| small_appliances | 606 | 4.79% | 4.266 | 11.31% |
| toys | 3,787 | 6.42% | 4.240 | 11.31% |
| sports_leisure | 7,492 | 6.59% | 4.235 | 11.20% |
| consoles_games | 1,013 | 6.12% | 4.182 | 11.06% |
| home_appliances | 747 | 4.42% | 4.212 | 11.02% |
| cool_stuff | 3,530 | 5.92% | 4.230 | 10.91% |
| pet_shop | 1,682 | 5.05% | 4.275 | 10.57% |
| fashion_bags_accessories | 1,811 | 5.58% | 4.243 | 10.09% |
| stationery | 2,244 | 6.60% | 4.307 | 9.68% |
| luggage_accessories | 1,012 | 4.25% | 4.371 | 8.13% |

**Insight:** khác biệt giữa các danh mục về tỷ lệ trễ nhỏ hơn nhiều so với khác biệt giữa các bang (4.2–8.1% so với 2.8–21.4%). Tuy vậy, office_furniture có tỷ lệ review xấu rất cao (21.9%) dù tỷ lệ trễ chỉ trung bình. Điều này cho thấy còn nguyên nhân khác ngoài giao hàng (hàng cồng kềnh, lắp ráp…).

### 3.3.6 Phân tích bổ sung (dữ liệu đầu vào cho DSS)

**Ảnh hưởng của số sản phẩm và số người bán trong đơn** (đơn có review):

| Số SP trong đơn | Người bán | Trễ? | Số đơn | Tỷ lệ review xấu |
|---|---|---|---|---|
| 1 | 1 | Không | 80,407 | 7.55% |
| 1 | 1 | Có | 5,889 | 62.10% |
| 2 | 1 | Không | 6,000 | 19.72% |
| 2 | 1 | Có | 373 | 65.42% |
| 2 | Nhiều | Không | 935 | 45.35% |
| 2 | Nhiều | Có | 11 | 72.73% |
| ≥3 | 1 | Không | 1,787 | 25.35% |
| ≥3 | 1 | Có | 107 | 68.22% |
| ≥3 | Nhiều | Không | 314 | 51.59% |
| ≥3 | Nhiều | Có | 1 | 100.00% |

**Insight:** đơn có **nhiều người bán** có tỷ lệ review xấu 45–52% **ngay cả khi giao đúng hạn**. Nguyên nhân có thể là hàng về thành nhiều lần, hoặc khách đánh giá ngay khi mới nhận được một phần đơn.

**Người bán và khách cùng bang hay khác bang:**

| Cùng bang? | Số đơn | Ngày giao TB | Tỷ lệ trễ | Tỷ lệ review xấu |
|---|---|---|---|---|
| Khác bang | 61,776 | 15.09 | 8.05% | 14.12% |
| Cùng bang | 34,694 | 7.89 | 4.51% | 10.47% |

---

# 4. Hệ hỗ trợ quyết định (DSS)

> **Lý thuyết (slide Ch.4–8).**
> - DSS là *“a computer-based system that supports decision-making activities by integrating data, sophisticated analytical models, and user-friendly software tools”* (Ch.6).
> - Các subsystem: **data management, model management, user interface (dialog)**, và knowledge-based (tuỳ chọn).
> - Quá trình ra quyết định của Simon gồm các pha **intelligence, design, choice, implementation** (và **evaluation**) (Ch.5-cont).
> - Mô hình gồm **decision variables, uncontrollable variables, result variables**, và được xây trong điều kiện **certainty / risk / uncertainty** (Ch.7).

## 4.1 Phân loại, kiến trúc và quá trình ra quyết định

**Phân loại (slide Ch.4):** **Hybrid DSS**, gồm hai phần:
- **data-driven:** truy vấn và OLAP trên kho dữ liệu;
- **model-driven:** cây quyết định cùng các phân tích what-if, sensitivity, goal seeking, và mô hình tối ưu (mathematical programming) để phân bổ ngân sách.

Theo phân loại của Holsapple & Whinston (slide Ch.6), đây là dạng *compound DSS*, kết hợp database-oriented và solver-oriented.

**Kiến trúc subsystem** (theo ví dụ “business analytics DSS” trong slide Ch.6):

| Subsystem | Hiện thực trong project |
|---|---|
| Data management | Kho dữ liệu PostgreSQL (schema `dw`): `fact_delivery` cùng các dimension, nạp bằng ETL (Section 2) |
| Model management | `src/dss/train_model.py` (cây quyết định, model base lưu ở `models/`) · `src/dss/whatif.py` (what-if, sensitivity, goal seeking, xếp hạng) · `src/dss/optimizer.py` (tối ưu ngân sách, phân tích độ vững) · `config/cost_assumptions.csv` (giả định chi phí) |
| User interface (dialog) | Trang DSS trên Streamlit, gồm 5 tab: chọn phạm vi, kéo thanh trượt, nhập mục tiêu, nhập ngân sách và giả định, xem bảng và biểu đồ |
| Knowledge-based (tuỳ chọn) | Tập luật IF-THEN rút ra từ cây quyết định, dùng để giải thích cho người quản lý |

**Vai trò của DW trong DSS** (L.O.1.2): DW là *data management subsystem*. Nó cung cấp dữ liệu đã tích hợp và làm sạch, đúng grain (đơn hàng), cho cả phần OLAP (data-driven) lẫn mô hình (model-driven). Nếu không có bước chuẩn hoá ở DW, mô hình sẽ bị sai vì review trùng, đơn nhiều item, hoặc thiếu ngày giao.

**Ánh xạ quá trình ra quyết định của Simon:**

| Pha | Câu hỏi | Công cụ trong hệ thống | Kết quả |
|---|---|---|---|
| Intelligence | Có vấn đề gì? Ở đâu? | Home, OLAP, Delivery | Giao trễ → review xấu; Northeast và RJ trễ nhiều; đỉnh 11/2017 và 02–03/2018 |
| Design | Mô hình hoá vấn đề, liệt kê phương án | DSS tab 1: cây quyết định và luật | Các nhóm đơn rủi ro cao; biến quyết định = mức giảm trễ, số ngày rút ngắn |
| Choice | Chọn phương án | DSS tab 2–5: xếp hạng, what-if, sensitivity, goal seeking, tối ưu ngân sách | Ưu tiên RJ, GO, PR, RN ở mọi bộ giả định chi phí; cần giảm 58% đơn trễ để đạt 11% |
| Implementation | Hành động gì? | Khung “Đề xuất” tự sinh ở tab 2 và tab 5 | Phân bổ ngân sách theo bang, đổi / thêm đơn vị vận chuyển, nới ngày giao dự kiến cho sát thực tế |
| Evaluation | Mô hình tin được đến đâu? | Metrics, confusion matrix, thực nghiệm chọn tham số, kiểm tra trên tập test (tab 1); độ nhạy theo giả định chi phí (tab 5) | Section 4.2.4, 4.3, 4.4.7 và Section 5 |

[HÌNH] 5 tab của trang DSS.

## 4.2 Mô hình cây quyết định

### 4.2.1 Dữ liệu và thuộc tính

- **Tập dữ liệu:** các đơn trong `fact_delivery` **có review**, tổng **95,824 đơn** (đã loại 646 đơn không có review). Tỷ lệ review xấu là **12.81%**. Trong tập này, tỷ lệ trễ là 6.66% (6,381 đơn).
- **Biến mục tiêu:** `is_bad_review` (1 nếu điểm ≤ 2).
- **Chia dữ liệu:** train 76,659 / test 19,165 (80/20, stratified, `random_state = 42`).

| Thuộc tính | Nguồn | Ý nghĩa |
|---|---|---|
| is_late | fact_delivery | Có trễ không |
| delay_days | fact_delivery | Số ngày trễ (âm = sớm) |
| delivery_days | fact_delivery | Số ngày giao thực tế |
| estimated_days | fact_delivery | Số ngày giao dự kiến |
| n_items | fact_delivery | Số sản phẩm trong đơn |
| n_sellers | fact_delivery | Số người bán trong đơn |
| freight_ratio | freight_total / order_value | Tỷ lệ phí ship so với giá trị đơn |
| same_state | dim_customer.state = dim_seller.state | Người bán và khách cùng bang |
| region_* (5 cột) | dim_customer.region (one-hot) | Vùng của khách |

### 4.2.2 Thuật toán và cấu hình

Thuật toán là cây quyết định với tiêu chí **entropy / information gain**, thuộc họ ID3 / C4.5. Đây là thuật toán có ví dụ tính tay trong slide Ch.5 (bộ dữ liệu *buys_computer*).

| Tham số | Giá trị | Lý do |
|---|---|---|
| criterion | entropy | Dùng information gain như trong lecture |
| max_depth | 4 | Cây nhỏ, dễ giải thích |
| min_samples_leaf | 200 | Mỗi lá đủ lớn để tỷ lệ trong lá có ý nghĩa thống kê |
| class_weight | balanced | Review xấu là lớp thiểu số (12.8%) |
| random_state | 42 | Tái lập kết quả |

Cây thu được có **độ sâu 4 và 15 lá**.

**Thực nghiệm chọn tham số.** Nhóm so sánh 12 cấu hình `max_depth` ∈ {3, 4, 5, 6} × `min_samples_leaf` ∈ {100, 200, 500} bằng **cross-validation 5-fold (stratified) trên tập train**. Tập test không được dùng ở bước này, để nó vẫn là phép kiểm tra cuối cùng khách quan. Cây được dùng theo hai cách, nên nhóm đo hai loại chỉ số:
- chỉ số **phân loại** (accuracy, precision, recall, F1 của lớp review xấu);
- chỉ số **chất lượng xác suất**, vì what-if dùng tỷ lệ của lá làm xác suất: AUC (càng cao càng tốt) và Brier score (càng thấp càng tốt).

| max_depth | min_samples_leaf | Số lá | Accuracy | Precision | Recall | F1 | AUC | Brier |
|---|---|---|---|---|---|---|---|---|
| 3 | 100 / 200 / 500 | 8 | 83.76% | 39.99% | 50.73% | 0.445 | 0.7307 | 0.0876–0.0878 |
| **4** | **200** | **15** | **80.69%** | **34.43%** | **56.04%** | **0.426** | **0.7408** | **0.0874** |
| 4 | 100 / 500 | 15 / 14 | 80.69% | 34.43% | 56.04% | 0.426 | 0.7407–0.7408 | 0.0874–0.0876 |
| 5 | 100 / 200 / 500 | 26 / 24 / 21 | 81.15–81.27% | 35.29–35.46% | 54.87–55.06% | 0.429–0.430 | 0.7435–0.7436 | 0.0872–0.0874 |
| 6 | 100 / 200 / 500 | 44 / 39 / 31 | 82.16–82.20% | 36.80–36.85% | 53.78–54.07% | 0.437–0.438 | 0.7455–0.7456 | 0.0871–0.0873 |

*(nguồn: `models/experiments.json`; trung bình 5 fold)*

**Lý do giữ depth 4 / leaf 200:**
- Depth 3 có F1 cao nhất nhưng AUC thấp nhất. Cây chỉ có 8 lá thì phân nhóm rủi ro quá thô cho what-if.
- Depth 5–6 chỉ tăng AUC thêm khoảng 0.003–0.005 nhưng số lá tăng gấp 2–3 lần, nên khó giải thích bằng luật IF-THEN hơn.
- Với depth 4, `min_samples_leaf` gần như không đổi kết quả. Chọn 200 để mỗi lá đủ lớn.

### 4.2.3 Ví dụ tính information gain (theo công thức slide Ch.5)

Bảng đếm (95,824 đơn có review):

| is_late | Số đơn | Review xấu | Review tốt |
|---|---|---|---|
| 0 | 89,443 | 8,289 | 81,154 |
| 1 | 6,381 | 3,983 | 2,398 |
| **Tổng (D)** | **95,824** | **12,272** | **83,552** |

Các bước tính:
- Info(D) = −(12,272/95,824)·log₂(12,272/95,824) − (83,552/95,824)·log₂(83,552/95,824) = **0.5521**
- Info(D | is_late = 0) = −(8,289/89,443)·log₂(8,289/89,443) − (81,154/89,443)·log₂(81,154/89,443) = **0.4453**
- Info(D | is_late = 1) = −(3,983/6,381)·log₂(3,983/6,381) − (2,398/6,381)·log₂(2,398/6,381) = **0.9550**
- Info_is_late(D) = (89,443/95,824)·0.4453 + (6,381/95,824)·0.9550 = **0.4793**
- **Gain(is_late) = 0.5521 − 0.4793 = 0.0728 bit**

So sánh với các thuộc tính khác (tính cùng công thức):

| Thuộc tính | Gain (bit) |
|---|---|
| is_late | 0.0728 |
| n_sellers > 1 | 0.0068 |
| region (5 vùng) | 0.0011 |

**Nhận xét:**
- Giao trễ mang thông tin gấp khoảng **10 lần** số người bán và gấp khoảng **66 lần** vùng địa lý.
- Trên cây thực tế, thuộc tính được chọn ở gốc là `delay_days` (dạng liên tục, ngưỡng 1.5 ngày), không phải `is_late`. Lý do: ngưỡng tối ưu tách tốt hơn ngưỡng 0, vì đơn chỉ trễ 1 ngày chưa bị phạt nặng. Vì vậy độ quan trọng của `is_late` trên cây bằng 0.

### 4.2.4 Kết quả đánh giá (tập test, 19,165 đơn)

| Chỉ số | Giá trị |
|---|---|
| Accuracy | 79.67% |
| Precision (lớp review xấu) | 32.95% |
| Recall (lớp review xấu) | 56.76% |
| F1 (lớp review xấu) | 0.417 |

**Confusion matrix:**

| | Dự đoán: tốt | Dự đoán: xấu |
|---|---|---|
| **Thực tế: tốt** | 13,876 (TN) | 2,835 (FP) |
| **Thực tế: xấu** | 1,061 (FN) | 1,393 (TP) |

**Độ quan trọng của thuộc tính:**

| Thuộc tính | Importance |
|---|---|
| delay_days | 0.7160 |
| n_items | 0.1936 |
| delivery_days | 0.0689 |
| n_sellers | 0.0215 |
| is_late, estimated_days, freight_ratio, same_state, region_* | 0 |

*(biểu đồ: cột ngang)*

**Diễn giải:**
- Mô hình bắt được khoảng 57% đơn bị review xấu chỉ từ dữ liệu giao hàng.
- Precision thấp là điều có thể dự đoán trước. Review xấu còn do nhiều nguyên nhân không có trong dữ liệu (chất lượng sản phẩm, sai mô tả…).
- Mục đích chính của cây trong DSS là **phân nhóm rủi ro và giải thích**, không phải dự đoán từng đơn.

### 4.2.5 Luật IF-THEN (15 lá, sắp theo rủi ro)

P = tỷ lệ review xấu thực tế của nhóm trên tập train; n = số đơn train trong nhóm.

| # | IF | P(review xấu) | n |
|---|---|---|---|
| 1 | 5.5 < delay_days ≤ 34.5 | 79.73% | 2,684 |
| 2 | 4.5 < delay_days ≤ 5.5 | 64.23% | 355 |
| 3 | delay_days > 34.5 | 61.76% | 204 |
| 4 | 2.5 < delay_days ≤ 4.5 AND delivery_days > 22.5 | 57.46% | 496 |
| 5 | delay_days ≤ 1.5 AND n_items > 1.5 AND n_sellers > 1.5 AND delivery_days > 11.5 | 54.10% | 244 |
| 6 | 2.5 < delay_days ≤ 4.5 AND delivery_days ≤ 22.5 | 48.57% | 245 |
| 7 | delay_days ≤ 1.5 AND n_items > 1.5 AND n_sellers > 1.5 AND delivery_days ≤ 11.5 | 45.55% | 764 |
| 8 | 1.5 < delay_days ≤ 2.5 AND freight_ratio ≤ 0.23 | 35.87% | 223 |
| 9 | 1.5 < delay_days ≤ 2.5 AND freight_ratio > 0.23 | 33.66% | 202 |
| 10 | delay_days ≤ 1.5 AND n_items > 1.5 AND n_sellers ≤ 1.5 AND delivery_days > 7.5 | 24.22% | 4,113 |
| 11 | delay_days ≤ 1.5 AND n_items ≤ 1.5 AND delivery_days > 21.5 | 15.23% | 4,734 |
| 12 | delay_days ≤ 1.5 AND n_items > 1.5 AND n_sellers ≤ 1.5 AND delivery_days ≤ 7.5 | 14.78% | 2,138 |
| 13 | delay_days ≤ 1.5 AND n_items ≤ 1.5 AND 16.5 < delivery_days ≤ 21.5 | 9.64% | 6,993 |
| 14 | delay_days ≤ 1.5 AND n_items ≤ 1.5 AND 9.5 < delivery_days ≤ 16.5 | 7.72% | 21,784 |
| 15 | delay_days ≤ 1.5 AND n_items ≤ 1.5 AND delivery_days ≤ 9.5 | 6.05% | 31,480 |

**Tri thức rút ra (knowledge):**
1. Trễ từ khoảng 5 ngày trở lên → khoảng 62–80% bị review xấu (luật 1–3).
2. Trễ 2–4 ngày → 34–57%. Rủi ro tăng nếu tổng thời gian giao dài (luật 4, 6, 8, 9).
3. Đơn **nhiều sản phẩm từ nhiều người bán** → 46–54% dù không trễ (luật 5, 7).
4. Đơn 1 sản phẩm, đúng hạn, giao ≤ 9.5 ngày → chỉ khoảng 6% (luật 15). Đây là nhóm lớn nhất, chiếm 31,480 / 76,659 đơn train.
5. Kể cả khi đúng hạn, giao càng lâu thì rủi ro càng tăng: 6.05% (≤ 9.5 ngày) → 7.72% (9.5–16.5) → 9.64% (16.5–21.5) → 15.23% (> 21.5 ngày) (luật 15 → 14 → 13 → 11).

## 4.3 Mô hình rủi ro và các biến

**Mô hình under risk (slide Ch.7).** Mỗi đơn được gán một **xác suất** bị review xấu, bằng tỷ lệ review xấu thực tế của lá mà đơn rơi vào (`leaf_rate`). Tỷ lệ review xấu kỳ vọng của một nhóm là trung bình các xác suất đó.
- Không dùng `predict_proba`, vì `class_weight = balanced` làm lệch xác suất.
- Kiểm tra độ khớp: tỷ lệ kỳ vọng do mô hình ước lượng là **12.85%**, tỷ lệ thực tế là **12.81%**.
- **Kiểm tra trên tập test** (19,165 đơn mà mô hình chưa thấy khi train):
  - Số review xấu kỳ vọng tính theo `leaf_rate` của tập train là **2,497.6**, số thực tế là **2,454** (lệch 1.8%).
  - So từng lá, tỷ lệ trên tập test lệch trung bình (có trọng số theo số đơn) **0.6 điểm %** so với tập train.
  - Kết luận: xác suất theo lá không bị overfit và dùng được cho what-if. Số liệu nằm ở `leaf_check` trong `models/metrics.json`.

| Loại biến (slide Ch.7) | Trong mô hình |
|---|---|
| Decision variables | `late_reduction`: % số đơn trễ được làm cho đúng hạn (0–100%) · `days_faster`: số ngày rút ngắn cho mọi đơn (0–10) · phạm vi áp dụng: toàn quốc / 1 bang / 1 danh mục |
| Uncontrollable variables | Hành vi chấm điểm của khách hàng, phản ánh qua `leaf_rate` · số sản phẩm và số người bán trong đơn |
| Result variables | Tỷ lệ review xấu kỳ vọng · số review xấu tránh được · tỷ lệ trễ sau can thiệp |

**Cách mô phỏng** (`whatif.simulate`):
- **`days_faster = N`:** trừ N ngày vào `delivery_days` của mọi đơn trong phạm vi, rồi tính lại `delay_days` và `is_late`.
- **`late_reduction = X`:** chọn X% số đơn đang trễ trong phạm vi và cho giao **đúng ngày dự kiến**, tức `delivery_days = estimated_days`, `delay_days = 0`, `is_late = 0`.
  - Đơn được chọn dựa trên một số ngẫu nhiên cố định cho mỗi đơn (seed 42). Nhờ vậy kết quả tái lập được, và tập đơn được sửa ở mức X% lớn luôn chứa tập ở mức nhỏ hơn. Do đó tỷ lệ kỳ vọng giảm **đơn điệu**.
- Sau khi mô phỏng, đưa dữ liệu qua cây để lấy xác suất mới, rồi so sánh với trước khi can thiệp.

## 4.4 Các công cụ ra quyết định

### 4.4.1 What-if analysis — Toàn quốc, biến quyết định `late_reduction`

| Giảm % đơn trễ | Tỷ lệ trễ sau | Tỷ lệ review xấu kỳ vọng | Review xấu tránh được |
|---|---|---|---|
| 0% | 6.66% | 12.85% | 0 |
| 10% | 6.02% | 12.53% | 307 |
| 25% | 5.00% | 12.04% | 781 |
| 50% | 3.35% | 11.24% | 1,549 |
| 75% | 1.68% | 10.44% | 2,307 |
| 100% | 0.00% | 9.63% | 3,085 |

### 4.4.2 What-if analysis — Toàn quốc, biến quyết định `days_faster`

| Rút ngắn (ngày) | Tỷ lệ trễ sau | Tỷ lệ review xấu kỳ vọng | Review xấu tránh được |
|---|---|---|---|
| 0 | 6.66% | 12.85% | 0 |
| 1 | 5.80% | 12.26% | 564 |
| 2 | 5.24% | 11.72% | 1,083 |
| 3 | 4.73% | 11.23% | 1,559 |
| 5 | 3.82% | 10.38% | 2,369 |
| 7 | 2.90% | 9.72% | 2,997 |
| 10 | 2.11% | 9.06% | 3,635 |

**Nhận xét:** rút ngắn 3 ngày cho mọi đơn cho hiệu quả tương đương việc sửa 50% đơn trễ (khoảng 1,550 review xấu tránh được). Rút ngắn từ 7 ngày trở lên hiệu quả hơn cả sửa 100% đơn trễ, vì còn giảm rủi ro của các đơn đúng hạn nhưng giao lâu (tri thức 5 ở Section 4.2.5).

### 4.4.3 What-if analysis — Phạm vi bang RJ (12,212 đơn có review)

| Kịch bản | Tỷ lệ trễ RJ | Review xấu kỳ vọng RJ | Review xấu tránh được | Review xấu kỳ vọng toàn quốc |
|---|---|---|---|---|
| Hiện tại | 11.93% | 16.62% (thực tế 18.33%) | 0 | 12.85% |
| Giảm 30% đơn trễ | 8.25% | 14.67% | 238 | 12.60% |
| Giảm 50% đơn trễ | 5.86% | 13.38% | 395 | 12.44% |
| Giảm 100% đơn trễ | 0.00% | 10.33% | 769 | 12.05% |
| Rút ngắn 3 ngày | 9.52% | 14.63% | 244 | 12.60% |
| Giảm 50% + rút ngắn 3 ngày | 4.67% | 12.06% | 557 | 12.27% |

Ghi chú: ở RJ, mô hình ước lượng thấp hơn thực tế (16.62% so với 18.33%). Nghĩa là RJ còn những yếu tố gây review xấu nằm ngoài các thuộc tính của mô hình.

### 4.4.4 Sensitivity analysis

Tỷ lệ review xấu kỳ vọng thay đổi theo mức giảm đơn trễ:

| Giảm % đơn trễ | Toàn quốc: tỷ lệ trễ | Toàn quốc: review xấu | RJ: tỷ lệ trễ | RJ: review xấu |
|---|---|---|---|---|
| 0% | 6.66% | 12.85% | 11.93% | 16.62% |
| 10% | 6.02% | 12.53% | 10.85% | 16.03% |
| 20% | 5.32% | 12.20% | 9.51% | 15.33% |
| 30% | 4.66% | 11.87% | 8.25% | 14.67% |
| 40% | 3.99% | 11.54% | 7.05% | 14.04% |
| 50% | 3.35% | 11.24% | 5.86% | 13.38% |
| 60% | 2.67% | 10.91% | 4.71% | 12.80% |
| 70% | 2.01% | 10.60% | 3.47% | 12.16% |
| 80% | 1.31% | 10.27% | 2.19% | 11.50% |
| 90% | 0.67% | 9.95% | 1.16% | 10.93% |
| 100% | 0.00% | 9.63% | 0.00% | 10.33% |

*(biểu đồ: 2 đường)*

**Nhận xét:**
- Quan hệ gần như **tuyến tính**. Mỗi 10% đơn trễ được sửa làm giảm khoảng 0.32 điểm % review xấu ở toàn quốc, và khoảng 0.63 điểm % ở RJ.
- Đầu tư vào RJ cho hiệu quả trên mỗi đơn **gấp khoảng 2 lần** so với đầu tư dàn trải toàn quốc.
- Ngay cả khi hết hoàn toàn giao trễ, toàn quốc vẫn còn 9.63% review xấu. Đây là phần **không giải quyết được bằng logistics**.

### 4.4.5 Goal seeking

Hệ thống duyệt `late_reduction` từ 0% đến 100%, mỗi bước 1%. Đây là *complete enumeration* (blind search, slide Ch.7). Kết quả trả về là mức nhỏ nhất đạt mục tiêu.

**Toàn quốc** (hiện tại 12.85%):

| Mục tiêu review xấu ≤ | Cần giảm % đơn trễ | Tỷ lệ trễ sau | Review xấu kỳ vọng | Review xấu tránh được |
|---|---|---|---|---|
| 12.5% | 11% | 5.94% | 12.49% | 344 |
| 12.0% | 27% | 4.87% | 11.98% | 840 |
| 11.5% | 42% | 3.85% | 11.47% | 1,321 |
| **11.0%** | **58%** | 2.80% | 10.97% | 1,803 |
| 10.5% | 74% | 1.75% | 10.48% | 2,274 |
| 10.0% | 89% | 0.74% | 9.98% | 2,751 |
| 9.5% | **Không khả thi** (100% đúng hạn vẫn còn 9.63%) | — | — | — |

**Bang RJ** (hiện tại 16.62%):

| Mục tiêu review xấu ≤ | Cần giảm % đơn trễ | Review xấu kỳ vọng |
|---|---|---|
| 16% | 11% | 15.94% |
| 15% | 26% | 14.99% |
| 14% | 41% | 13.98% |
| 13% | 57% | 12.98% |

Khi mục tiêu không khả thi, hệ thống báo lỗi và gợi ý cần giải pháp khác ngoài logistics: chất lượng sản phẩm, đóng gói, gom đơn nhiều người bán…

### 4.4.6 Xếp hạng ưu tiên (Choice)

Với mỗi nhóm, hệ thống giả sử **toàn bộ đơn trễ** trong nhóm được giao đúng hạn, rồi tính số review xấu kỳ vọng tránh được. Chỉ xét các nhóm có ≥ 100 đơn có review.

**Top 10 bang:**

| # | Bang | Số đơn | Tỷ lệ trễ | Tỷ lệ review xấu | Review xấu tránh được | Giá trị đơn trễ (R$) | Giảm tỷ lệ review xấu trong bang |
|---|---|---|---|---|---|---|---|
| 1 | SP | 40,271 | 4.43% | 10.69% | 805 | 264,659 | 2.00 điểm % |
| 2 | RJ | 12,212 | 11.93% | 18.33% | 769 | 209,710 | 6.30 điểm % |
| 3 | MG | 11,282 | 4.49% | 11.76% | 227 | 72,691 | 2.01 điểm % |
| 4 | BA | 3,228 | 11.90% | 17.01% | 191 | 60,310 | 5.92 điểm % |
| 5 | RS | 5,326 | 6.03% | 11.92% | 161 | 43,109 | 3.02 điểm % |
| 6 | SC | 3,520 | 8.07% | 12.95% | 130 | 37,436 | 3.69 điểm % |
| 7 | ES | 1,970 | 10.41% | 13.81% | 100 | 27,037 | 5.10 điểm % |
| 8 | CE | 1,275 | 13.65% | 17.10% | 91 | 30,226 | 7.10 điểm % |
| 9 | PR | 4,898 | 3.96% | 10.90% | 86 | 28,981 | 1.75 điểm % |
| 10 | PE | 1,578 | 9.51% | 14.89% | 77 | 26,346 | 4.89 điểm % |

**Top 10 danh mục:**

| # | Danh mục | Số đơn | Tỷ lệ trễ | Tỷ lệ review xấu | Review xấu tránh được | Giá trị đơn trễ (R$) | Giảm tỷ lệ review xấu trong danh mục |
|---|---|---|---|---|---|---|---|
| 1 | bed_bath_table | 9,090 | 7.33% | 15.82% | 320 | 76,649 | 3.53 điểm % |
| 2 | health_beauty | 8,567 | 7.39% | 11.35% | 315 | 91,224 | 3.68 điểm % |
| 3 | sports_leisure | 7,448 | 6.53% | 11.20% | 247 | 69,474 | 3.32 điểm % |
| 4 | furniture_decor | 6,142 | 7.15% | 14.85% | 203 | 56,657 | 3.31 điểm % |
| 5 | watches_gifts | 5,436 | 7.27% | 13.65% | 195 | 89,282 | 3.59 điểm % |
| 6 | computers_accessories | 6,480 | 6.28% | 14.51% | 193 | 60,655 | 2.97 điểm % |
| 7 | housewares | 5,646 | 5.31% | 11.57% | 147 | 37,456 | 2.61 điểm % |
| 8 | telephony | 4,049 | 7.09% | 13.93% | 132 | 25,167 | 3.26 điểm % |
| 9 | auto | 3,774 | 7.23% | 12.80% | 131 | 64,106 | 3.47 điểm % |
| 10 | toys | 3,757 | 6.18% | 11.31% | 117 | 30,243 | 3.12 điểm % |

**Hạn chế của xếp hạng này:** mọi nhóm đều được giả định sửa *toàn bộ* đơn trễ, và chưa tính chi phí. Vì vậy bảng chỉ cho biết tiềm năng của mỗi nhóm, chưa trả lời được câu hỏi “ngân sách có hạn thì chọn đâu”. Câu hỏi đó được giải ở §4.4.7.

### 4.4.7 Tối ưu phân bổ ngân sách (Choice — mathematical programming)

**Câu hỏi quyết định chính:** với ngân sách giới hạn, nên giảm đơn trễ ở những bang nào và giảm bao nhiêu, để tránh được nhiều review xấu nhất? Thứ tự ưu tiên có còn đúng khi giả định chi phí thay đổi không?

**Mô hình** (slide Ch.7: *mathematical programming*, dạng bài toán cái túi nhiều lựa chọn, quy hoạch nguyên 0-1):

| Thành phần | Trong mô hình |
|---|---|
| Decision variables | x[s, r] = 1 nếu bang s được giảm r% đơn trễ, với r ∈ {25, 50, 75, 100}% |
| Result variable (hàm mục tiêu) | Tối đa hoá số review xấu tránh được: Σ benefit[s, r] · x[s, r] |
| Ràng buộc | Mỗi bang chọn tối đa 1 mức · tổng chi phí ≤ ngân sách · (tuỳ chọn) số bang tối đa K, thể hiện năng lực quản lý |
| benefit[s, r] | Tính bằng mô hình what-if (§4.3) cho từng bang và từng mức. Đơn ở các bang khác nhau là tách biệt, nên lợi ích cộng dồn được chính xác |
| Phạm vi | 24 bang có ≥ 100 đơn có review, 4 mức, tổng 96 phương án |

**Chi phí** (BRL) = phí ship thực tế của các đơn trễ được sửa × `surcharge` × `tier[r]`.
- Phí ship lấy **từ DW**, nên chênh lệch chi phí giữa các bang là thật. Ví dụ, phí ship trung bình một đơn ở vùng Southeast là 19.84 BRL, ở vùng North là 41.35 BRL.
- `surcharge` = 0.5 và `tier` = 1 / 1.2 / 1.5 / 2 (càng sửa sâu càng đắt) là **giả định**, vì Olist không công bố chi phí cải thiện giao hàng. Hai tham số này nằm ở `config/cost_assumptions.csv`.
- Nhóm đã kiểm tra trên dữ liệu: so trong cùng tuyến và cùng nhóm cân nặng, đơn trả phí ship cao hơn **không** giao nhanh hơn. Vì vậy phí ship chỉ được dùng làm thước đo “logistics ở bang đó đắt hay rẻ”, không phải cơ chế làm đơn nhanh hơn (chi tiết ở `config/README.md`).
- `surcharge` nhân đều mọi chi phí nên **không làm đổi phương án**, chỉ đổi thang đo của ngân sách. Đã kiểm chứng: surcharge 0.5 với ngân sách 30,000 BRL cho đúng cùng phương án như surcharge 1.0 với 60,000 BRL.

**Thuật toán:**
- Giải **chính xác** bằng MILP (SciPy `milp`, solver HiGHS), mỗi lần giải mất khoảng 0.03–0.06 giây.
- Có thêm thuật toán **greedy** (chọn dần bước nâng cấp có lợi ích / chi phí cao nhất) làm baseline, để thấy tối ưu chính xác thêm được bao nhiêu.

**Phương án tối ưu với giả định mặc định:**

| Ngân sách (BRL) | Số bang | Đơn trễ được sửa | Review xấu tránh được | Tỷ lệ review xấu kỳ vọng toàn quốc | Greedy | Greedy kém hơn |
|---|---|---|---|---|---|---|
| 5,000 | 2 | — | 226.1 | — | 225.6 | 0.24% |
| 10,000 | 5 | 899 | 448.2 | 12.85% → 12.38% | 446.6 | 0.36% |
| 20,000 | 12 | 1,698 | 817.5 | 12.85% → 12.00% | 817.5 | 0.00% |
| 40,000 | 19 | 2,893 | 1,410.9 | 12.85% → 11.38% | 1,405.1 | 0.41% |
| 80,000 | 22 | — | 2,194.7 | — | 2,194.3 | 0.02% |
| 160,000 | 24 | — | 3,079.8 | — | 3,078.2 | 0.05% |

*(biểu đồ: đường cong ngân sách – lợi ích, có thêm đường greedy)*

**Nhận xét:**
- Lợi ích **giảm dần theo ngân sách** (diminishing returns). 10,000 BRL đầu tiên tránh được 448 review xấu. Tăng ngân sách từ 80,000 lên 160,000 BRL chỉ tránh thêm 885 review.
- Sửa toàn bộ đơn trễ ở cả 24 bang tốn khoảng 160,000 BRL và tránh được khoảng 3,080 review xấu.
- Greedy kém tối ưu tối đa 0.41%. Với dữ liệu này, heuristic đơn giản đã khá tốt. MILP vẫn được dùng vì nó chắc chắn cho kết quả tối ưu và chạy đủ nhanh.

Ví dụ khung đề xuất tự sinh ở tab 5 với ngân sách 40,000 BRL:
> Giảm 50% đơn trễ ở RJ, SP, MG, BA, RS, SC, ES, PR, GO, DF, PI, MS; giảm 25% đơn trễ ở CE, PE, PA, MT, AL, SE, TO (tổng chi phí 39,966 BRL, 2,893 đơn trễ được xử lý). Dự kiến tránh được khoảng 1,411 review xấu; tỷ lệ review xấu kỳ vọng toàn quốc giảm từ 12.85% xuống 11.38%.

**Độ nhạy theo giả định `tier`** (ngân sách 40,000 BRL):

| Kịch bản tier | Hệ số 25 / 50 / 75 / 100% | Review xấu tránh được | Số bang | Đơn trễ được sửa | Dạng phương án |
|---|---|---|---|---|---|
| Phẳng | 1 / 1 / 1 / 1 | 1,818.4 | 8 | 3,737 | Sửa sâu ở ít bang: SP 100%, RJ 100%, ES / GO / PR / RO / RS 50%, SC 25% |
| Mặc định | 1 / 1.2 / 1.5 / 2 | 1,410.9 | 19 | 2,893 | Phần lớn các bang giảm 25–50% |
| Dốc | 1 / 1.5 / 2.25 / 3.5 | 1,240.6 | 20 | 2,525 | Sửa nhẹ ở nhiều bang, đa số chỉ 25% |

→ `tier` quyết định nên **sửa sâu ở ít bang hay sửa nhẹ ở nhiều bang**. Đây là giả định có ảnh hưởng lớn nhất, nên cần thay bằng báo giá thật của hãng vận chuyển trước khi thực hiện.

**Phân tích độ vững (robustness) — câu trả lời chính của DSS.** Vì chi phí là giả định, nhóm giải lại bài toán dưới **6 bộ giả định**:
- 2 cách tính chi phí:
  - theo phí ship thật của từng bang;
  - đồng đều: mọi đơn trễ cùng một giá, bằng phí ship trung bình toàn quốc của một đơn trễ, tức là bỏ hẳn yếu tố phí ship;
- × 3 kịch bản tier: phẳng / mặc định / dốc;
- mỗi bộ giải ở 3 mức ngân sách (10,000 / 20,000 / 40,000 BRL), tổng 18 lần giải.

Một bang thuộc **ưu tiên k** nếu ở mức ngân sách thứ k nó đã được chọn trong **ít nhất 4/6 bộ giả định**.

| Ưu tiên | Từ ngân sách | Bang (số bộ giả định chọn bang ở mức 10k / 20k / 40k, trên 6) |
|---|---|---|
| **1** | 10,000 BRL | **RJ** (5/5/6), **GO** (4/5/6), **PR** (4/4/6), **RN** (5/4/4) |
| 2 | 20,000 BRL | RS, ES, SP, SE, PA, SC, AL, TO, MT, DF, MG |
| 3 | 40,000 BRL | BA, PI, MS, PE, CE |
| Ít khi được chọn | — | RO, PB, MA, AM |

*(nguồn: `optimizer.robustness()`, tab 5 trang DSS)*

**Diễn giải:**
- **RJ là kết luận vững nhất.** RJ được chọn ở 16/18 lần giải. Điều này khớp với xếp hạng ở §4.4.6: RJ có tỷ lệ trễ cao (11.93%) trên một lượng đơn lớn.
- **SP không thuộc ưu tiên 1, dù đứng đầu về số tuyệt đối.** Ở 10,000 BRL, SP được chọn ở cả 3 bộ giả định tính theo phí ship thật, nhưng không được chọn ở bộ nào tính theo chi phí đồng đều. Như vậy vị trí của SP phụ thuộc vào giả định chi phí, và SP chỉ chắc chắn được chọn từ 20,000 BRL.
- **Mức giảm cụ thể ở mỗi bang phụ thuộc giả định.** Ví dụ, RJ dao động từ 25% đến 100%. Vì vậy hệ thống chỉ báo mức giảm dưới dạng khoảng, còn **thứ tự ưu tiên** mới là kết luận dùng được.

[HÌNH] Tab 5 trang DSS: bảng ưu tiên vững, phương án chi tiết, đường cong ngân sách.

### 4.4.8 Đề xuất cho nhà quản lý (Implementation)

1. **Ưu tiên RJ, sau đó GO, PR, RN.**
   - Đây là các bang được chọn ngay ở ngân sách nhỏ nhất (10,000 BRL) trong ít nhất 4/6 bộ giả định chi phí (§4.4.7).
   - Với RJ, xếp hạng theo tiềm năng (§4.4.6) cho cùng kết luận. RJ tránh được 769 review xấu, gần bằng SP (805), dù số đơn chỉ bằng khoảng 30% SP. Mức giảm tỷ lệ review xấu trong bang (6.3 điểm %) cao gấp khoảng 3 lần SP.
   - SP chỉ nên đưa vào khi ngân sách từ khoảng 20,000 BRL, vì vị trí của SP phụ thuộc giả định chi phí.
   - Hành động: đánh giá lại đơn vị vận chuyển tuyến vào RJ, hoặc thêm đơn vị vận chuyển cho tuyến này.
   - Trước khi giải ngân: thay `surcharge` và `tier` bằng báo giá thật của hãng vận chuyển, rồi chạy lại tab 5.
2. **Nhóm Northeast (BA, CE, AL, MA, SE…)** có tỷ lệ trễ 12–21%. Nên **nới ngày giao dự kiến** cho sát thời gian thực tế (ngày giao TB 19–25 ngày). Khi ngày dự kiến sát thực tế, một phần đơn sẽ không còn bị tính là trễ.
3. **Đơn nhiều người bán** có 45–54% review xấu dù đúng hạn. Nên gom hàng và giao một lần, hoặc thông báo rõ cho khách là đơn sẽ về thành nhiều đợt.
4. **Mục tiêu khả thi:** muốn đưa tỷ lệ review xấu toàn quốc về ≤ 11%, cần giảm 58% số đơn trễ (tỷ lệ trễ 6.7% → 2.8%). Mức dưới 9.6% không thể đạt được chỉ bằng cải thiện giao hàng.

---

# 5. Đánh giá & kết luận

## 5.1 Mức độ đáp ứng yêu cầu bài tập lớn

**Sáu mục tiêu (§1.1 của đề):**

| # | Yêu cầu | Đáp ứng | Section |
|---|---|---|---|
| 1 | Phân tích yêu cầu nghiệp vụ, xác định bài toán | Bài toán giao trễ → review xấu; câu hỏi phân tích và câu hỏi quyết định; data profiling | 1.1, 1.2 |
| 2 | Thiết kế DW đa chiều (star / snowflake) + ETL | Fact constellation (2 fact dạng star dùng chung 4 dimension), grain, hierarchy; ETL 3 bước + metadata; hợp đồng nguồn và kiểm tra chất lượng | 2.1–2.3, 2.5 |
| 3 | Hiện thực backend (CSDL, ETL, OLAP) + frontend | PostgreSQL, ETL tự động, ROLAP + materialized views; dashboard Streamlit 5 trang (Home, OLAP, Delivery, DSS, Data Quality) | 2.4, 2.5, 3 |
| 4 | Phát triển thành phần DSS dựa trên DW | Hybrid DSS: cây quyết định, what-if, sensitivity, goal seeking, xếp hạng, tối ưu ngân sách (MILP) và phân tích độ vững, đề xuất | 4 |
| 5 | Đánh giá kết quả, hạn chế, hướng phát triển | 43 kiểm tra chất lượng, 102 test tự động, metrics mô hình, cross-validation chọn tham số, kiểm tra mô hình rủi ro trên tập test, độ nhạy theo giả định chi phí, hạn chế, hướng phát triển | 2.4–2.5, 4.2, 4.3, 4.4.7, 5.2–5.3 |
| 6 | Trình bày trước lớp / video | Slide và video | [TODO] |

**Chuẩn đầu ra (§1.2):**

| L.O. | Nội dung | Section |
|---|---|---|
| 1.1 | Khái niệm cơ bản DW & DSS | 2 (khung lý thuyết), 4 (khung lý thuyết) |
| 1.2 | Vai trò của DW trong DSS | 4.1 |
| 1.3 | Ví dụ thực tế DW & DSS | 5.4 + chính project này |
| 2.1 | Quy trình, nguyên lý thiết kế DW | 2.1 |
| 2.2 | Các vấn đề trong thiết kế DW | 1.2 (chất lượng dữ liệu), 2.1.3 (granularity), 2.3 (partition, index, metadata), 2.5 (kiểm soát chất lượng) |
| 2.3 | Thiết kế và hiện thực hệ thống DW | 2, 3 |
| 3.1 | Khái niệm, đặc tính MSS & DSS | 4 (khung lý thuyết), 4.1 |
| 3.2 | Các giai đoạn ra quyết định | 4.1 (ánh xạ pha Simon) |
| 3.3 | Minh hoạ mô hình hoá trong DSS | 4.2–4.4 (gồm mô hình tối ưu ở 4.4.7) |
| 4.1 | Nguyên tắc phân tích, thiết kế DSS | 4.1, 1.4 (prototyping) |
| 4.2 | Phân tích, thiết kế, hiện thực DSS đơn giản | 4 |

**Thành phần nộp (§5.1):**

| Thành phần | Trạng thái |
|---|---|
| Báo cáo PDF | [TODO] viết từ tài liệu này |
| Mã nguồn `src/` (SQL, Python, frontend, ETL) — GitHub | ✅ https://github.com/taita2005/co4031-olist-dw-dss |
| Dữ liệu mẫu `data/` | [TODO] link Google Drive chứa CSV (GitHub không chứa CSV) |
| Slide PDF | [TODO] |
| Link video trên trang bìa | [TODO] nếu thuyết trình qua video |

## 5.2 Hạn chế

| Hạn chế | Ảnh hưởng |
|---|---|
| Dữ liệu chỉ 2016–2018; các tháng đầu / cuối rất ít đơn | Không phản ánh hiện tại; dashboard phải lọc tháng |
| 97% khách chỉ mua 1 lần (2,997 / 96,096 khách mua > 1 lần) | Không phân tích được hành vi mua lặp |
| Review xấu còn nhiều nguyên nhân ngoài giao hàng | Precision của mô hình thấp (32.9%) |
| What-if giả định giao trễ là **nguyên nhân** của review xấu (mô hình dựa trên tương quan) | Kết quả là ước lượng, cần kiểm chứng bằng thử nghiệm thực tế |
| “Sửa đơn trễ” được giả định là giao đúng ngày dự kiến | Chưa mô hình hoá được cách sửa cụ thể (đổi hãng, thêm kho…) |
| Chi phí trong tối ưu ngân sách dựa trên 2 giả định (`surcharge`, `tier`), vì Olist không có dữ liệu chi phí can thiệp | Mức giảm cụ thể ở mỗi bang phụ thuộc giả định; chỉ thứ tự ưu tiên là vững (§4.4.7) |
| ETL dạng full refresh, chưa incremental | Chưa phù hợp với dữ liệu phát sinh liên tục |
| Chưa dùng SCD (khách đổi địa chỉ chỉ giữ địa chỉ của đơn gần nhất) | Mất lịch sử thay đổi địa chỉ |
| Chưa dùng geolocation, chưa có bản đồ | Chưa phân tích được theo khoảng cách địa lý |
| Một số bang có rất ít đơn (RR 41, AP 67, AC 80) | Tỷ lệ ở các bang này kém tin cậy |

## 5.3 Hướng phát triển

1. **Incremental ETL** (nạp theo ngày, dùng `etl_log` để biết lần nạp gần nhất) và **SCD type 2** cho dim_customer / dim_seller.
2. **Bản đồ địa lý** từ bảng geolocation (lấy toạ độ trung bình theo zip); thêm thuộc tính khoảng cách người bán – khách.
3. **Thay giả định chi phí bằng dữ liệu thật** (báo giá của hãng vận chuyển theo tuyến). Khi đó có thể mở rộng mô hình tối ưu ở §4.4.7 từ chọn bang sang **chọn đơn vị vận chuyển cho từng tuyến** (người bán → người mua).
4. **Dự báo nhu cầu** theo tháng để chuẩn bị năng lực vận chuyển cho các đợt cao điểm như Black Friday (11/2017).
5. Dùng **comment review** (văn bản) để tách các nguyên nhân review xấu không liên quan đến giao hàng.

## 5.4 Ví dụ thực tế về DW & DSS (L.O.1.3)

[TODO] Nhóm tự bổ sung 2–3 ví dụ doanh nghiệp có **trích nguồn**, ví dụ:
- kho dữ liệu bán lẻ dùng cho quyết định nhập hàng (nhóm tự chọn doanh nghiệp và tìm nguồn);
- DSS tối ưu tuyến giao hàng của doanh nghiệp logistics (ví dụ P&G dùng mô hình vận tải và mô hình chọn vị trí trung tâm phân phối, có trong slide Ch.7);
- DSS phân tích khách hàng trong ngân hàng / viễn thông.

Liên hệ với project: Olist là trường hợp thực tế, gồm DW tích hợp dữ liệu đơn hàng và DSS hỗ trợ quyết định logistics.

## 5.5 Kết luận

Nhóm đã xây dựng hoàn chỉnh một hệ thống gồm:
1. **Kho dữ liệu** dạng fact constellation trên dữ liệu thật khoảng 100k đơn hàng. Quy trình ETL tự động có metadata, hợp đồng nguồn và 43 kiểm tra chất lượng sau mỗi lần nạp.
2. **Dashboard OLAP** minh hoạ đủ 5 phép toán trên 2 fact dùng chung dimension, cùng trang theo dõi chất lượng dữ liệu.
3. **DSS** kết hợp dữ liệu và mô hình. DSS chỉ ra được:
   - giao trễ là yếu tố quyết định review xấu (trễ trên 5 ngày → khoảng 80% review xấu);
   - đơn nhiều người bán là nguồn rủi ro thứ hai;
   - với ngân sách giới hạn, nên ưu tiên **RJ, GO, PR, RN**. Thứ tự này đúng trong ít nhất 4/6 bộ giả định chi phí. Ngân sách 40,000 BRL (giả định mặc định) đưa tỷ lệ review xấu kỳ vọng từ 12.85% xuống 11.38%;
   - muốn tỷ lệ review xấu ≤ 11% cần giảm 58% đơn trễ, còn dưới 9.6% thì logistics không giải quyết được.

Hệ thống đi đủ các pha ra quyết định của Simon, từ phát hiện vấn đề (intelligence) đến đề xuất hành động (implementation) và đánh giá (evaluation).

---

# Tài liệu tham khảo

1. W. H. Inmon, *Building the Data Warehouse*, 4th ed. Wiley, 2005.
2. R. Kimball, M. Ross, *The Data Warehouse Toolkit*, 3rd ed. Wiley, 2013.
3. E. Turban, J. E. Aronson, T.-P. Liang, *Decision Support Systems and Intelligent Systems*, 7th ed. Prentice-Hall, 2005.
4. R. Elmasri, S. B. Navathe, *Fundamentals of Database Systems*, 7th ed. Addison-Wesley, 2016.
5. R. Sharda, D. Delen, E. Turban, *Analytics, Data Science, & Artificial Intelligence: Systems for Decision Support*, 7th ed. Pearson, 2020.
6. J. Han, M. Kamber, J. Pei, *Data Mining: Concepts and Techniques*, 3rd ed. Morgan Kaufmann, 2012.
7. F. Burstein, C. W. Holsapple, *Handbook on Decision Support Systems*. Springer, 2008.
8. Trần Minh Quang et al., *Cơ sở dữ liệu: khái niệm, phương pháp, và kỹ thuật phân tích thiết kế*. NXB ĐHQG-HCM, 2025.
9. Olist, *Brazilian E-Commerce Public Dataset by Olist*, Kaggle. https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
10. Slide bài giảng CO4031 HK261, Chương 1–8, giảng viên Đỗ Thanh Thái.
11. Tài liệu PostgreSQL 16, scikit-learn 1.5, Streamlit 1.39.

---

# Phụ lục

## A. Hướng dẫn cài đặt và chạy

Chi tiết xem `README.md` mục 1. Tóm tắt:

```bash
git clone https://github.com/taita2005/co4031-olist-dw-dss.git BTL && cd BTL
# đặt CSV Olist vào data/ (xem data/README.md)
bash scripts/setup_env.sh        # cài môi trường cục bộ (~3–5 phút, chỉ lần đầu)
source scripts/env.sh
bash scripts/db_start.sh         # PostgreSQL cục bộ, port 5433
python src/etl/run_etl.py        # ETL + 43 kiểm tra chất lượng (~12 giây)
python src/dss/train_model.py    # huấn luyện mô hình, thực nghiệm tham số, tính trước phương án tối ưu (~25 giây)
streamlit run src/app/Home.py    # http://localhost:8501
python -m pytest tests -q        # 102 test tự động
bash scripts/db_stop.sh          # tắt PostgreSQL khi xong
```

## B. Cấu trúc mã nguồn

| Đường dẫn | Vai trò |
|---|---|
| `scripts/` | Cài môi trường, bật / tắt PostgreSQL cục bộ |
| `environment.yml` | Danh sách package |
| `src/db.py` | Kết nối CSDL dùng chung |
| `src/sql/01_staging.sql` | Tạo bảng staging |
| `src/sql/02_dw_schema.sql` | Tạo dimension, fact, index, partition, `meta.etl_log` |
| `src/sql/03_transform_load.sql` | Toàn bộ logic Transform + Load |
| `src/sql/04_olap_views.sql` | Materialized views |
| `src/sql/05_checks.sql` | 27 kiểm tra chất lượng trên DW → `meta.check_result` |
| `src/sql/06_bi_views.sql` | View `bi` cho Metabase (phần mở rộng tuỳ chọn), chỉ trả dữ liệu khi mọi kiểm tra đạt |
| `src/etl/contracts.py` | Hợp đồng nguồn: kiểm tra từng CSV trước khi nạp |
| `src/etl/run_etl.py` | Điều phối ETL, ghi metadata và kết quả kiểm tra |
| `src/dss/train_model.py` | Huấn luyện cây quyết định, trích luật, tính information gain, thực nghiệm tham số, tính trước lợi ích cho tối ưu |
| `src/dss/whatif.py` | What-if, sensitivity, goal seeking, xếp hạng |
| `src/dss/optimizer.py` | Tối ưu ngân sách (MILP + greedy baseline), độ nhạy theo tier, phân tích độ vững |
| `config/cost_assumptions.csv` | 2 giả định chi phí (`surcharge`, `tier`), kèm giải thích ở `config/README.md` |
| `src/app/Home.py`, `src/app/pages/*.py` | 5 trang dashboard |
| `tests/` | 102 test (pytest) |
| `models/` | (sinh ra) model, luật, metrics, `experiments.json`, `options.csv` |
| `compose.yml`, `docs/metabase.md` | Tuỳ chọn: chạy toàn bộ stack bằng Docker Compose, kèm 3 dashboard Metabase (không dùng cho số liệu trong báo cáo này) |

## C. Danh sách hình cần chụp cho báo cáo và slide

| # | Hình | Section |
|---|---|---|
| 1 | ERD dữ liệu nguồn | 1.2 |
| 2 | Sơ đồ kiến trúc 3 tầng | 1.3 |
| 3 | Sơ đồ schema fact constellation | 2.1.3 |
| 4 | Luồng ETL (staging → dw → meta) | 2.2 |
| 5 | Trang Home (KPI + xu hướng) | 3.3.1–3.3.2 |
| 6–10 | OLAP: roll-up, drill-down, slice, dice, pivot | 3.2 |
| 11 | OLAP: mục “SQL được sinh ra” | 3.2 |
| 12 | OLAP: chọn fact_delivery (ghi chú non-additive) | 3.2 |
| 13 | Trang Delivery | 3.3.3–3.3.5 |
| 14–17 | DSS: 4 tab (mô hình, xếp hạng, what-if + sensitivity, goal seeking) | 4 |
| 18 | Goal seeking trường hợp không khả thi (mục tiêu 9.5%) | 4.4.5 |
| 19 | DSS tab 5: bảng ưu tiên vững qua 6 bộ giả định | 4.4.7 |
| 20 | DSS tab 5: phương án chi tiết 40,000 BRL + đường cong ngân sách – lợi ích | 4.4.7 |
| 21 | DSS tab 1: bảng thực nghiệm chọn tham số | 4.2.2 |
| 22 | Trang Data Quality | 2.5 |

## D. Thay đổi so với proposal ban đầu

Xem bảng “Thay đổi so với bản đề xuất ban đầu” trong `docs/proposal.md`. Tóm tắt:
- dùng môi trường micromamba thay cho Docker;
- thêm `product_key` và `n_sellers` vào `fact_delivery`;
- metadata đặt ở schema `meta`;
- đã làm partition;
- xác suất lấy theo lá của cây;
- goal seeking dùng complete enumeration;
- phân công đổi thành 1 người code, 2 người review;
- bổ sung sau proposal: hợp đồng nguồn và kiểm tra chất lượng tự động, trang Data Quality, thực nghiệm chọn tham số bằng cross-validation, tối ưu ngân sách (MILP) cùng phân tích độ vững, và phần mở rộng Docker Compose + Metabase.

## E. Gợi ý chia slide (15 phút)

| Phần | Người trình bày | Nội dung | Thời lượng |
|---|---|---|---|
| Section 1 | A | Bài toán, dữ liệu, kiến trúc, tính năng | ~3 phút |
| Section 2 | A | Schema, grain, ETL, kết quả ETL | ~3 phút |
| Section 3 | B | Demo OLAP 5 phép toán, insight Delivery | ~4 phút |
| Section 4–5 | C | Cây quyết định, what-if, goal seeking, tối ưu ngân sách và độ vững, đề xuất, đánh giá | ~5 phút |
