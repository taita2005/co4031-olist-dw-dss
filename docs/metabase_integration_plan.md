# Kế hoạch tích hợp 3 dashboard Metabase

> **For agentic workers:** Khi triển khai, dùng `superpowers:executing-plans` theo từng task và các checkbox dưới đây. Tài liệu này là kế hoạch, chưa phải bằng chứng dashboard đã chạy.

**Ngày lập:** 14/11/2026. **Baseline mã nguồn:** `8b285d0`.

**Điều chỉnh theo yêu cầu người dùng:** Toàn bộ stack chạy bằng Docker Compose; máy host chỉ cần Docker Engine/Desktop và Compose v2, không cài Python, micromamba, PostgreSQL hoặc Java để chạy demo.

**Goal:** Bổ sung ba dashboard tiếng Việt để phân tích kinh doanh, cơ cấu bán hàng và chất lượng giao hàng; có SQL đối chiếu và hình dùng cho báo cáo.

**Architecture:** Docker Compose chạy PostgreSQL Olist, container Python cho ETL/train/provision/test, Streamlit/DSS, Metabase và PostgreSQL application DB riêng. Metabase đọc view BI của kho Olist qua mạng Compose. Giữ logic ETL/DW/DSS hiện tại và lưu dữ liệu, model, cấu hình dashboard qua các lần tạo lại container.

**Tech Stack:** Docker Compose v2, PostgreSQL 16, image Python 3.12 dùng chung cho app và job, image Metabase OSS chính thức; API HTTP qua thư viện chuẩn Python. Java do image Metabase cung cấp.

**Spec:** Yêu cầu ba dashboard trong trao đổi với người dùng; phạm vi và định nghĩa cụ thể tại mục 3–5 của tài liệu này. Đây là phần mở rộng cho `docs/plan.md`, không thay các kết quả đã chốt trong đó.

## 1. Hiện trạng đã đọc từ checkout

| Thành phần                      | Hiện trạng                                                                                                               | Hệ quả cho tích hợp                                                                                                                           |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Môi trường                     | `environment.yml`: Python 3.12, PostgreSQL 16, pandas, SQLAlchemy, psycopg2, scikit-learn, Streamlit, Plotly, pytest     | Tạo image Python và lock dependencies; đối chiếu imports thực tế, gồm SciPy của optimizer, thay vì chỉ chuyển nguyên environment.yml |
| Kết nối                         | `scripts/env.sh`: `localhost:5433`, database `olist_dw`, user `btl`; `db_start.sh` dùng `initdb --auth=trust` | Compose cấp PGHOST=postgres, PGPORT=5432 và credentials; không source env.sh trong container vì sẽ ghi đè kết nối                        |
| ETL                               | `src/etl/run_etl.py`: validate CSV → COPY → SQL 01–04 → metadata → SQL 05 và source checks                         | Cần móc tạo view/quyền BI vào cùng transaction sau bước kiểm tra                                                                         |
| Chất lượng                     | Có `meta.etl_log`, `meta.check_result`, `05_checks.sql`, trang `4_Data_Quality.py`                                | Tái sử dụng trạng thái kiểm tra, không viết thêm một hệ monitoring                                                                     |
| Commit ETL                        | Nếu check trả FAIL, ETL vẫn commit rồi mới thoát code 1; lỗi SQL thì rollback                                      | View BI phải chặn dữ liệu của phiên không đạt; không chỉ kiểm tra lúc provision                                                      |
| Warehouse                         | 4 dimension; `fact_sales` grain item, `fact_delivery` grain đơn đã giao                                            | Mỗi truy vấn dùng đúng một fact, không join trực tiếp hai fact                                                                           |
| Tổng hợp                        | `mv_monthly_kpi`, `mv_sales_cube`, `mv_delivery_by_state` trong `04_olap_views.sql`                                | MV hiện tại không đủ bộ lọc kết hợp và mẫu số; không sửa chúng để tránh ảnh hưởng Streamlit                                  |
| DSS                               | Có cây quyết định, what-if, optimizer dùng `scipy.optimize.milp`, metadata model có `etl_run_id`                | Metabase phục vụ bước Intelligence; quyết định/ngân sách giữ ở Streamlit                                                               |
| Kiểm thử                        | Có 5 file `tests/test_*.py`; fixture `engine` bỏ qua test khi DB không truy cập được                            | Bổ sung test BI vào cấu trúc pytest hiện tại; SKIP không được ghi thành PASS                                                           |
| Tài liệu                        | `docs/plan.md` trước đây loại Metabase/Docker khỏi scope; `handoff.md` phản ánh mốc cũ hơn                  | Khi triển khai, cập nhật riêng phạm vi BI trong plan/README, không ghi đè lịch sử                                                       |
| Dữ liệu/runtime tại ngày lập | Có 9 CSV trong `data/`; ETL cần 8 file. Chưa có `.env-btl/`, `.pgdata/`, `models/`                             | Chưa chạy ETL/model/UI/Metabase hoặc xác nhận các số liệu trong report ở lần lập kế hoạch này                                       |

## 2. Lựa chọn triển khai và giới hạn

