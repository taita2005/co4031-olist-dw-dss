# Kế hoạch hoàn thiện BTL CO4031 — Olist DW & DSS

Lập ngày: 03/11/2026 (thứ Ba, tuần 11). Hạn nộp: **23:59 Chủ nhật 15/11/2026** trên LMS.
Thuyết trình: tuần 13–15 (19/11, 26/11, 03/12) hoặc nộp video 10–15 phút kèm báo cáo.

Tài liệu này thay cho mục "Còn lại" trong `docs/handoff.md`. Phần "Các quyết định đã chốt" trong `handoff.md` vẫn giữ nguyên giá trị.

---

## 0. Tóm tắt

- **Nền là repo A** (repo này). A đã có DW, ETL, OLAP, cây quyết định và what-if, cùng `report.md` thô. Không chuyển sang kiến trúc của B.
- **Lấy từ B (`DW-DSS_Project`):**
  - bước *tối ưu ngân sách*, có so sánh với greedy và vẽ đường cong ngân sách – lợi ích;
  - ý tưởng *kiểm tra dữ liệu tự động* (grain, đối chiếu, cận tỷ lệ);
  - cách ghi rõ *giả định, không phải nhân quả*.
- **Học từ C (Coffee Shop):**
  - khung báo cáo học thuật (bìa, phân công, Mở đầu, sơ đồ ETL từng bảng, từ điển dữ liệu);
  - bảng so sánh các lần thực nghiệm;
  - kết thúc mỗi phân tích bằng mục *Diễn giải → Khuyến nghị*;
  - lưu model kèm tham số.
- **Tránh lỗi của C:**
  - số liệu không đối chiếu (doanh thu sai khoảng 34 lần);
  - văn chung chung không có số;
  - sót dấu vết công cụ AI;
  - báo cáo lệch code;
  - không có bài toán quyết định, không có chương Đánh giá.

## 1. Bài toán quyết định (duy nhất)

> **Với ngân sách cải thiện giao hàng có hạn, nên đầu tư vào những bang nào, và giảm bao nhiêu % đơn giao trễ ở mỗi bang, để giảm được nhiều review 1–2 sao nhất?**

| Thành phần | Nội dung |
|---|---|
| Người ra quyết định | Quản lý vận hành / logistics của sàn Olist |
| Biến quyết định | Mức giảm đơn trễ của từng bang: 0 / 25 / 50 / 75 / 100% |
| Biến kết quả | Số review xấu kỳ vọng tránh được (từ mô hình cây quyết định) |
| Ràng buộc | Tổng chi phí ≤ ngân sách; số bang được chọn ≤ K |
| Biến không kiểm soát | Hành vi đánh giá của khách hàng (nằm trong tỷ lệ review xấu của từng lá cây) |

Mọi thành phần của hệ thống phục vụ câu hỏi này, theo 4 pha của Simon:

| Pha | Thành phần | Trạng thái |
|---|---|---|
| Intelligence | DW + OLAP + trang Delivery: trễ có liên quan review xấu không, ở đâu | Đã có |
| Design | Cây quyết định (entropy), what-if, sensitivity, goal seeking | Đã có |
| Choice | **Tối ưu ngân sách (0-1 integer programming) so với greedy**, kèm xếp hạng ưu tiên | **Cần làm** |
| Implementation | Bảng khuyến nghị bằng câu chữ cho nhà quản lý | **Cần làm** |

Những phần **không** đưa vào bài toán:
- danh mục chỉ dùng để phân tích, không là biến quyết định;
- `days_faster` chỉ giữ trong tab what-if;
- điểm rủi ro có trọng số của B bị bỏ, vì nó là một cách xếp hạng thứ hai dễ mâu thuẫn với kết quả tối ưu.

## 2. Phạm vi

