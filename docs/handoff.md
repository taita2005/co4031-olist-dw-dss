# Bàn giao — BTL CO4031 (Olist DW & DSS)

Cập nhật: 14/11/2026. Hạn nộp: **23:59 ngày 15/11/2026** (nộp 1 file ZIP lên LMS).

## Bối cảnh

Đây là bài tập lớn môn CO4031 – Kho dữ liệu & Hệ hỗ trợ quyết định (ĐH Bách khoa TP.HCM), nhóm 3 người. Đề bài nằm ở `CO4031_Assignment_HK261.pdf`.

Đề tài: kho dữ liệu bán hàng – giao hàng trên bộ dữ liệu Olist, cùng một DSS giúp quản lý vận hành quyết định: với ngân sách giới hạn, nên cải thiện giao hàng ở bang nào và cải thiện bao nhiêu để giảm tỷ lệ review 1–2 sao.

**Phần code đã xong và đã kiểm tra. `docs/report.md` đã cập nhật đủ theo code (14/11). Việc còn lại là điền TODO, chụp hình, báo cáo PDF, slide và nộp bài.**

Người dùng viết tiếng Việt. Khi có điểm chưa rõ thì hỏi lại, không tự đoán.

## Đọc gì trước

| File | Nội dung |
|---|---|
| `CLAUDE.md` | Lệnh chạy, kiến trúc code, các điểm dễ nhầm trong dữ liệu |
| `docs/report.md` | **Bản báo cáo thô đầy đủ** (5 section), mọi số liệu ở dạng bảng. Đây là nguồn để viết báo cáo PDF và slide |
| `docs/proposal.md` | Đề xuất đã duyệt, kèm bảng 12 điểm thay đổi so với bản đầu |
| `docs/plan.md` | Kế hoạch kỹ thuật; §1 là câu hỏi quyết định |
| `config/README.md` | Giả định chi phí của tối ưu ngân sách và kiểm tra "phí ship cao có giao nhanh hơn không" |
| `docs/metabase.md` | Phần mở rộng tuỳ chọn: Docker Compose + 3 dashboard Metabase |
| `README.md` | Hướng dẫn clone, chạy, xử lý sự cố, checklist review (tiếng Việt) |
| `data/README.md` | Link Kaggle và danh sách CSV cần đặt vào `data/` |

## Đã xong

1. **Môi trường:** micromamba cục bộ trong project. Thư mục `.env-btl/` chứa Python 3.12 và PostgreSQL 16, tạo từ `environment.yml` bằng `scripts/setup_env.sh`. Không cài gì vào hệ thống. Ngày 14/11 đã dựng lại env vì thư mục project bị chuyển chỗ (xem CLAUDE.md).
2. **Kho dữ liệu và ETL** (`src/sql/01–06`, `src/etl/`):
   - Dữ liệu đi theo luồng CSV → schema `staging` → schema `dw`, có metadata ở `meta.etl_log`.
   - `dw` là fact constellation: `fact_sales` (112,650 dòng) và `fact_delivery` (96,470 dòng) dùng chung 4 dimension. Có 3 materialized view.
   - Hợp đồng nguồn (`contracts.py`) và 43 kiểm tra chất lượng (`05_checks.sql` → `meta.check_result`). Lần chạy 14/11: 43/43 đạt, 12.3 s.
   - Đã đối chiếu: tổng tiền ở staging bằng ở dw (13,591,643.70); chạy lại ETL cho cùng kết quả.
3. **DSS** (`src/dss/`):
   - Cây quyết định dùng entropy, accuracy 79.7%, recall 56.8% cho lớp review xấu. Tham số chọn bằng CV 5-fold (`models/experiments.json`).
   - Có what-if, sensitivity, goal seeking, xếp hạng ưu tiên.
   - Tối ưu ngân sách (`optimizer.py`, MILP) và phân tích độ vững: ưu tiên 1 là **RJ, GO, PR, RN**; 40,000 BRL đưa tỷ lệ review xấu kỳ vọng 12.85% → 11.38%.
   - Model đã train lại ngày 14/11 ở `models/` (khớp `etl_run_id` của DW hiện tại).