**Phương án đã chốt theo yêu cầu người dùng: Docker Compose cho toàn bộ stack.** Dùng một `compose.yml` và một image Python dùng chung, không yêu cầu môi trường ngôn ngữ trên host. Các script micromamba cũ giữ nguyên cho người đang dùng, nhưng không nằm trong đường chạy Compose.

| Cách làm                            | Đánh đổi                                                       | Quyết định trong kế hoạch                                             |
| ------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| Docker Compose toàn bộ stack        | Cần build/pull lần đầu; kết nối và persistence thống nhất | Đường triển khai chính theo yêu cầu mới                            |
| Docker Compose chỉ cho BI            | Vẫn phụ thuộc PostgreSQL và runtime trên host                 | Không chọn vì chưa đáp ứng chạy toàn bộ bằng Compose            |
| Tạo dashboard thủ công hoàn toàn | Có hình nhanh nhưng khó tái tạo, bàn giao                   | Chỉ dùng chỉnh hình thức sau khi script provision đã tạo nội dung |

- Dùng Metabase OSS; không phụ thuộc tính năng trả phí, public sharing hoặc serialization trả phí.
- Baseline tham chiếu là image `metabase/metabase:v0.64.1` của repo gốc. Task 1 phải xác minh tag/digest, khả năng pull và nền tảng CPU trước khi chốt. Pin image Metabase/PostgreSQL/Python theo bản cụ thể và digest đã kiểm; không dùng `latest` hoặc cài JRE trên host.
- Service `metabase-db` chạy PostgreSQL riêng, database/owner `metabase_app`, volume `metabase_data`. Metabase nhận `MB_DB_HOST=metabase-db`, `MB_DB_PORT=5432`, `MB_DB_TYPE=postgres` và credentials riêng. Không dùng H2.
- Kết nối dữ liệu Olist dùng role `metabase_ro`, không dùng `btl` hay owner application DB. Role chỉ đọc view trong schema `bi`, không có quyền sửa dữ liệu hoặc đọc staging.
- Web chỉ publish `127.0.0.1:3000:3000` và Streamlit `127.0.0.1:8501:8501`. Streamlit listen `0.0.0.0` bên trong container. Hai PostgreSQL không publish cổng ra host; kết nối nội bộ dùng service DNS và xác thực mật khẩu, không dùng trust/localhost/host.docker.internal.
- Không thêm dbt/Airflow, thay mô hình DSS, đổi customer grain hay tự động sửa kết quả báo cáo đã chốt.
- Hạn nộp trong tài liệu hiện tại là 15/11/2026 23:59 ICT: ước lượng công sức bên dưới không phải cam kết kịp hạn. Nếu gate chưa đạt, tiếp tục dùng ảnh Streamlit đã kiểm chứng; không đưa hình Metabase chưa đối chiếu vào báo cáo.

### 2.1. Service, kết nối và lưu trữ

| Service         | Trách nhiệm và kết nối                                                                                                                 | Lưu trữ                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `postgres`    | PostgreSQL 16, database `olist_dw`; admin bootstrap riêng, owner ETL `btl` không superuser, reader `metabase_ro`                    | Named volume `olist_data`; không mount `.pgdata/` của host                                           |
| `metabase-db` | PostgreSQL 16 lưu cấu hình Metabase; chỉ Metabase dùng role app owner                                                                  | Named volume `metabase_data`                                                                             |
| `app`         | Streamlit/DSS từ image Python chung; PGHOST=postgres, PGPORT=5432, PGDATABASE=olist_dw                                                     | Volume `model_data` tại `/app/models`; `.runtime/` bind mount để xuất evidence                   |
| `tools`       | Job một lần từ cùng image: bootstrap DB, ETL, train, provision, tests, backup; không tự chạy ETL khi up/restart                      | `data/` bind read-only, `model_data` dùng chung với app, `.runtime/` bind read-write               |
| `metabase`    | Image OSS; đọc Olist ở `postgres:5432` qua metabase_ro, lưu cấu hình ở `metabase-db:5432`; API nội bộ `http://metabase:3000` | Metadata nằm trong metabase-db; không lưu dashboard trong filesystem container                          |
| `bootstrap`   | Cùng image Python, không depends_on DB; sinh `.env` mode 600 bằng secrets, giữ các giá trị đã có                         | Chỉ job này mount root repo để tạo env và thư mục `.runtime/`; chạy trước khi up các service |
| `db-init` | Job tự động tạo roles/quyền BI, chờ PostgreSQL healthy | Không nạp lại CSV |
| `etl-init` | Chờ db-init thành công; chỉ ETL khi cả hai fact chưa tồn tại; kho hiện có phải đạt quality gate | `data/` bind read-only |
| `train-init` | Chờ etl-init; train khi thiếu model hoặc ETL run ID đã đổi | Named volume `model_data` |
| `metabase-init` | Chờ etl-init và Metabase healthy; provision mặc định, giữ chỉnh sửa tay | Catalog trong `.runtime/`; không dùng `--upgrade` |