**Làm:**
1. Kiểm tra dữ liệu tự động và test.
2. Bộ tối ưu ngân sách và tab DSS mới.
3. Khuyến nghị bằng câu chữ.
4. Trang Data Quality.
5. Lưu metadata của model.
6. Viết lại báo cáo theo khung mới.
7. Slide, video (nếu có), đóng gói ZIP.

**Không làm** (chỉ ghi vào phần Hướng phát triển của báo cáo): dbt, Airflow, Metabase/Tableau, Docker, CI, fixture tổng hợp, SCD type 2, incremental load, bản đồ địa lý.
Lý do: còn 12 ngày, và nhóm phải giải thích được mọi thứ có trong bài khi thầy hỏi.

## 3. Phân công

Tên thật điền vào bảng phân công trong báo cáo. Không để AI tự điền.

| Vai trò | Người | Phụ trách code | Phụ trách báo cáo / slide |
|---|---|---|---|
| **TV1 — DW/ETL & tích hợp** | [điền tên] | Phase 1, 2, 4; chạy lại số liệu cuối | Chương 3–4; slide kiến trúc + DW |
| **TV2 — OLAP & chất lượng dữ liệu** | [điền tên] | Review `src/sql`, `src/etl`, các trang Home/OLAP/Delivery; viết test SQL (Phase 1) cùng TV1; chụp hình | Chương 1, 2, 5, 7.1; slide bài toán + OLAP |
| **TV3 — DSS & đánh giá** | [điền tên] | Review `src/dss`, trang DSS; viết test cho optimizer; chạy thực nghiệm (Phase 3) | Chương 6, 7, 8; tài liệu tham khảo; slide DSS + demo |

Cả 3 người đều phải thuyết trình (bắt buộc theo §4 của đề). Mỗi người trình bày phần mình phụ trách.

## 4. Các phase kỹ thuật

Quy tắc chung:
- Không commit thẳng lên `main`. Mỗi phase làm trên một nhánh riêng và có ít nhất một người khác review.
- Sau khi sửa SQL/ETL phải chạy lại `run_etl.py` và `train_model.py`.

### Phase 1 — Kiểm tra dữ liệu và test (03–05/11, TV1 + TV2) — ✅ xong 03/11 (nhánh `feat/data-checks`)

Kết quả: 25 kiểm tra trong `05_checks.sql`, tất cả đạt trên 2 lần chạy ETL liên tiếp. 23 test `pytest` đạt, gồm 7 trường hợp cố tình làm hỏng DW để chắc kiểm tra bắt được lỗi. Phần test cho optimizer chuyển sang Phase 2.

Mục tiêu: không bao giờ gặp lỗi kiểu C (doanh thu sai, nhân dòng) mà không biết.

| Việc | File | Tiêu chí xong |
|---|---|---|
| Thêm `src/sql/05_checks.sql`, chạy cuối ETL, ghi kết quả vào `meta.check_result(run_id, check_name, expected, actual, passed)` | `05_checks.sql`, `run_etl.py` | Mỗi lần chạy ETL ghi đủ các dòng kiểm tra; ETL in ra `FAIL` nếu có kiểm tra không đạt |
| Kiểm tra grain: `fact_sales` unique theo (order_id, order_item_id); `fact_delivery` unique theo order_id | | Đạt |
| Đối chiếu số liệu: số dòng và `SUM(price)` ở staging = dw (13.591.643,70); số đơn delivered có ngày giao ở staging = `fact_delivery` (96.470) | | Đạt |
| Ràng buộc miền giá trị: `review_score` ∈ [1,5]; `price`, `freight` ≥ 0; `is_late` ∈ {0,1}; tỷ lệ trong materialized view ∈ [0,1]; `dim_date` phủ hết ngày mua và ngày giao | | Đạt |
| Không có fact mồ côi (mọi khoá ngoại đều tìm thấy dimension) | | Đạt |
| Thêm `pytest` vào `environment.yml`; tạo `tests/test_dss.py` để kiểm tra: what-if giảm đơn điệu theo `late_reduction`; `goal_seek` trả `None` khi mục tiêu không đạt được; optimizer không vượt ngân sách và luôn ≥ greedy | `tests/` | `pytest` chạy xanh |
| Chạy ETL 2 lần, so số dòng và tổng tiền, chứng minh chạy lại cho cùng kết quả | ghi vào `report.md` §7 | Có bảng kết quả |

