# Dữ liệu nguồn

Các file CSV không được đưa lên GitHub vì nặng (~120MB). Trước khi chạy ETL, hãy tải bộ **Brazilian E-Commerce Public Dataset by Olist** từ Kaggle:

https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Giải nén và đặt **trực tiếp** các file sau vào thư mục `data/` này (không để trong thư mục con):

```
olist_customers_dataset.csv
olist_geolocation_dataset.csv        (không dùng, có thể bỏ qua)
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

Kiểm tra nhanh: `ls data/*.csv | wc -l` phải ra 8 hoặc 9.
