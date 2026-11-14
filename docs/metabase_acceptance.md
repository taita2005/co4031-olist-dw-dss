# Nghiệm thu Metabase + Docker Compose — 14/11/2026

Phạm vi: repo con `co4031-olist-dw-dss`, nhánh `feat/metabase-compose`. Luna hiện thực; agent điều phối chạy kiểm thử Docker, API và trình duyệt. Thay đổi được chia thành các commit chức năng; chưa push. Hướng dẫn vận hành: [metabase.md](metabase.md).

## Kết quả đã chạy

| Gate | Bằng chứng thực tế |
|---|---|
| Build | Python 3.12.12; 51 dependency được pin; PostgreSQL 16 và Metabase OSS v0.64.1 pin digest; Linux amd64 |
| Bootstrap | Sinh env riêng; chạy lại giữ nguyên nội dung, quyền `0600`, UID của người dùng host |
| ETL | Hai lần nạp thành công, mỗi lần **43/43 checks**; `fact_sales` 112.650 dòng, `fact_delivery` 96.470 dòng |
| Snapshot | `etl_run_id = 2026-11-14 05:55:56.907810`; view status READY, 43 checks, 0 fail |
| DSS | Train trong container; model trong named volume, cùng ETL run ID; Streamlit healthy; preflight thử thực tế chấp nhận model hiện tại, từ chối thiếu model và model cũ |
| Regression | `python -m pytest tests -q`: **86 passed**, không skip (44,98 giây); sau chỉnh layout cuối, unit/SQL BI **9 passed** (1,15 giây) |
| API/đối chiếu | **108/108 lượt**: 18 questions × 6 bộ lọc (mặc định, 2018 + SP/RJ + hai danh mục Sales, quý, năm, một tháng, tập rỗng); đủ 15 data cards được đối chiếu fact/dimension; tiền sai số tuyệt đối < 1e-6 BRL, tỷ lệ < 1e-9 |
| Quyền BI | Test kết nối `metabase_ro`: đọc BI được; đọc staging và ghi fact bị từ chối; gate FAIL/thiếu checks kiểm tra trong transaction rollback |
| Provision/recreate | Ba dashboard, 18 questions; recreate Metabase/app vẫn healthy; provision mặc định giữ ID và card thủ công thử nghiệm |
| Backup/restore | Dump cả hai DB; phục hồi vào DB tạm riêng: kho có 112.650/96.470 dòng và READY; application DB có 3 dashboard/18 questions; model có bản tar |
| Trình duyệt | Ba dashboard render thực tế, không lỗi JavaScript; S4 dùng bảng số trên Metabase OSS |

Các artifact riêng máy nằm trong `.runtime/` và không đưa vào Git: catalog IDs, backup định nghĩa, dump database và model. Dump kho chứa dữ liệu chi tiết; không dùng làm artifact công khai. Bản chọn lọc gồm [15 bảng tổng hợp và verification JSON](evidence/metabase/) được lưu cùng docs; đã kiểm tra không có cột ID đơn/item/khách hàng.

## Nghiệm thu chuỗi job tự khởi tạo — 14/11/2026

Compose đã bổ sung `db-init`, `etl-init`, `train-init`, `metabase-init`. Sau khi `.env` được tạo một lần và có đủ 8 CSV, `docker compose up -d` tự chạy các job; app chờ train và provision thành công. Train và provision có thể chạy song song sau ETL. `tools` vẫn dùng được độc lập để sửa lỗi.

| Trường hợp | Kết quả đã thực thi |
|---|---|
| Source copy, ba volumes mới | Project riêng `olist_auto_init_check`; `up -d` tự tạo roles, ETL **43/43 checks**, train model và tạo dashboard; app khởi động thành công. ETL run `2026-11-14 07:57:07.898165` |
| Dashboard được tạo tự động | Verifier **108/108 lượt API**, đủ 15 data cards đối chiếu SQL từ fact/dimension |
| Chạy `up -d` lần hai | Log xác nhận ETL/train skipped; fingerprint ETL run, model, metadata và định nghĩa dashboard/question không đổi |
| Quality FAIL | Chỉ thay một check trên DB thử, dừng app rồi chạy `up -d`: trả lỗi, app không khởi động và ETL run ID không đổi. Phục hồi check trong `finally`, chạy lại thành công |
| Stack demo đang có dữ liệu | Bốn job exit 0; ETL/train skipped; fingerprint kho, model và toàn bộ định nghĩa dashboard/question của người dùng giữ nguyên. Cả bốn dịch vụ dài hạn healthy |
| Regression | **102 passed**, không skip (46,23 giây); focused bootstrap/pipeline/Metabase unit **22 passed** |

Môi trường thử có source, `.env`, cổng UI, network và volumes riêng; CSV được mount read-only. Không dùng `--upgrade` trong job provision. Thử nghiệm source copy trên cùng máy Linux amd64 không thay thế kiểm thử từ clone sạch trên máy thứ hai/Windows/ARM64.