### Phase 2 — Bộ tối ưu ngân sách (04–06/11, TV1; TV3 review và viết test) — ✅ xong 03/11

Kết quả: `src/dss/optimizer.py`, `config/cost_assumptions.csv` (+ README giải thích giả định), `models/options.csv` (24 bang × 4 mức, tính trong khoảng 2,4 giây khi train), `tests/test_optimizer.py` (MILP khớp vét cạn; tổng 63 test đạt). Solver giải trong khoảng 0,02 giây.

**Chi phí (đã đổi so với Bước 2 ở dưới):** không còn bảng chi phí tự đặt theo vùng. Chi phí (BRL) = phí ship **thực tế** của các đơn trễ được sửa × `surcharge` (0,5) × `tier[mức]` (1 / 1,2 / 1,5 / 2). Chênh lệch giữa các bang lấy từ dữ liệu; chỉ 2 tham số là giả định. `surcharge` chỉ đổi thước đo ngân sách, không đổi phương án (đã có test). `tier` có ảnh hưởng: ở ngân sách 40.000 BRL, hệ số phẳng → sửa sâu ở 8 bang (RJ, SP 100%), mặc định → 19 bang, dốc → 20 bang mức nhẹ. Đây là nội dung cho phần phân tích độ nhạy.

Điều chỉnh so với dự kiến: greedy ban đầu (mỗi bang chọn 1 lần) là baseline quá yếu, nên đã đổi sang **greedy nâng cấp dần** (chọn bước nâng mức có lợi ích cận biên / chi phí cận biên cao nhất). Trên dữ liệu thật greedy này gần tối ưu khi không giới hạn số bang (chênh ≤ 1,1%), nhưng chênh 2,7–7,4% khi giới hạn K = 5 bang. Báo cáo cần nêu trung thực điều này.

File mới `src/dss/optimizer.py`.

**Bước 1 — Tính trước bảng lợi ích** (học cách làm cache của C). Hàm `build_options(bundle, df)`:
- Với mỗi bang có ≥ 100 đơn và mỗi mức r ∈ {25, 50, 75, 100}%, tính `benefit[s,r] = evaluate_scenario(bundle, df, scope=bang s, late_reduction=r)["bad_reviews_avoided"]`.
- `train_model.py` gọi hàm này và lưu kết quả vào `models/options.csv`, để dashboard không phải tính lại khi người dùng kéo slider.

**Bước 2 — Chi phí (giả định, phải ghi rõ trên UI và trong báo cáo).** File `config/cost_assumptions.csv` gồm `region, unit_cost` = chi phí giả định để biến 1 đơn trễ thành đúng hạn, theo vùng (North/Northeast cao hơn Southeast/South).

```
cost[s,r] = n_late[s] × r × unit_cost[region(s)] × tier[r]
tier = {25%: 1.0, 50%: 1.2, 75%: 1.5, 100%: 2.0}
```

`tier` tăng dần để thể hiện chi phí cận biên tăng: sửa những đơn trễ cuối cùng khó hơn. Nếu không có hệ số này, bài toán gần như tuyến tính và greedy luôn tối ưu, nên phần so sánh sẽ không có ý nghĩa.

**Bước 3 — Mô hình 0-1 integer programming** (bài toán multiple-choice knapsack; đúng thuật ngữ mô hình hoá ở Ch.7):

```
max  Σ_s Σ_r benefit[s,r] · x[s,r]
s.t. Σ_r x[s,r] ≤ 1                       với mọi s   (mỗi bang chọn tối đa 1 mức)
     Σ_s Σ_r cost[s,r] · x[s,r] ≤ B                    (ngân sách)
     Σ_s Σ_r x[s,r] ≤ K                                (số bang tối đa, tuỳ chọn)
     x[s,r] ∈ {0,1}
```

