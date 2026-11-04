"""Source contracts (src/etl/contracts.py) — no database needed."""
import pytest

from etl.contracts import CONTRACTS, ContractError, validate_csv

SELLERS = CONTRACTS["olist_sellers_dataset.csv"]
HEADER = "seller_id,seller_zip_code_prefix,seller_city,seller_state\n"


def write(tmp_path, text, name="sellers.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def bad_counts(report):
    return {name: n for name, n, _ in report.checks if n}


def test_clean_file_passes(tmp_path):
    report = validate_csv(write(tmp_path, HEADER + "s1,01037,sao paulo,SP\ns2,99999,curitiba,PR\n"), SELLERS)
    assert report.n_rows == 2
    assert report.n_bad == 0


def test_missing_file_is_fatal(tmp_path):
    with pytest.raises(ContractError, match="thiếu file"):
        validate_csv(tmp_path / "nope.csv", SELLERS)


@pytest.mark.parametrize("header", [
    "seller_id,seller_zip_code_prefix,seller_city\n",                       # column missing
    "seller_id,seller_city,seller_zip_code_prefix,seller_state\n",          # columns swapped
])
def test_wrong_header_is_fatal(tmp_path, header):
    with pytest.raises(ContractError, match="header"):
        validate_csv(write(tmp_path, header + "s1,01037,x,SP\n"), SELLERS)


def test_value_rules_count_each_broken_row(tmp_path):
    rows = ("s1,01037,a,SP\n"
            "s1,01037,b,SP\n"       # duplicate key
            ",01037,c,SP\n"         # empty key
            "s4,1037,d,SP\n"        # zip lost its leading zero (read as a number somewhere)
            "s5,01037,e,sp\n")      # state not upper case
    report = validate_csv(write(tmp_path, HEADER + rows), SELLERS)
    assert report.n_rows == 5
    assert bad_counts(report) == {
        "(seller_id): trùng khóa": 1,
        "seller_id: trống": 1,
        "seller_zip_code_prefix: zip 5 chữ số": 1,
        "seller_state: mã bang 2 chữ in hoa": 1,
    }
    assert "bản ghi thứ 2" in report.note()


def test_multiline_comment_is_one_record(tmp_path):
    reviews = CONTRACTS["olist_order_reviews_dataset.csv"]
    text = (",".join(reviews.columns) + "\n"
            'r1,o1,5,,"great\nproduct",2018-01-01 00:00:00,2018-01-02 10:00:00\n'
            "r2,o2,6,,,2018-01-01 00:00:00,not a date\n")
    report = validate_csv(write(tmp_path, text, "reviews.csv"), reviews)
    assert report.n_rows == 2
    assert bad_counts(report) == {"review_score: điểm 1..5": 1, "review_answer_timestamp: ngày giờ hợp lệ": 1}


def test_bom_in_header_is_accepted(tmp_path):
    translation = CONTRACTS["product_category_name_translation.csv"]
    path = tmp_path / "t.csv"
    path.write_text("product_category_name,product_category_name_english\nbeleza_saude,health_beauty\n",
                    encoding="utf-8-sig")
    assert validate_csv(path, translation).n_bad == 0