`tools` và `bootstrap` đặt trong profile `jobs`, được gọi đích danh bằng `compose run`. Sau khi tạo `.env` một lần và đặt đủ 8 CSV, `docker compose up -d` tự chạy bốn job init. Sau ETL, train và provision có thể chạy song song; app chờ cả hai thành công. Kho đã được chứng nhận và model đúng run được bỏ qua, partial DW hoặc checks fail thì dừng thay vì ghi đè. Bootstrap phải chạy được khi `.env` chưa tồn tại: không khai báo env_file bắt buộc hoặc `${VAR:?}` toàn cục ngăn parse Compose; service dùng secrets phải tự từ chối khởi động với giá trị trống. Compose đọc `.env` trước khi chạy container, nên bootstrap tạo file này vẫn là bước thủ công một lần.

- Build image Python từ source/lock; chỉ copy code, SQL và tests cần thiết. Cài PostgreSQL client 16 trong image tools dùng chung nếu job backup gọi pg_dump; version client phải tương thích server. `.dockerignore` loại CSV, `.git`, `.env*`, `.pgdata`, `.venv*`, models, logs và backups; raw CSV không vào image.
- Dùng `PG*` env trực tiếp với `src/db.py`; truyền credentials vào từng service theo nhu cầu. `tools` có credentials bootstrap; `app` dùng `btl` để tương thích khả năng train model khi thiếu, Metabase chỉ có reader của Olist và app-DB credentials. Không cấp admin PostgreSQL cho app.
- `postgres`/`metabase-db` có healthcheck `pg_isready`; job/app chờ DB healthy; provision chờ `/api/health` và gate dữ liệu. `depends_on` không thay thế kiểm tra DW/model đã sẵn sàng. App phải kiểm tra DW và model trước khi mở trang DSS; hướng dẫn chạy ETL/train khi thiếu, không tự nạp lại CSV.
- Model được train bởi tools và giữ qua recreate app. Sau ETL mới, train lại trước demo DSS; không lấy model host cũ đưa vào image. Backup `model_data` và `.env` cùng các database khi bàn giao trạng thái demo.
- Không đổi volume hoặc xóa volume để sửa lỗi đăng nhập; đổi env password không tự đổi password của database đã khởi tạo. `compose down` giữ volumes; `down -v` không thuộc hướng dẫn chạy thường ngày.
- Dữ liệu PostgreSQL cũ trên host chỉ di chuyển qua pg_dump/restore có lựa chọn, hoặc nạp CSV vào volume mới; không tự nhận/mount directory database hiện có. Nếu dùng lại dump thì chạy bootstrap grants và SQL 06 sau restore, kiểm chứng trước khi chụp hình.
- Bản đầu cho phép `build` image app từ clone sạch; đây chưa phải bản phát hành pull-only trên registry. Nếu chưa thử ARM64 thì ghi rõ giới hạn, không hứa chạy macOS Apple Silicon chỉ từ việc chạy được trên x86_64.

## 3. Hợp đồng dữ liệu và KPI

### 3.1. Quy tắc chung

- Thời gian lọc là **ngày mua**, lấy `dim_date.full_date` qua `purchase_date_key`; cửa sổ `[start_date, end_date)`.
- Mặc định trình bày 01/01/2017 đến trước 01/09/2018, khớp cửa sổ các tháng đầy đủ của Streamlit. Vẫn cho phép chọn toàn dữ liệu; không cắt dữ liệu ở view.
- Executive/Sales loại `order_status IN ('canceled', 'unavailable')`, giữ đúng repo con. Gọi là doanh thu giá sản phẩm; không gắn nhãn delivered GMV của repo gốc.
- Doanh thu = `SUM(price)`; freight tính riêng. Số dòng hàng = `COUNT(*)`; số đơn = `COUNT(DISTINCT order_id)` sau bộ lọc. AOV = doanh thu / số đơn, dùng `NULLIF` khi mẫu số bằng 0.
- Không cộng số đơn distinct giữa các danh mục; không lấy trung bình tỷ lệ giữa bang hoặc tháng. Tổng hợp lại tử số và mẫu số trên tập đang lọc.
- Địa lý khách hàng dùng địa chỉ mới nhất theo `customer_unique_id`, đúng DW hiện tại. Chú thích rõ đây không nhất thiết là địa chỉ ở thời điểm từng đơn hàng.
- Danh mục/người bán của `fact_delivery` là item giá cao nhất của đơn. Không dùng để kết luận mọi item trong đơn đều thuộc danh mục đó. Đợt đầu không thêm bộ lọc danh mục cho Delivery.
- Review xấu = điểm 1–2; mẫu số là đơn có review. Đơn không review không được coi là review tốt.
- Late rate = số đơn trễ / số đơn có đủ ngày thực tế và dự kiến. `fact_delivery` hiện khai báo các số ngày NOT NULL; vẫn đối chiếu điều kiện nguồn và check miền giá trị. Không tự thay đổi cách ETL xử lý nguồn thiếu ngày để làm dashboard chạy được.
- Nhóm ngày trễ: đúng/sớm (`delay_days <= 0`), 1–3, 4–7, 8–14, 15+. Khi tính bad-review rate theo nhóm chỉ dùng đơn có review; hiển thị cả tổng đơn và số có review.
- Bang xuất hiện trên bubble khi có ít nhất 50 đơn hợp lệ trong phạm vi lọc. KPI toàn phạm vi không áp ngưỡng 50; biểu đồ nhóm review hiện số mẫu, không ẩn nhóm ít đơn mà không chú thích.

### 3.2. View BI dự kiến

