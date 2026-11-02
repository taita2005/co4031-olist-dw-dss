"""Helpers shared by all Streamlit pages (top tier / user interface subsystem)."""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from db import get_engine, query  # noqa: E402

# Months at the edges of the dataset have only a handful of orders and distort charts
FULL_MONTHS = ("2017-01", "2018-08")


@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    return query(engine(), sql, params)


def fmt_money(x: float) -> str:
    return f"R$ {x:,.0f}"


def fmt_pct(x: float) -> str:
    return f"{x:.1%}"
