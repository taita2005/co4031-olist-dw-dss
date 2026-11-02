"""Database connection shared by the ETL, the DSS models and the Streamlit app.

Connection settings come from the standard PostgreSQL environment variables
(set by scripts/env.sh); the defaults match the project-local server.
"""
import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    user = os.getenv("PGUSER", "btl")
    password = os.getenv("PGPASSWORD", "")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5433")
    database = os.getenv("PGDATABASE", "olist_dw")
    auth = f"{user}:{password}" if password else user
    return create_engine(f"postgresql+psycopg2://{auth}@{host}:{port}/{database}")


def query(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a SELECT and return the result as a DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)