- **Solver:** dùng `scipy.optimize.milp`. SciPy đã có sẵn theo scikit-learn nên không thêm thư viện mới. Nếu nhóm muốn giống B thì dùng OR-Tools CP-SAT (`ortools` trên conda-forge); interface giữ nguyên.
- **Greedy baseline:** sắp các phương án theo benefit/cost giảm dần, mỗi bang chỉ lấy 1 mức, dừng khi hết ngân sách. Trả về cùng cấu trúc kết quả để so sánh.
- **`frontier(options, budgets)`:** lợi ích tối ưu theo từng mức ngân sách, dùng để vẽ đường cong ngân sách – lợi ích (đây là sensitivity của ngân sách).
- **`recommend(result)`:** sinh câu khuyến nghị bằng tiếng Việt, ví dụ: *"Với ngân sách 500 đơn vị: giảm 75% đơn trễ ở RJ, 50% ở BA… → dự kiến tránh ~N review xấu, tỷ lệ review xấu toàn quốc giảm từ 12,9% xuống X%."*

**Tiêu chí xong:**
- 27 bang × 4 mức tính xong dưới khoảng 30 giây trong `train_model.py`;
- optimizer giải xong dưới 1 giây;
- test ở Phase 1 chạy xanh;
- kết quả tối ưu ≥ greedy ở mọi mức ngân sách.

### Phase 3 — Giao diện DSS và khuyến nghị (05–07/11, TV1 code; TV3 kiểm tra kết quả)

Sắp lại `src/app/pages/3_DSS.py` theo luồng của bài toán:

| Tab | Nội dung | Thay đổi |
|---|---|---|
| 1. Mô hình | Metrics, luật IF-THEN, feature importance | Thêm cột "Diễn giải" bằng lời cho 5 luật rủi ro nhất |
| 2. Xếp hạng ưu tiên | `priority_ranking` theo bang | Giữ nguyên |
| 3. What-if & Sensitivity | Như hiện tại | Giữ nguyên |
| 4. Goal seeking | Như hiện tại | Giữ nguyên |
| **5. Tối ưu ngân sách** | Nhập ngân sách B và số bang K; bảng phương án tối ưu so với greedy; đường cong ngân sách – lợi ích; **hộp khuyến nghị**; nút tải CSV | **Mới** |

Ghi chú bắt buộc hiển thị trên tab 5 (học cách ghi của B):
- "Chi phí là giả định, đơn vị quy ước, không phải số liệu Olist."
- "Lợi ích là kỳ vọng từ mô hình, giả định giao trễ là nguyên nhân gây review xấu."

**Thực nghiệm cho báo cáo** (học bảng thực nghiệm của C; TV3 chạy và lưu vào `models/experiments.json`):
1. Cây quyết định với `max_depth` ∈ {3, 4, 5, 6} × `min_samples_leaf` ∈ {100, 200, 500}: accuracy, recall, F1, số lá. Bảng này dùng để lý giải vì sao chọn depth 4 / leaf 200.
2. Optimizer so với greedy ở 3 mức ngân sách (thấp / vừa / cao): lợi ích, chi phí, các bang được chọn, chênh lệch %.
3. Độ nhạy theo chi phí: tăng `unit_cost` vùng North thêm ±50%, xem phương án tối ưu có đổi không.

### Phase 4 — Trang Data Quality và metadata model (06–07/11, TV2)

- Trang `src/app/pages/4_Data_Quality.py`: lịch sử `meta.etl_log` (số dòng nguồn so với số dòng đã nạp theo từng lần chạy), kết quả `meta.check_result` của lần chạy gần nhất (đạt/không đạt), các quy tắc làm sạch dữ liệu.
- `train_model.py` ghi thêm vào `metrics.json`: `trained_at`, `params`, `n_rows`, `etl_run_id` (lấy từ `meta.etl_log`). Mọi số liệu trong báo cáo phải truy ngược được về `etl_run_id` này.