4. **Dashboard Streamlit** (`src/app/`): Home, OLAP (đủ 5 phép toán, chọn được 1 trong 2 fact), Delivery, DSS (5 tab), Data Quality.
5. **Kiểm thử:** `python -m pytest tests -q` → 100 đạt, 2 bỏ qua (1 test cần chạy ETL 2 lần, 1 test chỉ chạy trong Docker).
6. **Phần mở rộng (PR #1, #2 của 2 bạn):** budget optimizer; Docker Compose + Metabase. Số liệu báo cáo không lấy từ Metabase.
7. **Tài liệu:** README, `data/README.md`, proposal, `docs/report.md` (đã bổ sung §2.5, §4.2.2, §4.3, §4.4.7 ngày 14/11), CLAUDE.md.
8. **Git / GitHub:** https://github.com/taita2005/co4031-olist-dw-dss, nhánh `main`.
   - `.gitignore` bỏ qua: CSV trong `data/`, `lectures/`, `.env-btl/`, `.pgdata/`, `.mamba/`, `.tools/`, `models/`, `.env`, `.runtime/`.
   - File đề PDF vẫn được đưa lên.

**Trạng thái máy hiện tại:**
- PostgreSQL **đang tắt**.
- `.pgdata/` đã có dữ liệu nạp ngày 14/11, `models/` đã có model mới.
- Muốn chạy app thì dùng: `source scripts/env.sh && bash scripts/db_start.sh && streamlit run src/app/Home.py`.

## Còn lại (theo thứ tự)

1. **Upload CSV lên Google Drive.** Đề §5.1 yêu cầu có `data/`, nhưng GitHub không chứa CSV. Sau khi có link thì ghi vào `data/README.md` và vào trang bìa trong `docs/report.md`.
2. **Chụp 22 hình** theo danh sách ở `docs/report.md` Phụ lục C (đã thêm hình 19–22 cho tab 5, bảng thực nghiệm, trang Data Quality). Cần bật DB và Streamlit để chụp. Sơ đồ ERD và schema có thể vẽ bằng dbdiagram.io hoặc Mermaid.
3. **Điền các chỗ `[TODO]` trong `docs/report.md`:**
   - số nhóm, thành viên, MSSV, % đóng góp; **sửa lại vai trò** trong bảng phân công (2 bạn đã có PR code, không chỉ review);
   - các link Drive, video;
   - **mục 5.4: 2–3 ví dụ DW/DSS ngoài thực tế có trích nguồn**, cần cho chuẩn đầu ra L.O.1.3. Chưa có, và không được bịa.
4. **Viết báo cáo PDF chính thức** từ `docs/report.md`. Đề không quy định template hay số trang. Nhóm chưa chọn công cụ (Word hay LaTeX) và ngôn ngữ, nên cần hỏi.
5. **Làm slide PDF.** Gợi ý chia slide 15 phút cho 3 người có ở `docs/report.md` Phụ lục E. Mọi thành viên đều phải trình bày.
6. **Quay video 10–15 phút** nếu nhóm không thuyết trình trực tiếp. Mọi thành viên phải xuất hiện, và link video ghi trên trang bìa. Nhóm chưa chọn hình thức thuyết trình (trực tiếp hay video), nên cần hỏi.
7. **Đóng gói ZIP:** báo cáo PDF + `src/` + `data/` (hoặc link) + slide PDF (+ link video). Nộp trước 23:59 ngày 15/11.

## Các quyết định đã chốt và lý do

| Quyết định | Lý do |
|---|---|
| Đề tài: giao trễ → review xấu trên dữ liệu Olist | Có sẵn dữ liệu thật (~100k đơn); đơn trễ có 62% review xấu, đơn đúng hạn chỉ 9%, nên bài toán có cơ sở rõ |
| Stack: Python + PostgreSQL + Streamlit | Miễn phí, chạy được trên macOS, một ngôn ngữ cho ETL, DSS và UI |
| Môi trường micromamba cục bộ là đường chạy chính; Docker Compose chỉ là tuỳ chọn (PR #2) | Máy không có Docker, Homebrew hay PostgreSQL; người dùng yêu cầu không đụng môi trường hệ thống |
| PostgreSQL chạy ở port 5433, user `btl`, auth trust | Tránh trùng port 5432 nếu máy có PostgreSQL khác; đây là server cục bộ chỉ dùng cho dev |
| Fact constellation gồm 2 fact | Review và ngày giao thuộc về cả đơn (grain đơn hàng), còn doanh thu ở grain item. Gộp chung sẽ đếm trùng. Cách này cũng khớp ví dụ "sales and shipping" trong slide Ch.3 |
| Khách hàng thật = `customer_unique_id` | `customer_id` sinh mới theo từng đơn |
| `fact_delivery` chỉ gồm đơn `delivered` có ngày giao; seller/product lấy theo item giá cao nhất | Chỉ những đơn này mới đo được trễ hay không; cần một khoá đại diện để phân tích theo danh mục |
| Không nạp geolocation | 1 triệu dòng, không cần cho bài toán; ghi vào phần hạn chế |
| Full refresh; `etl_log` đặt ở schema `meta` | Đơn giản, chạy lại không đổi kết quả; metadata phải giữ được qua các lần xoá `dw` |
| ROLAP + materialized view (có `GROUP BY CUBE`) | Đúng lý thuyết trong slide; không cần thêm OLAP server riêng |
| Cây quyết định dùng entropy (`max_depth=4`, `min_samples_leaf=200`, `class_weight=balanced`) | Cùng thuật toán với ví dụ tính tay trong slide Ch.5; cây nhỏ dễ giải thích; review xấu là lớp thiểu số |
| Xác suất review xấu = tỷ lệ thực tế của từng lá (`leaf_rate`), không dùng `predict_proba` | `class_weight` làm lệch `predict_proba`; tỷ lệ theo lá là mô hình "under risk" dễ giải thích |
| What-if chọn đơn trễ cần sửa theo cột `rand` (seed 42) | Kết quả tái lập được và giảm đơn điệu khi tăng mức giảm trễ |
| Goal seeking duyệt từng 1% (complete enumeration) | Đơn giản, dùng đúng thuật ngữ "blind search" trong slide Ch.7 |
| Thuật ngữ bám slide; khái niệm từ Kimball (grain, surrogate key) thì ghi rõ nguồn | Người dùng phải trình bày lại với thầy |
| UI và README viết tiếng Việt; comment trong code viết tiếng Anh | Người dùng chọn |
| Đổi tên `dataset/` thành `data/`; CSV không đưa lên GitHub | Khớp cấu trúc nộp bài; file nặng 120MB |
| Không đưa `lectures/` lên GitHub; vẫn đưa file đề | Slide là tài liệu của giảng viên; file đề để nhóm tham chiếu |
| 1 người code, 2 người review; cả 3 cùng thuyết trình | Code ít file, chia 3 người code không hiệu quả |
| Báo cáo gồm 5 section: Giới thiệu / Kho dữ liệu & ETL / OLAP / DSS / Đánh giá & kết luận | Người dùng muốn ngắn gọn theo các phần của hệ thống; thêm section DW và Đánh giá để đủ mục tiêu 2 và 5 của đề |

## Lưu ý cho phiên mới

- Nếu sửa SQL hoặc ETL: chạy lại `python src/etl/run_etl.py`, rồi `python src/dss/train_model.py`. **Sau đó cập nhật lại số liệu trong `docs/report.md`**, vì các số ở đó lấy từ lần chạy ngày 02/11 (đã đối chiếu lại ngày 14/11, không đổi).
- Số liệu trong report đều lấy từ truy vấn thật. Nếu cần thêm số, bật DB rồi truy vấn, không ước lượng.
- Sau khi bật PostgreSQL để làm việc thì nhớ tắt: `bash scripts/db_stop.sh`.