Tạo `src/sql/06_bi_views.sql`, view thường để đọc dữ liệu hiện tại, không thêm bước refresh MV. Interface:

| View                   | Grain và các cột cần có                                                                                                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bi.dataset_status`  | Một dòng: `etl_run_id`, `check_count`, `failed_count`, `ready`; lấy phiên load mới nhất, yêu cầu có marker `step='run'` cùng ID và đủ tập check hiện hành đều đạt               |
| `bi.sales_items`     | Một item: `order_id`, `order_item_id`, `purchase_date`, `customer_state`, `customer_region`, `category`, `price`, `freight_value`; lọc status theo mục 3.1                                 |
| `bi.delivery_orders` | Một đơn: `order_id`, `purchase_date`, `customer_state`, `customer_region`, `delivery_days`, `delay_days`, `is_late`, `review_score`, `is_bad_review`, `delay_bucket`, `bucket_order` |

Hai view dữ liệu chỉ trả dòng khi `dataset_status.ready = true`. View status luôn trả một dòng kể cả chưa có phiên hợp lệ. Điều kiện đủ tập check phải dựa trên danh sách check của baseline khi triển khai, bao gồm source checks; không chỉ kiểm tra `failed_count = 0` trên tập rỗng hoặc bị thiếu. Mỗi question đối chiếu trạng thái trong chính query; không dựa vào kết quả preflight cũ.

View có ID cấp đơn chỉ phục vụ BI local để đếm đúng distinct; không export hoặc công khai các view này. Saved questions chỉ trả dữ liệu tổng hợp. Owner view có quyền đọc DW; role Metabase chỉ được SELECT view, không cần grant toàn bộ DW.

**Vòng đời full refresh:** `DROP SCHEMA dw CASCADE` làm mất các view `bi` phụ thuộc DW và quyền gắn với chúng. Sau khi ghi checks và marker hoàn tất, ETL phải chạy lại SQL 06 và grant SELECT trên các view vừa tạo **trước commit**, trong cùng transaction. Nếu SQL 06 lỗi, rollback toàn bộ; nếu checks FAIL, view được tạo nhưng không trả dữ liệu. Provision khi chưa có BI phải hướng dẫn chạy bootstrap/ETL, không tự chạy full refresh ngoài ý muốn.

Giữ query caching/model persistence tắt trong demo. Trước chụp ảnh phải refresh toàn dashboard sau ETL và xác nhận run ID; các card là query riêng nên không tuyên bố toàn dashboard có snapshot nguyên tử khi ETL đang chạy.

## 4. Danh mục dashboard: 15 card dữ liệu + 3 card trạng thái

Mỗi dashboard có thêm một card SQL dạng bảng gọn từ `bi.dataset_status` và một text card giải thích nguồn/KPI. Tổng 18 saved questions (15 dữ liệu + 3 status); text card không tính là saved question. Không cần nhập thêm dữ liệu cho các biểu đồ này.

### A. Tổng quan kinh doanh — Executive

Bộ lọc: ngày mua, vùng và nhiều bang; time grain tháng/quý/năm chỉ đổi các biểu đồ xu hướng.

| ID | Card                               | Dữ liệu và cách đọc                                                                                                                              |
| -- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| E1 | KPI doanh thu giá sản phẩm      | SUM(price), BRL, từ sales_items                                                                                                                       |
| E2 | KPI số đơn bán hàng           | COUNT DISTINCT order_id, cùng phạm vi E1                                                                                                             |
| E3 | Đường doanh thu theo thời gian | SUM(price) theo kỳ; số liệu lịch sử, không gọi là dự báo                                                                                     |
| E4 | Combo số đơn và AOV            | Cột số đơn, đường AOV; hai trục có đơn vị riêng, AOV tính lại mỗi kỳ                                                                  |
| E5 | Pareto doanh thu theo bang         | Cột doanh thu giảm dần, đường tỷ trọng tích lũy; giữ mọi bang đang lọc, không LIMIT trước khi tính mẫu số; tie-break theo mã bang |

### B. Cơ cấu bán hàng — Sales OLAP

Bộ lọc: ngày mua, vùng, nhiều bang, nhiều danh mục; time grain tháng/quý/năm áp dụng S2.

| ID | Card                                              | Dữ liệu và cách đọc                                                                                                                      |
| -- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| S1 | Top 10 danh mục theo doanh thu — bar ngang      | Top trên đúng tập đã lọc; số tiền các item khớp danh mục                                                                           |
| S2 | Xu hướng top 5 danh mục — line                | Chọn top 5 theo tổng doanh thu toàn cửa sổ đang lọc, cố định danh sách qua mọi kỳ; tie-break tên danh mục                       |
| S3 | Cơ cấu danh mục theo vùng — stacked 100%     | Dùng top 5 như S2; gộp phần còn lại thành “Danh mục khác trong bộ lọc”; tổng phần trăm mỗi vùng có doanh thu dương = 100% |
| S4 | Ma trận vùng × top 10 danh mục — pivot table | SUM(price), tô màu ô nếu OSS bản đã pin hỗ trợ; bảng số là fallback được chấp nhận, không hứa heatmap chưa kiểm tra       |
| S5 | Doanh thu theo bang — bar ngang                  | Mọi bang trong phạm vi lọc; liên kết phân tích cơ cấu với Executive                                                                  |

### C. Giao hàng & trải nghiệm — Delivery Quality

Bộ lọc: ngày mua, vùng, nhiều bang; time grain tháng/quý/năm áp dụng D2. Không có filter danh mục trong đợt đầu.

| ID | Card                                               | Dữ liệu và cách đọc                                                                                                                 |
| -- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| D1 | Bảng KPI và mẫu số                             | Đơn hợp lệ, đơn trễ, số có review, số review xấu, late rate, bad-review rate; phân biệt hai mẫu số                         |
| D2 | Xu hướng giao trễ và review xấu — line       | Hai tỷ lệ tính lại từ số đếm trong mỗi kỳ; không AVG tỷ lệ đã tổng hợp                                                   |
| D3 | Mức độ tập trung vấn đề theo bang — bubble | X: đơn hợp lệ; Y: late rate; size: đơn trễ; ngưỡng 50; tooltip đủ các số đếm                                               |
| D4 | Phân bố ngày trễ — bar                        | Đếm đơn theo 5 nhóm ở mục 3.1, sắp theo bucket_order, tổng khớp mẫu số giao hàng                                             |
| D5 | Review xấu theo nhóm ngày trễ — combo         | Cột tỷ lệ review xấu, đường số đơn có review; tooltip thêm tổng đơn; mô tả tương quan, không kết luận nguyên nhân |

**Định hướng hình thức:** Tiêu đề/nhãn tiếng Việt; layout khoảng 1440 px, card theo lưới hai cột, KPI trên đầu; tối đa hai series với combo khác đơn vị. Màu xanh cho doanh thu, cam cho trễ, đỏ cho review xấu; màu danh mục ổn định giữa S2/S3. Hiển thị BRL và %, tên trục/legend đầy đủ, không dựa riêng vào màu. Giá trị không có mẫu số hiển thị trống/không có dữ liệu, không thay bằng 0. Không yêu cầu thay theme toàn sản phẩm hoặc CSS riêng.

## 5. File và trách nhiệm khi triển khai

Các đường dẫn sau là file **dự kiến**, trừ các file ghi “sửa”; chưa được tạo bởi kế hoạch này.

| File                                                           | Trách nhiệm                                                                                                                                  |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `compose.yml`                                                | Khai báo 10 service ở mục 2.1, gồm bốn job init tự động, network, healthchecks, profiles, mounts, credentials và cổng loopback                                       |
| `Dockerfile`, `requirements-docker.txt`, `.dockerignore` | Image Python 3.12 dùng chung, lock dependency bao gồm SciPy/pytest; loại raw data và secrets khỏi build context                           |
| `scripts/docker_init.py`                                     | Entry point bootstrap chạy trong container, sinh `.env` và `.runtime/`, giữ secrets có sẵn; không yêu cầu Python trên host |
| `scripts/docker_bootstrap_db.py`                             | Chạy bằng tools để tạo owner ETL/reader, grants và cài view khi DW đã có; idempotent, không đổi password hiện hữu               |
| `src/sql/06_bi_views.sql`                                    | Tạo view status và hai view dữ liệu, grant lại quyền nếu role BI tồn tại; không tạo role trong ETL                                  |
| `src/bi/metabase.py`                                         | Định nghĩa 3 dashboard/18 questions, SQL template, filter mapping và cấu hình hình thức; hàm `dashboard_specs() -> dict`            |
| `scripts/metabase_provision.py`                              | API client tối thiểu và `provision()`: tạo/nhận diện collection, kết nối, questions, dashboard; kiểm preflight; lưu catalog        |
| `tests/test_metabase_unit.py`                                | Kiểm tra specs/payload, HTTP giả lập, filter mappings và chạy provision lại                                                              |
| `tests/test_metabase_sql.py`                                 | Kiểm tra view/KPI/quyền bằng PostgreSQL qua fixture engine; sửa dữ liệu thử trong transaction rollback                                  |
| `docs/metabase.md`                                           | Hướng dẫn chạy, filter, định nghĩa KPI, chụp hình, backup/restore và xử lý lỗi                                                    |
| Sửa `src/etl/run_etl.py`                                    | Chạy SQL 06 sau checks/marker, trước commit; không thay cơ chế commit hiện tại                                                         |
| Sửa `.gitignore`                                            | Bỏ qua `.runtime/`, `.env`, dữ liệu xuất và evidence local; model giữ trong volume                                            |
| Sửa `README.md`, `docs/plan.md`                           | Thêm liên kết BI tùy chọn, ghi rõ phần mở rộng so với scope cũ                                                                      |

Không copy nguyên module repo gốc: chỉ tái sử dụng mẫu API stdlib, catalog, cấu hình chart và mẫu Compose. Không đưa tên `marts.*`, `ops.*` hoặc định nghĩa delivered GMV sang repo con. `postgres:5432` là endpoint nội bộ mới, trùng tên với repo gốc nhưng trỏ service riêng của project Compose này.

## 6. Review Focus và kiểm thử bắt buộc

1. **Fan-out/distinct:** đơn có nhiều item và review; doanh thu không nhân, số đơn theo nhiều danh mục không cộng sai — Task 2/3.
2. **Mẫu số/tập rỗng:** không review, không dòng khớp filter, bang ít mẫu — Task 2/3; NULL thay cho tỷ lệ giả bằng 0.
3. **Full refresh/FAIL:** view và quyền được phục hồi; phiên check FAIL hoặc thiếu check không trả số liệu — Task 2/4.
4. **Chạy provision lại:** không sinh bản trùng, không xóa nội dung chỉnh tay, catalog sai ID phải dừng — Task 3/4.
5. **Restart và scope filter:** giữ dashboard qua restart; các card nhận cùng filter; schema inclusion không thay thế quyền SQL — Task 1/3/4.

### Task 1 — Docker Compose toàn bộ stack và quyền đọc (TV1; ước lượng 4–6 giờ)

**Files:** compose.yml, Dockerfile, requirements-docker.txt, .dockerignore, scripts/docker_init.py, scripts/docker_bootstrap_db.py; `.gitignore`; `docs/metabase.md` phần chạy Compose.

**Interfaces:** Input là source repo và 8 CSV ETL trong data/. Output là stack tại mục 2.1, `.env` mode 600, API Metabase ở `http://127.0.0.1:3000`, Streamlit ở `http://127.0.0.1:8501`. Container dùng `/app` làm working directory để các đường dẫn PROJECT_ROOT hiện tại tiếp tục đúng.