### Phase 5 — Đóng băng code và chốt số liệu (08/11, TV1)

1. Merge xong mọi nhánh, chạy lại toàn bộ: `run_etl.py`, `train_model.py`, `pytest`, rồi khởi động Streamlit và đi qua mọi trang.
2. Xuất số liệu cuối vào `docs/numbers.md`: mọi con số sẽ xuất hiện trong báo cáo và slide, kèm `etl_run_id` và câu SQL hoặc hàm sinh ra số đó.
3. Sau mốc này **không sửa logic nữa**, chỉ sửa giao diện hoặc chữ nếu cần. Nếu bắt buộc phải sửa logic thì làm lại từ bước 1 và cập nhật `numbers.md`.

## 5. Báo cáo PDF

Viết lại từ `docs/report.md` theo khung dưới đây (khung của C, nội dung của A + B). Số liệu **chỉ lấy từ `docs/numbers.md`**.

| Chương | Nội dung | Từ `report.md` hiện tại | Người viết |
|---|---|---|---|
| Bìa | Trường, môn, đề tài, GVHD, nhóm, thành viên + MSSV, **link GitHub / Drive / video** | Trang bìa (điền TODO) | TV2 |
| Bảng phân công | Tên, MSSV, việc làm cụ thể, % đóng góp | Bảng thành viên | Cả nhóm thống nhất |
| 1. Mở đầu | Lý do, mục tiêu (map với 6 mục tiêu của đề), phạm vi, phương pháp, bố cục | Mới (học C) | TV2 |
| 2. Bài toán và dữ liệu | Câu hỏi quyết định (§1 ở trên), người ra quyết định, mô tả 9 CSV, **bảng các điểm dễ nhầm trong dữ liệu** | §1.1–1.2 | TV2 |
| 3. Kiến trúc và ETL | Three-tier, sơ đồ luồng, **quy tắc transform cho từng bảng** (cleansing / mapping / business rule / attribute construction), `etl_log` | §1.3–1.4, §2.2 | TV1 |
| 4. Thiết kế kho dữ liệu | 4 đặc tính Inmon, data cube, fact constellation + **ERD**, grain, **từ điển dữ liệu**, measure cộng / không cộng được, partition, materialized view | §2.1, §2.3 | TV1 |
| 5. OLAP và dashboard | ROLAP, 5 phép toán, mỗi biểu đồ **kèm số thật**, kết thúc bằng "Ý nghĩa hỗ trợ quyết định" | §3 | TV2 |
| 6. Hệ hỗ trợ quyết định | 4 pha Simon và các subsystem của DSS; cây quyết định (information gain tính tay, **bảng so sánh tham số**, luật IF-THEN); mô hình rủi ro; what-if, sensitivity, goal seeking; **tối ưu ngân sách** (mô hình toán, so với greedy, đường cong ngân sách); **bảng khuyến nghị** | §4 + mới | TV3 |
| 7. Đánh giá | **Bảng đối chiếu số liệu**, kết quả `check_result`, test, chạy lại cho cùng kết quả, thời gian chạy (ETL, train, solver), mức đáp ứng 6 mục tiêu và 11 L.O. của đề, **hạn chế** | §5.1–5.2 + mới | TV3 + TV1 |
| 8. Kết luận và hướng phát triển | Kết luận; hướng phát triển (dbt / Airflow / incremental / SCD2 / bản đồ / dữ liệu chi phí thật); **2–3 ví dụ DW/DSS thực tế có trích nguồn (L.O.1.3)** | §5.3–5.5 | TV3 |
| Tài liệu tham khảo | Ưu tiên 8 tài liệu trong đề (Inmon, Kimball, Turban…), cộng dataset Olist (CC BY-NC-SA 4.0), scikit-learn, SciPy/OR-Tools. **Không bịa nguồn** | Có sẵn | TV3 |
| Phụ lục | Cài đặt và chạy, cấu trúc mã nguồn, thay đổi so với proposal | Phụ lục A, B, D | TV1 |

