# Chi phí trong tối ưu ngân sách (DSS)

## Công thức

```
cost[bang, mức r] (BRL) = phí ship thực tế của các đơn trễ được sửa ở mức r   ← dữ liệu Olist
                          × surcharge                                         ← giả định
                          × tier[r]                                           ← giả định
```

- **Phần lấy từ dữ liệu:** `freight_fixed` = tổng `freight_value` (BRL) mà khách đã trả cho đúng những đơn trễ được sửa, tính từ `dw.fact_delivery` khi train mô hình (`models/options.csv`). Nhờ vậy chênh lệch chi phí giữa các bang là thật. Ví dụ phí ship trung bình mỗi đơn ở vùng Southeast là 19,84 BRL, ở vùng North là 41,35 BRL.
- **Phần giả định:** hai tham số trong `cost_assumptions.csv`. Olist không công bố chi phí cải thiện giao hàng, nên không có số thật cho hai tham số này.

BRL là đồng Real Brazil, đơn vị tiền tệ của toàn bộ dữ liệu Olist (giai đoạn 2016–2018).

## `cost_assumptions.csv`

| Tham số | Giá trị | Ý nghĩa | Ảnh hưởng tới phương án |
|---|---|---|---|
| `surcharge` | 0.5 | Chi phí can thiệp (đổi hãng vận chuyển, thêm kho trung chuyển, ưu tiên xử lý…) để một đơn trễ giao đúng hạn, ước bằng 50% phí ship của đơn đó. Phí ship chỉ là thước đo logistics ở bang đó đắt hay rẻ (xem mục kiểm tra bên dưới) | **Không đổi phương án**. Hệ số này nhân đều mọi chi phí, nên chỉ đổi thước đo của ngân sách: phụ phí 50% với ngân sách 30.000 BRL cho ra cùng phương án như phụ phí 100% với 60.000 BRL. Đã có test kiểm chứng |
| `tier_25` … `tier_100` | 1.0 / 1.2 / 1.5 / 2.0 | Hệ số nhân chi phí mỗi đơn ở mức giảm 25 / 50 / 75 / 100% đơn trễ. Chi phí cận biên tăng dần: những đơn đầu dễ sửa, những đơn cuối khó và đắt | **Có ảnh hưởng**: quyết định nên sửa sâu ở ít bang hay sửa nhẹ ở nhiều bang. Xem phân tích độ nhạy `tier_sensitivity()` với 3 kịch bản: phẳng (1/1/1/1), mặc định, dốc (1/1.5/2.25/3.5) |

Muốn thử giả định khác thì sửa file này hoặc chỉnh trên trang DSS. Không cần chạy lại ETL hay train lại mô hình.

## Đã kiểm tra giả định trên dữ liệu chưa?

Đã kiểm tra (03/11/2026): **trả phí ship cao hơn có làm giao nhanh hơn không?** So trong **cùng tuyến** (bang người bán → bang người mua) và **cùng nhóm cân nặng**, trên 78.803 đơn có 1 sản phẩm, chia 4 nhóm theo phí ship:

| Nhóm phí ship | Phí ship TB (BRL) | Ngày giao TB | Tỷ lệ trễ |
|---|---|---|---|
| Rẻ nhất 25% | 13,43 | 11,5 | 6,63% |
| 2 | 16,13 | 12,2 | 7,21% |
| 3 | 18,97 | 12,6 | 6,58% |
| Đắt nhất 25% | 25,87 | 12,2 | 6,92% |

**Kết luận: không.** Trong Olist, `freight_value` là phí vận chuyển tiêu chuẩn, không phải lựa chọn giao nhanh. Vì vậy:
- Phí ship chỉ được dùng làm **thước đo logistics ở mỗi bang đắt hay rẻ** (chênh lệch thật giữa các bang). Không dùng nó như cơ chế làm đơn nhanh hơn.
- Can thiệp (đổi hãng vận chuyển, thêm kho…) và mức `surcharge` = 50% là **giả định, không kiểm chứng được bằng Olist**. Nhưng `surcharge` không làm đổi phương án (xem bảng trên).
- **Không được** nói "dữ liệu cho thấy trả thêm tiền thì giao nhanh hơn".

Câu SQL dùng để kiểm tra: nhóm theo `dim_seller.state || '->' || dim_customer.state` và nhóm cân nặng của `dim_product.weight_g` (mốc 500 / 1.000 / 2.000 / 5.000 / 10.000 g), `ntile(4)` theo `freight_total` trong mỗi nhóm, chỉ giữ nhóm có ≥ 40 đơn, `n_items = 1`.

## Kết luận nào không phụ thuộc các giả định này?

`optimizer.robustness()` giải lại bài toán với **2 cách tính chi phí** (phí ship thật của bang; hoặc đồng đều: mọi đơn trễ cùng giá = phí ship trung bình toàn quốc của một đơn trễ, tức là bỏ hẳn giả định phí ship) × **3 kịch bản hệ số theo mức** × **3 mức ngân sách** (10.000 / 20.000 / 40.000 BRL). Bang được chọn ngay ở mức ngân sách nhỏ trong ít nhất 4/6 bộ giả định là ưu tiên cao nhất. Kết quả hiện ở tab 5 trang DSS: ưu tiên 1 là RJ, GO, PR, RN. Mức giảm % cụ thể ở mỗi bang thì phụ thuộc giả định, nên chỉ báo cáo dưới dạng khoảng.

## Các giả định khác của DSS (cần liệt kê trong báo cáo)

1. Giao trễ là **nguyên nhân** gây review xấu (thực tế còn chất lượng sản phẩm, đóng gói…).
2. Đơn trễ sau khi được sửa sẽ đến **đúng ngày dự kiến**.
3. Tỷ lệ review xấu thực tế của mỗi lá cây (tập train) được dùng làm **xác suất** review xấu của đơn rơi vào lá đó.
4. Hai tham số chi phí ở trên.