- [x] Xác minh image tags/digests và CPU hỗ trợ; lock Python dependencies theo imports thực tế. Build image, thử import ETL/Streamlit/DSS/SciPy và chạy unit tests trong container; không xem environment.yml là lock đủ cho pip.
- [x] Tạo bootstrap độc lập với file env/DB; xác nhận chạy lại giữ secrets. Compose chỉ khởi động dịch vụ cần thiết, không chạy job phá snapshot bằng up/restart; secrets không có giá trị mặc định dùng được.
- [x] Tạo roles nếu thiếu, không đổi password role đang có; btl là owner DW không superuser. App-DB owner chỉ dùng ở metabase-db; `metabase_ro`: NOSUPERUSER, NOCREATEDB, NOCREATEROLE, không membership role ghi; chỉ CONNECT + USAGE bi + SELECT view.
- [ ] Build/pull → DB healthy → bootstrap roles → ETL → train → Metabase/provision → app. Từ chối/giải thích rõ khi thiếu CSV, DB lỗi, thiếu model, cổng UI đã bị chiếm; không kill tiến trình khác. Kiểm tra app không source env.sh làm kết nối nhầm localhost.
- [x] Kiểm chứng recreate/stop/start giữ DW, model và dashboard. Backup hai DB bằng pg_dump trong tools hoặc service PostgreSQL, restore sang DB tạm; model volume có phương án backup. Không đọc/xuất credentials ra log hoặc kết quả docker compose config.
- [ ] Kiểm tra từ clone sạch trên máy có Docker nhưng không có runtime host; xác nhận volumes không đụng `.pgdata` cũ và data mount read-only. Ghi giới hạn platform thực sự đã thử. Chưa commit/push tự động; gom diff theo task để review.

