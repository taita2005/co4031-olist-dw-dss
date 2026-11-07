"""Source contracts: what each CSV must look like before it is loaded.

Staging keeps every column as TEXT, so a broken file would otherwise load
without complaint and only fail later (a cast error deep in
03_transform_load.sql) or, worse, load silently into the wrong columns.
The contract is checked in Python before COPY:

- Fatal (the ETL stops before touching the database): the file is missing,
  or its header is not exactly the expected column list.
- Value rules (recorded as checks in meta.check_result, category 'source';
  the run continues and run_etl.py exits 1 if any rule is broken):
  keys are present and unique, numbers / timestamps parse, review scores
  are 1..5, states are 2-letter UF codes, zip prefixes are 5 digits.
  An empty value is allowed in typed columns unless the column is required.
"""
import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class ContractError(Exception):
    """The file cannot be loaded at all (missing or wrong header)."""


def _is_nonneg_number(v: str) -> bool:
    try:
        return float(v) >= 0
    except ValueError:
        return False


def _is_timestamp(v: str) -> bool:
    try:
        datetime.fromisoformat(v)
        return True
    except ValueError:
        return False


_STATE = re.compile(r"[A-Z]{2}")
_ZIP = re.compile(r"\d{5}")

# rule name -> (description shown in check_result, predicate on a non-empty value)
RULES = {
    "int": ("số nguyên không âm", str.isdigit),
    "amount": ("số không âm", _is_nonneg_number),
    "timestamp": ("ngày giờ hợp lệ", _is_timestamp),
    "score": ("điểm 1..5", lambda v: v in {"1", "2", "3", "4", "5"}),
    "state": ("mã bang 2 chữ in hoa", lambda v: _STATE.fullmatch(v) is not None),
    "zip": ("zip 5 chữ số", lambda v: _ZIP.fullmatch(v) is not None),
}


@dataclass(frozen=True)
class Contract:
    columns: tuple[str, ...]
    key: tuple[str, ...]                 # must be non-empty and unique together
    required: tuple[str, ...] = ()       # other columns that must be non-empty
    types: dict[str, str] = field(default_factory=dict)   # column -> RULES key


TS = "timestamp"
CONTRACTS = {
    "olist_orders_dataset.csv": Contract(
        columns=("order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
                 "order_delivered_carrier_date", "order_delivered_customer_date",
                 "order_estimated_delivery_date"),
        key=("order_id",),
        required=("customer_id", "order_status", "order_purchase_timestamp", "order_estimated_delivery_date"),
        types={"order_purchase_timestamp": TS, "order_approved_at": TS, "order_delivered_carrier_date": TS,
               "order_delivered_customer_date": TS, "order_estimated_delivery_date": TS},
    ),
    "olist_order_items_dataset.csv": Contract(
        columns=("order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price",
                 "freight_value"),
        key=("order_id", "order_item_id"),
        required=("product_id", "seller_id", "price", "freight_value"),
        types={"order_item_id": "int", "shipping_limit_date": TS, "price": "amount", "freight_value": "amount"},
    ),
    "olist_order_payments_dataset.csv": Contract(
        columns=("order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"),
        key=("order_id", "payment_sequential"),
        required=("payment_type", "payment_value"),
        types={"payment_sequential": "int", "payment_installments": "int", "payment_value": "amount"},
    ),
    "olist_order_reviews_dataset.csv": Contract(
        # review_id and order_id are each non-unique in the source; the pair is unique
        columns=("review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
                 "review_creation_date", "review_answer_timestamp"),
        key=("review_id", "order_id"),
        required=("review_score",),
        types={"review_score": "score", "review_creation_date": TS, "review_answer_timestamp": TS},
    ),
    "olist_customers_dataset.csv": Contract(
        columns=("customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city",
                 "customer_state"),
        key=("customer_id",),
        required=("customer_unique_id", "customer_state"),
        types={"customer_zip_code_prefix": "zip", "customer_state": "state"},
    ),
    "olist_sellers_dataset.csv": Contract(
        columns=("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
        key=("seller_id",),
        required=("seller_state",),
        types={"seller_zip_code_prefix": "zip", "seller_state": "state"},
    ),
    "olist_products_dataset.csv": Contract(
        # the source misspells "length" as "lenght"; 610 products have no category (allowed)
        columns=("product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
                 "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm",
                 "product_width_cm"),
        key=("product_id",),
        types={c: "int" for c in ("product_name_lenght", "product_description_lenght", "product_photos_qty",
                                     "product_weight_g", "product_length_cm", "product_height_cm",
                                     "product_width_cm")},
    ),
    "product_category_name_translation.csv": Contract(
        columns=("product_category_name", "product_category_name_english"),
        key=("product_category_name",),
        required=("product_category_name_english",),
    ),
}


@dataclass
class CsvReport:
    filename: str
    n_rows: int
    checks: list[tuple[str, int, str]]   # (check name, number of bad rows, note)

    @property
    def n_bad(self) -> int:
        return sum(n for _, n, _ in self.checks)

    def note(self) -> str:
        broken = [f"{name} ({n}, {note})" for name, n, note in self.checks if n]
        return "; ".join(broken) if broken else f"đạt cả {len(self.checks)} quy tắc"


def validate_csv(path: Path, contract: Contract, max_examples: int = 3) -> CsvReport:
    """Check one CSV against its contract. Raises ContractError if it cannot be loaded at all."""
    if not path.exists():
        raise ContractError(f"thiếu file nguồn: {path}")
    # utf-8-sig strips the BOM of the translation file; csv handles newlines inside quoted comments
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = tuple(next(reader, ()))
        if header != contract.columns:
            missing = [c for c in contract.columns if c not in header]
            extra = [c for c in header if c not in contract.columns]
            raise ContractError(
                f"{path.name}: header khác hợp đồng (thiếu {missing}, thừa {extra}"
                + (", sai thứ tự" if not missing and not extra else "") + ")")

        idx = {c: i for i, c in enumerate(header)}
        key_idx = [idx[c] for c in contract.key]
        required = contract.key + contract.required
        bad = {f"{c}: trống": [] for c in required}
        bad.update({f"{c}: {RULES[r][0]}": [] for c, r in contract.types.items()})
        dup_name = f"({', '.join(contract.key)}): trùng khóa"
        bad[dup_name] = []
        seen = set()
        n_rows = 0
        for rec_no, row in enumerate(reader, start=1):   # record number (a review can span lines)
            n_rows += 1
            if len(row) != len(header):
                bad.setdefault("số cột của dòng sai", []).append(rec_no)
                continue
            for c in required:
                if row[idx[c]] == "":
                    bad[f"{c}: trống"].append(rec_no)
            for c, rule in contract.types.items():
                v = row[idx[c]]
                if v != "" and not RULES[rule][1](v):
                    bad[f"{c}: {RULES[rule][0]}"].append(rec_no)
            key = tuple(row[i] for i in key_idx)
            if key in seen:
                bad[dup_name].append(rec_no)
            seen.add(key)

    checks = []
    for name, lines in bad.items():
        note = f"ví dụ bản ghi thứ {', '.join(map(str, lines[:max_examples]))}" if lines else None
        checks.append((name, len(lines), note))
    return CsvReport(path.name, n_rows, checks)