**Hình cần có** (danh sách 18 hình ở Phụ lục C của `report.md`, cộng thêm):
- sơ đồ kiến trúc three-tier;
- ERD fact constellation (dbdiagram.io hoặc Mermaid);
- sơ đồ luồng ETL;
- tab Tối ưu ngân sách;
- đường cong ngân sách – lợi ích;
- trang Data Quality.

**Checklist soát báo cáo trước khi xuất PDF** (rút kinh nghiệm từ lỗi của C):
- [ ] Mọi con số có trong `numbers.md`; KPI tổng trên dashboard khớp với bảng đối chiếu.
- [ ] Không còn `[TODO]`, `[HÌNH]`, `contentReference`, `oaicite`, hay câu "là một mô hình ngôn ngữ".
- [ ] Không nhắc tới cột hoặc tính năng không tồn tại; số chương ở mục Bố cục khớp với thực tế.
- [ ] Tham số trong báo cáo khớp với code (`max_depth`, ngưỡng, ngân sách mặc định…).
- [ ] Mỗi tỷ lệ ghi rõ mẫu số; chi phí ghi rõ là giả định.
- [ ] Không có đoạn văn chung chung kiểu "nếu doanh thu tăng thì…" mà không có số.
- [ ] Ví dụ ở L.O.1.3 có nguồn thật, có thể kiểm chứng.

## 6. Slide và thuyết trình (15 phút + 5 phút hỏi đáp)

| Phút | Nội dung | Người |
|---|---|---|
| 0–2 | Bài toán quyết định, dữ liệu, tại sao trễ dẫn tới review xấu (62% so với 9%) | TV2 |
| 2–5 | Kiến trúc three-tier, ETL, fact constellation, grain, đối chiếu số liệu | TV1 |
| 5–8 | Demo OLAP (drill-down, slice/dice, pivot) và trang Delivery | TV2 |
| 8–13 | DSS: cây quyết định, what-if, goal seeking, **tối ưu ngân sách và khuyến nghị** (demo) | TV3 |
| 13–15 | Đánh giá, hạn chế, kết luận | TV1 + TV3 |

- **Hình thức:** đề (§4.1) chỉ ghi "Thuyết trình trực tiếp / video: sinh viên đăng ký với giảng viên", không nêu hạn hay cách đăng ký. Nhóm cần hỏi giảng viên / kênh lớp sớm. Nếu nộp video thì video phải xong cùng báo cáo trước 15/11. Nếu làm video: quay ngày 13–14/11, cả 3 người phải xuất hiện, dài 10–15 phút, upload YouTube (unlisted) hoặc Drive, ghi link lên trang bìa.
- Chuẩn bị video hoặc ảnh demo dự phòng, đề phòng máy lỗi khi thuyết trình trực tiếp.
- **Hỏi đáp:** mỗi người tự soạn 5 câu hỏi khó về phần mình. Ví dụ:
  - Vì sao dùng 2 fact?
  - Vì sao không dùng `predict_proba`?
  - Chi phí lấy ở đâu ra?
  - Greedy thua tối ưu khi nào?
  - Kết quả có phải quan hệ nhân quả không?

## 7. Lịch làm việc

