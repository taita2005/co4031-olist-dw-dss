"""Create the DW owner and least-privilege Metabase reader roles."""
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etl.run_etl import run_sql_file  # noqa: E402


def main():
    admin_password = os.environ.get("POSTGRES_ADMIN_PASSWORD", "")
    if not admin_password:
        raise SystemExit("POSTGRES_ADMIN_PASSWORD is empty; run the bootstrap job first")
    conn = psycopg2.connect(host=os.getenv("PGHOST", "postgres"), port=os.getenv("PGPORT", 5432),
                            dbname=os.getenv("PGDATABASE", "olist_dw"), user="postgres", password=admin_password)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname='btl'")
            if cur.fetchone():
                cur.execute("ALTER ROLE btl NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN")
            else:
                cur.execute("CREATE ROLE btl LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s",
                            (os.environ["PGPASSWORD"],))
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname='metabase_ro'")
            if cur.fetchone():
                cur.execute("ALTER ROLE metabase_ro NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN")
            else:
                cur.execute("CREATE ROLE metabase_ro LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s",
                            (os.environ["METABASE_RO_PASSWORD"],))
            database = os.getenv("PGDATABASE", "olist_dw")
            cur.execute(sql.SQL("ALTER DATABASE {} OWNER TO btl").format(sql.Identifier(database)))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO metabase_ro").format(sql.Identifier(database)))
            cur.execute("CREATE SCHEMA IF NOT EXISTS bi AUTHORIZATION btl")
            cur.execute("GRANT USAGE ON SCHEMA bi TO metabase_ro")
            cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA bi TO metabase_ro")
            cur.execute("ALTER DEFAULT PRIVILEGES FOR ROLE btl IN SCHEMA bi GRANT SELECT ON TABLES TO metabase_ro")
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='dw' AND table_name='fact_sales')")
            has_dw = cur.fetchone()[0]
            if has_dw:
                cur.execute("SET ROLE btl")
                run_sql_file(cur, "06_bi_views.sql")
                cur.execute("RESET ROLE")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Roles ready; run ETL to create BI views and grants.")


if __name__ == "__main__":
    main()