Khi chủ động chạy ETL mới trong lúc Streamlit đang mở, cần recreate app sau train để xóa cache; xem hướng dẫn refresh trong [metabase.md](metabase.md). `up -d` với app đã chạy không bảo đảm tự xóa cache Streamlit.

## Mở bản demo hiện tại

- [Executive](http://127.0.0.1:3300/dashboard/2): doanh thu, số đơn, xu hướng, AOV và Pareto bang.
- [Sales OLAP](http://127.0.0.1:3300/dashboard/3): top danh mục, xu hướng top 5, cơ cấu vùng và ma trận vùng–danh mục.
- [Delivery Quality](http://127.0.0.1:3300/dashboard/4): mẫu số, giao trễ, phân bố độ trễ và review xấu.
- [Streamlit DSS](http://127.0.0.1:8502): ứng dụng DSS hiện có.

Cổng 3300/8502 được chọn vì stack repo gốc đang dùng 3000/8501. Compose mặc định vẫn là 3000/8501; đổi cổng trong `.env`. Không có PostgreSQL nào được publish lên host.

## Dùng trong báo cáo

Đã thay cả 7 screenshot bằng ảnh chụp trực tiếp các dashboard sau chỉnh sửa của người dùng lúc 14:29 ICT ngày 14/11/2026 (07:29 UTC). Ảnh toàn dashboard chụp ở chiều rộng 1600 px; ảnh chi tiết lấy trực tiếp từ card hiện tại. Ba dashboard đều hiển thị READY, 43 checks, 0 fail và không ghi nhận lỗi JavaScript. Lượt cập nhật này chỉ chụp ảnh; các kết quả kiểm thử ở trên thuộc lần nghiệm thu trước.

Ảnh và bảng tổng hợp dùng ngày mua `[2017-01-01, 2018-09-01)`, nhóm theo tháng, toàn bộ vùng/bang/danh mục. Caption dưới đây cùng dùng ETL run ID nêu trên. CSV tương ứng nằm tại [docs/evidence/metabase/](evidence/metabase/); có thể tạo lại bằng `scripts/metabase_verify.py` vào `.runtime/metabase/acceptance/`.

| Hình | Caption gợi ý và CSV |
|---|---|
| [Executive](screenshots/metabase/Executive.png) | Tổng quan doanh thu giá sản phẩm bằng BRL, loại canceled/unavailable; số đơn distinct; `E1.csv`–`E5.csv` |
| [Sales OLAP](screenshots/metabase/Sales_OLAP.png) | Phân tích bán hàng theo danh mục, thời gian và vùng; top được chọn trên toàn cửa sổ lọc; `S1.csv`–`S5.csv` |
| [Delivery Quality](screenshots/metabase/Delivery_Quality.png) | Mẫu số giao đủ ngày và đơn có review được trình bày riêng; `D1.csv`–`D5.csv` |
| [E5](screenshots/metabase/E5.png) | “Doanh thu theo bang”: doanh thu và tỷ trọng lũy kế theo thứ tự giảm dần; `E5.csv` |
| [S2](screenshots/metabase/S2.png) | Xu hướng doanh thu của cùng top 5 danh mục qua các tháng; `S2.csv` |
| [D3](screenshots/metabase/D3.png) | Quy mô đơn và tỷ lệ giao trễ theo bang; chỉ bang có ít nhất 50 đơn; kích thước bubble là số đơn trễ; `D3.csv` |
| [D5](screenshots/metabase/D5.png) | Tỷ lệ review 1–2 sao trong các đơn có review, theo nhóm độ trễ; kèm quy mô mẫu review; `D5.csv` |

Executive/Sales cung cấp bằng chứng cho phần OLAP; Delivery cung cấp mô tả vấn đề để dẫn vào mô hình và kịch bản DSS. Các biểu đồ mô tả tương quan lịch sử; không chứng minh nguyên nhân hay khoản tiết kiệm đã đạt được. Docker đóng góp khả năng tái lập môi trường và quy trình demo, không làm tăng độ chính xác mô hình.

## Giới hạn và các gate chưa xác nhận

- Chưa nghiệm thu từ clone sạch trên máy thứ hai, Windows hoặc ARM64; chưa phát hành image registry để pull-only.
- Chưa tự động sửa nội dung báo cáo môn học. Ảnh/caption là đầu vào cho nhóm biên soạn, không thay thế đánh giá DSS hay rubric CO4031.
- S4 là ma trận bảng số, chưa có heatmap/pivot tô màu. Chưa kiểm tra thao tác clear/chọn lại mọi filter bằng chuột; API kiểm tra bộ lọc là bằng chứng riêng.
- Quyền read-only áp dụng ở PostgreSQL. View BI nội bộ vẫn có ID đơn/item để đếm distinct; admin Metabase có thể viết SQL đọc các ID đó. Cam kết không có ID chỉ áp dụng các saved questions/CSV tổng hợp được quản lý ở đây, không phải mọi truy vấn admin tự tạo.
- Restore kho phải thực hiện vào DB rỗng. Thử `pg_restore --clean` đè lên DB thử có partition báo lỗi constraint kế thừa; sau khi tạo lại DB thử rỗng, restore với `--exit-on-error` đạt.