### Task 2 — View BI và gate chất lượng (TV1 + TV2; ước lượng 2–3 giờ)

**Files:** SQL 06, run_etl.py, `tests/test_metabase_sql.py`.

**Interfaces:** `bi.dataset_status`, `bi.sales_items`, `bi.delivery_orders` theo mục 3.2; toàn bộ SQL 06 chạy được cả khi chưa tạo role BI.

- [ ] Viết test trước cho grain, totals, status không có check/thiếu check/FAIL và quyền chỉ đọc. Test dữ liệu nhỏ dùng schema/database thử riêng hoặc transaction rollback; không sửa bộ Olist active rồi commit.
- [x] Tạo view và tích hợp điểm gọi SQL 06. Bổ sung `scripts/docker_bootstrap_db.py` áp dụng SQL 06 cho DW đã nạp để không buộc chạy lại ETL chỉ vì cài BI.
- [x] Kiểm tra quyền thật bằng kết nối role Metabase: SELECT view được; SELECT staging và UPDATE/INSERT/DELETE fact bị từ chối. Đừng dùng owner `btl` để chứng minh read-only.
- [x] Chạy ETL hai lần trên DB thử; xác nhận view còn tồn tại, grants còn đúng, KPI không đổi và run ID cập nhật. Gây một check FAIL trong transaction thử, xác nhận cả hai view dữ liệu trả rỗng trong khi status chỉ ra lỗi.
- [ ] Đối chiếu doanh thu/số đơn/tháng với `mv_monthly_kpi` cùng phạm vi; so late/review trực tiếp fact và kiểm tra nguồn. Không dùng view BI làm cả expected lẫn actual.

### Task 3 — Tạo 3 dashboard và filter qua API (TV2; ước lượng 3–4 giờ)

**Files:** `src/bi/metabase.py`, `scripts/metabase_provision.py`, `tests/test_metabase_unit.py`, SQL tests từ Task 2.

**Interfaces:** `dashboard_specs() -> dict` chứa key dashboard, key question E1…D5/status, SQL, template tags, display/settings và layout. CLI `python scripts/metabase_provision.py` chạy trong tools, nhận env do Compose cấp từ `.env`, gọi `http://metabase:3000`, ghi `.runtime/metabase/catalog.json` chứa IDs, không chứa password/session token.

