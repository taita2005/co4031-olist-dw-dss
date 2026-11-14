# Metabase và Docker Compose

Đây là đường chạy bổ sung, giữ nguyên quy trình micromamba cũ. Compose dùng một PostgreSQL cho kho Olist, một PostgreSQL riêng cho cấu hình Metabase, cùng image Python cho ETL, huấn luyện, provision và Streamlit. Host cần Docker Engine/Desktop và Compose v2; cần 8 CSV ETL trong `data/` trước khi nạp kho.

## Lần chạy đầu

Chạy từ thư mục gốc của repo con. Bootstrap không cần Python trên host hoặc file `.env` có sẵn. Nếu muốn xem trước các khóa cấu hình, chỉ khi chưa có `.env` hãy sao chép mẫu bằng `cp .env.example .env`; các mật khẩu trong mẫu để trống. Lệnh đầu tiên không ghi đè `.env` hiện có:

```bash
docker compose build
docker compose run --rm --no-deps bootstrap
docker compose config --quiet
docker compose up -d
```

Compose tự đọc `.env`. Bootstrap sinh mật khẩu ngẫu nhiên cho khóa đang để trống, giữ mật khẩu và cổng đã có, ghi `.env` với quyền `0600` và tạo `.runtime/`. `.env.example` là mẫu không chứa secrets; không đưa `.env` hoặc nội dung `docker compose config` lên Git/báo cáo. Nếu cổng 3000 hoặc 8501 đang được dùng, đổi `METABASE_PORT` hoặc `STREAMLIT_PORT` trong `.env`; service nội bộ vẫn dùng cổng 3000 và 8501.

ETL kiểm tra đủ 8 CSV trước khi tải. Nếu chưa có dữ liệu, job dừng với lỗi file cụ thể. Job ETL tự động chỉ tải khi cả hai fact table đều chưa có; nếu cả hai đã có và chứng nhận chất lượng mới nhất đạt thì bỏ qua. Partial DW hoặc quality checks thiếu/fail dừng an toàn, không tự ghi đè. Sau khi ETL đạt chất lượng, model được huấn luyện nếu chưa có hoặc mang `etl_run_id` cũ. App preflight xác nhận view BI sẵn sàng và model mang cùng `etl_run_id` với lần ETL mới nhất.

Trong lần cài đặt đầu tiên, hãy tạo `.env` và đặt đủ 8 CSV trong `data/` trước lệnh `up`. Compose đọc `.env` để nội suy cấu hình trước khi khởi động container, nên bước bootstrap tạo `.env` vẫn là lệnh thủ công một lần. `docker compose up -d` sau đó tự chạy các job theo thứ tự: tạo role database; chỉ nạp ETL khi cả hai fact chưa tồn tại; huấn luyện nếu model thiếu hoặc thuộc ETL run cũ; chờ Metabase sẵn sàng rồi provision các object còn thiếu; cuối cùng khởi động app. `up -d` vẫn chờ các job phụ thuộc hoàn tất trước khi app chạy. DW có cả hai fact và trạng thái quality đạt sẽ được giữ nguyên; partial DW hoặc quality check thiếu/fail dừng fail-closed. Nếu model và metadata đã khớp run hiện tại, training được bỏ qua. Provision mặc định không dùng `--upgrade`, vì vậy giữ định nghĩa và chỉnh sửa thủ công hiện có. Khi chủ động chạy lại một bước, dùng `tools` trong profile `jobs` như hướng dẫn bên dưới.

Mở Metabase tại `http://127.0.0.1:3000` và Streamlit tại `http://127.0.0.1:8501` (hoặc các cổng đã đặt). Chỉ hai giao diện này được bind lên loopback của host. PostgreSQL không publish cổng host. Tài khoản đầu tiên do provision script tạo từ thông tin trong `.env`; không bật public sharing, embedding, sample content hoặc anonymous tracking. Cơ sở dữ liệu ứng dụng Metabase là `metabase-db`/`metabase_app`; dữ liệu Olist được Metabase đọc riêng qua `postgres:5432/olist_dw` bằng `metabase_ro`.

## Chạy lại và dừng

Khi volume đã có dữ liệu, lệnh thông thường vẫn là:

```bash
docker compose up -d --wait postgres metabase-db metabase app
```

Với lệnh này, các job init vẫn được Compose kiểm tra; database/model đã sẵn sàng sẽ được bỏ qua và provision mặc định giữ các object/chỉnh sửa tay. Không chạy lại `docker_bootstrap_db.py`, ETL hoặc train nếu snapshot không đổi. Nếu chủ động nạp snapshot mới trong khi app đang chạy, chạy ETL qua `tools`, sau đó recreate các job/model và app để làm mới model cùng cache của Streamlit:

```bash
docker compose run --rm tools python src/etl/run_etl.py
docker compose up -d --force-recreate train-init metabase-init app
```

`tools` và `bootstrap` nằm trong profile `jobs`, nên không được tự khởi động. `.runtime/metabase/catalog.json` lưu ID object cục bộ, không chứa session token hay password. Nếu ID trong catalog không còn hợp lệ, script dừng để tránh tạo object trùng.

Chạy nghiệm thu API sau khi provision để thực thi đủ 18 câu hỏi trên các bộ lọc mẫu và đối chiếu tổng hợp với fact/DW. Lệnh ghi CSV cùng `verification.json` vào `.runtime/metabase/acceptance/`:

```bash
docker compose run --rm tools python scripts/metabase_verify.py
```