| Ngày | Việc | Mốc |
|---|---|---|
| T3 03/11 | Chốt plan; mời collaborator GitHub; upload CSV lên Drive; bắt đầu Phase 1 | Plan được duyệt |
| T4 04/11 | Phase 1 (test) + bắt đầu Phase 2 (bảng lợi ích, chi phí) | |
| T5 05/11 | Phase 2 xong; bắt đầu Phase 3; TV2/TV3 review code theo checklist trong README | `pytest` xanh |
| T6 06/11 | Phase 3 + Phase 4; TV3 chạy thực nghiệm | |
| T7 07/11 | Sửa theo góp ý review; đã hỏi giảng viên về hình thức thuyết trình (trực tiếp hay video) | Review xong |
| **CN 08/11** | **Phase 5: đóng băng code, chốt `numbers.md`**, chụp toàn bộ hình | **Đóng băng code** |
| T2–T4 09–11/11 | Viết báo cáo theo phân công | Bản nháp đầy đủ 11/11 |
| T5 12/11 | Soát chéo báo cáo (mỗi người soát chương của người khác) + checklist §5; làm slide | |
| T6 13/11 | Xuất PDF báo cáo và slide; tập thuyết trình; quay video nếu cần | PDF xong |
| T7 14/11 | Đóng gói ZIP, thử giải nén và kiểm tra lại toàn bộ; clone sạch repo và chạy thử theo README | ZIP sẵn sàng |
| **CN 15/11** | Nộp **trước 20:00** (để dự phòng 4 tiếng) | **Nộp bài** |

## 8. Đóng gói nộp bài (§5.1 của đề)

```
Nhom<XX>_CO4031_Olist.zip
├── report.pdf
├── slides.pdf
├── src/                 # toàn bộ src/ của repo (SQL, ETL, DSS, app) + README.md, environment.yml, scripts/, config/, tests/
├── data/
│   └── README.md        # link Kaggle + link Google Drive chứa CSV (CSV không đưa lên GitHub)
└── README.txt           # link GitHub, link Drive, link video (nếu có)
```

- [ ] Không đưa vào ZIP: `.env-btl/`, `.pgdata/`, `.mamba/`, `.tools/`, `.logs/`, `lectures/`, file zip của nhóm Coffee Shop.
- [ ] Repo GitHub ở chế độ public (hoặc đã cấp quyền cho giảng viên); link Drive để chế độ "ai có link đều xem được".
- [ ] Trang bìa có link video (nếu nộp video).

## 9. Rủi ro và cách xử lý

| Rủi ro | Cách xử lý |
|---|---|
| Optimizer cho kết quả giống hệt greedy, phần so sánh không có ý nghĩa | Dùng hệ số `tier` tăng dần cho chi phí; thử thêm ràng buộc K; nếu vẫn giống thì báo cáo trung thực và giải thích vì sao |
| Bảng lợi ích tính chậm | Tính trước trong `train_model.py` và lưu `models/options.csv` |
| Sửa ETL sau khi đã đóng băng làm lệch số liệu trong báo cáo | Chỉ sửa logic khi bắt buộc; nếu sửa phải làm lại toàn bộ Phase 5 |
| Thầy hỏi về chi phí giả định | Trả lời: đây là tham số kịch bản, đã phân tích độ nhạy; dữ liệu chi phí thật nằm ở phần hướng phát triển |
| Thầy hỏi về quan hệ nhân quả | Trả lời: đây là mô hình "under risk" dựa trên quan sát lịch sử; đã ghi trong phần Hạn chế |
| Một thành viên không kịp phần việc | Mốc kiểm tra 07/11 và 11/11; người xong trước hỗ trợ |
| Thiếu ví dụ thực tế có nguồn (L.O.1.3) | TV3 tìm từ ngày 09/11; chỉ dùng nguồn có thể kiểm chứng |

## 10. Định nghĩa "xong"

- [ ] `run_etl.py` chạy sạch, mọi kiểm tra trong `meta.check_result` đạt; `pytest` xanh.
- [ ] Dashboard có 5 trang (Home, OLAP, Delivery, DSS 5 tab, Data Quality), chạy được trên một bản clone sạch.
- [ ] DSS trả lời trọn câu hỏi ở §1 bằng một khuyến nghị cụ thể.
- [ ] Báo cáo PDF qua hết checklist §5; slide PDF; video (nếu có).
- [ ] ZIP đúng cấu trúc §8, nộp trước 20:00 ngày 15/11.