- [x] Viết test specs có đúng 3 dashboard, 15 data + 3 status questions; không SQL trực tiếp join hai fact; time grain chỉ có month/quarter/year; filter ngày/vùng/bang và riêng Sales có category.
- [x] Viết SQL cùng định nghĩa mục 3; dùng native template tags/bindings đúng API bản chạy. Với field filters, chờ schema sync có đủ field IDs rồi map; timeout có lỗi rõ. Whitelist time grain, không nối raw user input vào SQL.
- [x] Xác nhận UI OSS của bản pin hỗ trợ combo/bubble/pivot. Nếu S4 không có tô màu thì giữ pivot table; nếu chart khác không render thì task chưa đạt, không thay bằng ảnh số liệu giả.
- [x] Provision lần đầu sau preflight status.ready; xác nhận connection thật là postgres:5432/olist_dw/metabase_ro, tách khỏi metabase-db:5432/metabase_app. Dùng IDs trong catalog khi chạy lại; catalog mất thì nhận diện theo key/tên cố định trong collection riêng và dừng khi có nhiều ứng viên.
- [x] Lần chạy mặc định chỉ tạo phần thiếu; không ghi đè SQL/layout đã chỉnh tay. Nếu ID bị xóa hoặc sai connection thì dừng, không tạo trùng. Trước cập nhật có chủ ý, backup định nghĩa và ghi rõ danh sách objects bị thay.
- [ ] API client có timeout/HTTP errors, không in body có thể chứa secrets; dùng urllib/json hiện có trong Python chuẩn. Kiểm thử mô phỏng lỗi giữa chừng rồi chạy tiếp không tạo dashboard trùng.
- [x] Kiểm tra E5 đạt tỷ trọng cuối 100% khi tổng dương; S2 chọn cùng top5 qua các kỳ; S3 giữ doanh thu nhóm Other; D4 tổng số đơn đúng và D5 dùng mẫu số có review.

### Task 4 — Đối chiếu, ảnh và bàn giao báo cáo (TV2 + TV3; ước lượng 2–3 giờ)

**Files:** `docs/metabase.md`, README/plan; ảnh được chọn ở `docs/screenshots/metabase/`; report chỉ cập nhật sau nghiệm thu.

- [x] Chạy unit/SQL tests và regression `python -m pytest tests -q` bằng tools. Ghi PASS/FAIL/SKIP rõ; DB tests bị skip nghĩa là gate SQL chưa đạt. `engine` phải trỏ postgres:5432, không dùng DB host; chạy checks cố tình làm hỏng trong DB thử/transaction rollback.
- [x] Gọi thực tế cả 18 questions qua API; không lỗi SQL/permission, không card trống ngoài tập rỗng có chủ đích. Lưu tên question, filter, thời điểm, run ID, kết quả đối chiếu và phiên bản Metabase.
- [x] Đối chiếu tất cả 15 data cards với SQL độc lập từ fact/dimension; API JSON được so tiền với sai số tuyệt đối < 1e-6 BRL và tỷ lệ < 1e-9 trước format. Thử full range, 2018 + SP/RJ + nhiều danh mục (Sales), một tháng, tháng không có dữ liệu, một vùng và nhiều bang giao nhau.
- [ ] Thử filter tháng/quý/năm trên E3/E4/S2/D2; KPI và các card không có trục thời gian giữ nguyên tổng cho cùng cửa sổ. Kiểm tra nút clear filters và chọn lại không để lại tham số cũ.
- [x] Chạy provision hai lần và restart: database/collection/question/dashboard IDs và card chỉnh tay giữ nguyên. Sau full refresh thử lại quyền đọc bằng metabase_ro và refresh UI.
- [x] Trước chụp hình: dừng ETL, refresh toàn dashboard, xác nhận status READY và cùng run ID. Xem thực tế trên trình duyệt: không nhãn bị cắt, legend che dữ liệu, trục % hiển thị như tiền hay card báo lỗi.
- [x] Lưu 3 ảnh toàn dashboard và 4 ảnh chi tiết E5/S2/D3/D5. Mỗi hình có caption ghi bộ lọc, định nghĩa KPI, run ID; kèm bảng aggregate để nhóm có thể vẽ lại hình khi cần. Không xuất ID đơn/khách.
- [ ] Trong report, đưa Executive/Sales vào chương OLAP, Delivery vào phần cơ sở bài toán DSS; ghi mô tả → bằng chứng → hàm ý quản trị. Không gọi tỷ lệ review xấu theo độ trễ là tác động nhân quả hoặc lợi ích tài chính đã đạt.

## 7. Lệnh vận hành và nghiệm thu

**Đã hiện thực và chạy trên Linux amd64 ngày 14/11/2026.** Xem [biên bản nghiệm thu](metabase_acceptance.md) để phân biệt gate đã đạt và các mục còn mở. Chạy từ root repo con; host chỉ cần Docker/Compose và các CSV trong data/. Các job được gọi tuần tự; chỉ chuyển bước nếu exit code 0.

Đường chạy mặc định hiện tại là build image, chạy bootstrap tạo `.env` một lần, rồi `docker compose up -d`; bốn job init được Compose điều phối tự động. Khối lệnh dưới đây giữ lại cách chạy từng bước để kiểm tra hoặc sửa lỗi. Khi tự refresh snapshot, recreate app sau train để xóa cache Streamlit.