Để áp dụng có chủ ý SQL, cấu hình biểu đồ, filter mapping hoặc layout được quản lý, dùng `--upgrade`. Script lưu JSON định nghĩa question/dashboard hiện tại dưới `.runtime/metabase/backups/` trước khi cập nhật; object thủ công còn trong collection được đặt phía dưới các card quản lý.

```bash
docker compose run --rm tools python scripts/metabase_provision.py --upgrade
```

```bash
docker compose down
```

Lệnh này giữ named volumes. Không dùng `down -v` nếu chưa chủ ý xóa cả hai database và model. Volume model dùng chung giữa `tools` và `app`; có thể sao lưu cùng thư mục runtime:

```bash
docker compose run --rm tools tar -czf /app/.runtime/models.tar.gz -C /app/models .
docker compose exec -T postgres pg_dump -U postgres -d olist_dw > .runtime/olist_dw.sql
docker compose exec -T metabase-db pg_dump -U metabase_app -d metabase_app > .runtime/metabase_app.sql
```

Thử phục hồi vào hai database tên mới, không ghi đè volume demo đang dùng:

```bash
docker compose exec -T postgres createdb -U postgres olist_dw_restore
docker compose exec -T postgres psql -U postgres -d olist_dw_restore -v ON_ERROR_STOP=1 < .runtime/olist_dw.sql
docker compose exec -T metabase-db createdb -U metabase_app metabase_app_restore
docker compose exec -T metabase-db psql -U metabase_app -d metabase_app_restore -v ON_ERROR_STOP=1 < .runtime/metabase_app.sql
```

Mật khẩu do Postgres lưu lúc khởi tạo không tự đổi khi sửa `.env` sau này.

## Ba dashboard và KPI

Tất cả query dữ liệu bắt đầu bằng việc kiểm tra `bi.dataset_status.ready`; câu hỏi chỉ trả số liệu tổng hợp. `bi.sales_items` có grain một item, `bi.delivery_orders` có grain một đơn. Hai fact không được join trực tiếp. Các view có `order_id` chỉ dùng nội bộ để `COUNT(DISTINCT ...)`, không dùng làm export công khai.

- **Executive:** E1 tổng `price` (BRL); E2 số đơn distinct; E3 doanh thu theo tháng/quý/năm; E4 số đơn và AOV theo kỳ; E5 Pareto doanh thu theo bang, tính tỷ trọng lũy kế trên toàn phạm vi lọc và giữ cả bang đồng hạng.
- **Sales OLAP:** S1 top 10 danh mục; S2 chọn top 5 trên toàn cửa sổ lọc rồi giữ nguyên danh sách qua các kỳ; S3 top 5 và nhóm phần còn lại theo vùng; S4 ma trận vùng × top 10 ở dạng bảng số; S5 doanh thu theo bang. S4 dùng bảng Metabase OSS làm phương án tương thích.
- **Delivery Quality:** D1 cho thấy riêng mẫu số đơn giao đủ ngày và đơn có review; D2 tính tỷ lệ lại từ số đếm mỗi kỳ; D3 chỉ vẽ bang có tối thiểu 50 đơn; D4 nhóm ngày trễ; D5 review xấu theo nhóm ngày trễ, mẫu số chỉ gồm đơn có review. Đây là mô tả tương quan, không phải bằng chứng nhân quả.

Ngày mua dùng cửa sổ `[ngày bắt đầu, ngày kết thúc)`, mặc định 01/01/2017 đến trước 01/09/2018. Có thể chọn vùng, nhiều bang và (riêng Sales) nhiều danh mục. Grain chỉ nhận `month`, `quarter`, `year`. Sales loại `canceled` và `unavailable`; doanh thu là tổng giá sản phẩm, freight tách riêng. Địa chỉ bang là địa chỉ mới nhất gắn với `customer_unique_id`, không nhất thiết là nơi ở thời điểm phát sinh đơn. Delivery quy danh mục theo item giá cao nhất của đơn trong fact, nhưng dashboard không dùng trường này để kết luận cả đơn thuộc một danh mục.

View status đòi hỏi đủ 27 SQL checks và 16 source checks với đúng tên contract, cùng run marker cho lần load mới nhất và không có check fail. Thiếu check, load chưa hoàn tất hoặc một check fail làm hai view dữ liệu rỗng. ETL tạo lại view và grants sau khi ghi check và run marker nhưng trước commit; SQL lỗi sẽ rollback lần tải đó.

## Kiểm tra và giới hạn

Chạy bằng image `tools`:

```bash
docker compose run --rm tools python -m pytest tests/test_metabase_unit.py -q
docker compose run --rm tools python -m pytest tests/test_metabase_sql.py -q
docker compose run --rm tools python -m pytest tests -q
```

Test database cần ETL đã chạy trong PostgreSQL của Compose. Test quyền dùng riêng kết nối `metabase_ro`; không xem test bị skip vì DB không truy cập được là pass.

Image app pin Python 3.12.12, image kho/app DB pin PostgreSQL 16, Metabase OSS pin v0.64.1 và digest. Kết quả build, ETL, tests, 108 lượt API đối chiếu, quyền BI, recreate, backup/restore và ảnh trình duyệt đã nghiệm thu được ghi tại [docs/metabase_acceptance.md](metabase_acceptance.md); các giới hạn còn lại cũng được nêu ở đó. Các digest hiện trong Compose là amd64; ARM64 chưa được xác nhận. View `bi` giữ ID cấp đơn/item bên trong để đếm đúng grain; role read-only ngăn ghi dữ liệu nhưng không ngăn admin Metabase tự viết SQL đọc các ID này. Saved questions được quản lý và CSV evidence chỉ trả số liệu tổng hợp. Export Tableau không được tạo tự động.
