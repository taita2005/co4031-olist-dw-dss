# Bàn giao — BTL CO4031 (Olist DW & DSS)

Cập nhật: 02/11/2026. Hạn nộp: **23:59 ngày 15/11/2026** (nộp 1 file ZIP lên LMS).

## Bối cảnh

Đây là bài tập lớn môn CO4031 – Kho dữ liệu & Hệ hỗ trợ quyết định (ĐH Bách khoa TP.HCM), nhóm 3 người. Đề bài nằm ở `CO4031_Assignment_HK261.pdf`.

Đề tài: kho dữ liệu bán hàng – giao hàng trên bộ dữ liệu Olist, cùng một DSS giúp quản lý vận hành quyết định nên cải thiện giao hàng ở bang hoặc danh mục nào, và cải thiện bao nhiêu, để giảm tỷ lệ review 1–2 sao.

**Phần code đã xong và đã kiểm tra. Việc còn lại là báo cáo, slide và nộp bài.**

Người dùng viết tiếng Việt. Khi có điểm chưa rõ thì hỏi lại, không tự đoán.

## Đọc gì trước

| File | Nội dung |
|---|---|
| `CLAUDE.md` | Lệnh chạy, kiến trúc code, các điểm dễ nhầm trong dữ liệu |
| `docs/report.md` | **Bản báo cáo thô đầy đủ** (5 section), mọi số liệu ở dạng bảng. Đây là nguồn để viết báo cáo PDF và slide |
| `docs/proposal.md` | Đề xuất đã duyệt, kèm bảng 12 điểm thay đổi so với bản đầu |
| `README.md` | Hướng dẫn clone, chạy, xử lý sự cố, checklist review (tiếng Việt) |
| `data/README.md` | Link Kaggle và danh sách CSV cần đặt vào `data/` |

## Đã xong

1. **Môi trường:** micromamba cục bộ trong project. Thư mục `.env-btl/` chứa Python 3.12 và PostgreSQL 16, tạo từ `environment.yml` bằng `scripts/setup_env.sh`. Không cài gì vào hệ thống.
2. **Kho dữ liệu và ETL** (`src/sql/01–04`, `src/etl/run_etl.py`):
   - Dữ liệu đi theo luồng CSV → schema `staging` → schema `dw`, có metadata ở `meta.etl_log`.
   - `dw` là fact constellation: `fact_sales` (112,650 dòng) và `fact_delivery` (96,470 dòng) dùng chung 4 dimension. Có 3 materialized view.
   - Đã đối chiếu: tổng tiền ở staging bằng ở dw (13,591,643.70); chạy lại ETL cho cùng kết quả.
3. **DSS** (`src/dss/`):
   - Cây quyết định dùng entropy, accuracy 79.7%, recall 56.8% cho lớp review xấu.
   - Có what-if, sensitivity, goal seeking và xếp hạng ưu tiên.
   - Model đã lưu ở `models/`.
4. **Dashboard Streamlit** (`src/app/`):
   - Gồm Home, OLAP (đủ 5 phép toán, chọn được 1 trong 2 fact), Delivery và DSS (4 tab).
   - Đã test bằng `streamlit.testing.v1.AppTest` và khởi động server thật.
5. **Tài liệu:** README, `data/README.md`, proposal (đã cập nhật), `docs/report.md`, CLAUDE.md.
6. **Git / GitHub:** đã push lên https://github.com/taita2005/co4031-olist-dw-dss, nhánh `main`.
   - `.gitignore` bỏ qua: CSV trong `data/`, `lectures/`, `.env-btl/`, `.pgdata/`, `.mamba/`, `.tools/`, `models/`.
   - File đề PDF vẫn được đưa lên.
   - Máy không có `gh`. Người dùng tự commit và push qua HTTPS.

**Trạng thái máy hiện tại:**
- PostgreSQL **đang tắt**.
- `.pgdata/` đã có sẵn dữ liệu đã nạp, `models/` đã có model.
- Muốn chạy app thì dùng: `source scripts/env.sh && bash scripts/db_start.sh && streamlit run src/app/Home.py`.

## Còn lại (theo thứ tự)

1. **Mời 2 bạn làm collaborator trên GitHub** (Settings → Collaborators), nếu người dùng chưa làm. Repo đã được push. *Không tự commit hay push nếu người dùng chưa yêu cầu.*
2. **Upload CSV lên Google Drive.** Đề §5.1 yêu cầu có `data/`, nhưng GitHub không chứa CSV. Sau khi có link thì ghi vào `data/README.md` và vào trang bìa trong `docs/report.md`.
3. **2 bạn review code** theo checklist ở README mục 6, sau đó sửa theo góp ý. Kế hoạch là review trong 03–07/11.
4. **Chụp 18 hình** theo danh sách ở `docs/report.md` Phụ lục C. Cần bật DB và Streamlit để chụp. Sơ đồ ERD và schema có thể vẽ bằng dbdiagram.io hoặc Mermaid.
5. **Điền các chỗ `[TODO]` trong `docs/report.md`:**
   - thành viên, MSSV, % đóng góp;
   - các link GitHub, Drive, video;
   - **mục 5.4: 2–3 ví dụ DW/DSS ngoài thực tế có trích nguồn**, cần cho chuẩn đầu ra L.O.1.3. Chưa có, và không được bịa.
6. **Viết báo cáo PDF chính thức** từ `docs/report.md`. Đề không quy định template hay số trang. Nhóm chưa chọn công cụ (Word hay LaTeX) và ngôn ngữ, nên cần hỏi.
7. **Làm slide PDF.** Gợi ý chia slide 15 phút cho 3 người có ở `docs/report.md` Phụ lục E. Mọi thành viên đều phải trình bày.
8. **Quay video 10–15 phút** nếu nhóm không thuyết trình trực tiếp. Mọi thành viên phải xuất hiện, và link video ghi trên trang bìa. Nhóm chưa chọn hình thức thuyết trình (trực tiếp hay video), nên cần hỏi.
9. **Đóng gói ZIP:** báo cáo PDF + `src/` + `data/` (hoặc link) + slide PDF (+ link video). Nộp trước 15/11.

## Các quyết định đã chốt và lý do

| Quyết định | Lý do |
|---|---|
| Đề tài: giao trễ → review xấu trên dữ liệu Olist | Có sẵn dữ liệu thật (~100k đơn); đơn trễ có 62% review xấu, đơn đúng hạn chỉ 9%, nên bài toán có cơ sở rõ |
| Stack: Python + PostgreSQL + Streamlit | Miễn phí, chạy được trên macOS, một ngôn ngữ cho ETL, DSS và UI |
| Môi trường micromamba cục bộ, không dùng Docker | Máy không có Docker, Homebrew hay PostgreSQL; người dùng yêu cầu không đụng môi trường hệ thống |
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

- Nếu sửa SQL hoặc ETL: chạy lại `python src/etl/run_etl.py`, rồi `python src/dss/train_model.py`. **Sau đó cập nhật lại số liệu trong `docs/report.md`**, vì các số ở đó lấy từ lần chạy ngày 02/11.
- Số liệu trong report đều lấy từ truy vấn thật. Nếu cần thêm số, bật DB rồi truy vấn, không ước lượng.
- Sau khi bật PostgreSQL để làm việc thì nhớ tắt: `bash scripts/db_stop.sh`.