```bash
# Lần đầu: build không cần env; bootstrap không khởi động các DB.
 docker compose build app tools bootstrap
 docker compose run --rm --no-deps bootstrap
 docker compose config --quiet
 docker compose up -d --wait postgres metabase-db
 docker compose run --rm tools python scripts/docker_bootstrap_db.py
# Nạp vào volume DW mới; lần sau chỉ chạy lại khi muốn thay snapshot.
 docker compose run --rm tools python src/etl/run_etl.py
 docker compose run --rm tools python src/dss/train_model.py
 docker compose up -d --wait metabase
 docker compose run --rm tools python scripts/metabase_provision.py
 docker compose up -d --wait app
 docker compose run --rm tools python -m pytest tests/test_metabase_unit.py -q
 docker compose run --rm tools python -m pytest tests/test_metabase_sql.py -q
 docker compose run --rm tools python -m pytest tests -q
# Dừng toàn stack, giữ named volumes.
 docker compose down
```

Những lần sau dùng `docker compose up -d --wait postgres metabase-db metabase app` (thêm prefix rtk nếu có); không chạy lại ETL/train khi snapshot không đổi. Không chạy lại train chỉ vì cài BI. Nếu đã thay snapshot qua ETL, train lại trước demo DSS và recreate app để xóa cache model/dữ liệu trong bộ nhớ; refresh Metabase và xác nhận run ID.

Lệnh kiểm thử SQL phải được chạy với database thử đã nạp khi nghiệm thu các tình huống phá dữ liệu/full refresh; cấu hình tools cho PGDATABASE của DB thử và không cho Metabase demo kết nối vào DB đó. Không dùng test đang skip làm bằng chứng kết nối container thành công.

Compose cấp biến app DB riêng, không đổi `PGDATABASE=olist_dw` của app/tools. `.env`, log, backup DB và catalog để local; ảnh/tables public-safe được chọn mới đưa vào Git. Không in `docker compose config` đầy đủ có secrets vào báo cáo; dùng `config --quiet` để kiểm cấu hình.

## 8. Tiêu chí hoàn tất và giới hạn bằng chứng

- [x] Cả ba dashboard hiển thị đủ 15 card dữ liệu và trạng thái ETL; filter hoạt động và số liệu đã đối chiếu.
- [x] Role BI read-only được thử thực tế; full refresh không làm mất quyền đọc/view; FAIL/thiếu checks không hiển thị dữ liệu được chứng nhận.
- [x] Restart và chạy provision lại giữ objects, không ghi đè chỉnh tay; có backup application DB được thử restore ở DB tạm.
- [x] Có 7 ảnh đã xem trực quan, bảng aggregate tương ứng và caption đủ provenance.
- [ ] README/plan/report phân biệt tính năng đã chạy với phần dự kiến; core tests không có regression do BI.
- [ ] Clone sạch chạy được toàn bộ qua Compose, không cần runtime trên host; hai PostgreSQL không publish cổng host; restart/recreate giữ DW, models và dashboards. Có ghi digest/platform và kết quả restore backup thực tế.

Tổng công sức ước lượng 11–16 giờ, đã tăng phần container hóa app/ETL/DSS; chưa gồm thời gian download, sửa lỗi môi trường hoặc review; có thể vượt quỹ trước hạn nộp. Làm từng task theo thứ tự, mỗi task có diff riêng; không hy sinh đối chiếu để đủ số hình. Trạng thái lập kế hoạch ban đầu chỉ dựa trên mã nguồn. Cập nhật nghiệm thu 14/11/2026: 86 test đạt, ETL hai lần đạt 43/43 checks, 108 lượt truy vấn API qua sáu bộ lọc đạt, recreate và restore DB tạm đạt. Những checkbox còn mở là phần chưa kiểm chứng đủ hoặc công việc biên soạn báo cáo.

## 9. Nguồn tham chiếu cho người triển khai

- Repo gốc: `../src/bi/metabase.py` (specs, native questions, format), `../scripts/metabase.py` (API stdlib, catalog, bảo toàn objects), `../docs/metabase.md` (quy tắc grain/tỷ lệ). Đây là đường dẫn từ root repo con khi nằm trong checkout hiện tại; clone độc lập không có các file cha, nên kế hoạch đã mô tả interface cần thiết ở trên.
- [Chạy Metabase bằng Docker](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker).
- [Thứ tự khởi động và healthcheck trong Compose](https://docs.docker.com/compose/how-tos/startup-order/).
- [Application database](https://www.metabase.com/docs/latest/installation-and-operation/configuring-application-database).
- [Tài liệu API](https://www.metabase.com/docs/latest/api); đối chiếu `/api/docs` của instance thực tế khi viết payload vì API phụ thuộc phiên bản.

Đã tra tài liệu chính thức ngày 14/11/2026 cho hướng Docker/application DB và Compose healthchecks. Đường dẫn `latest` có thể đổi; lúc triển khai dùng tài liệu đúng bản pin. Chưa pull/build image hoặc kiểm chứng Compose runtime, và chưa giả định API của repo gốc dùng nguyên vẹn được.
