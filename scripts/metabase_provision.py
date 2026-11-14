"""Provision Metabase questions, preserving definitions unless --upgrade is requested."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2
from psycopg2.extras import RealDictCursor

from src.bi.metabase import card_payload, dashboard_parameters, dashboard_specs

CATALOG = Path(".runtime/metabase/catalog.json")
DATABASE_NAME = "Olist DW (read only)"
COLLECTION_NAME = "CO4031 Olist BI"


def _runtime_owner(path):
    runtime_root = ROOT / ".runtime"
    resolved = path.resolve()
    if runtime_root.exists() and (resolved == runtime_root.resolve() or runtime_root.resolve() in resolved.parents):
        return runtime_root.stat()
    return path.stat()


class API:
    def __init__(self, url=None, timeout=20):
        self.url = (url or os.getenv("METABASE_URL", "http://localhost:3000")).rstrip("/")
        self.timeout = timeout
        self.session = None

    def call(self, method, path, value=None):
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["X-Metabase-Session"] = self.session
        request = Request(self.url + "/api/" + path, method=method, headers=headers,
                          data=None if value is None else json.dumps(value).encode("utf-8"))
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as exc:
            raise RuntimeError(f"Metabase {method} {path}: HTTP {exc.code}; inspect local server logs") from None
        except URLError as exc:
            raise RuntimeError(f"Metabase {method} {path}: {exc.reason}") from None


def preflight():
    conn = psycopg2.connect(host=os.getenv("PGHOST", "postgres"), port=os.getenv("PGPORT", "5432"),
                            dbname=os.getenv("PGDATABASE", "olist_dw"), user=os.getenv("PGUSER", "btl"),
                            password=os.getenv("PGPASSWORD", ""), connect_timeout=5)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT etl_run_id,check_count,failed_count,ready FROM bi.dataset_status")
            status = cur.fetchone()
            if not status or not status["ready"]:
                raise RuntimeError("BI data is not certified. Run bootstrap and ETL; all current checks must pass.")
            cur.execute("SELECT count(*) FROM bi.sales_items")
            cur.fetchone()
    finally:
        conn.close()


def _one_named(items, model, name):
    matches = [item for item in items if item.get("model") == model and item.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple Metabase {model}s named {name!r} in the target collection")
    return matches[0] if matches else None


def _dashcard(card_id, spec, row, col, width, height, index):
    mappings = [{"parameter_id": name, "card_id": card_id,
                 "target": ["variable" if name in ("start_date", "end_date", "grain") else "dimension",
                            ["template-tag", name]]} for name in spec["filters"]]
    return {"id": -(index + 1), "card_id": card_id, "row": row, "col": col,
            "size_x": width, "size_y": height, "parameter_mappings": mappings,
            "visualization_settings": {"card.title": spec["name"]}}


def _layout_managed(question_specs):
    layout_order = {"S1": 0, "S5": 1, "S2": 2, "S3": 3, "S4": 4}
    if {"S1", "S2", "S3", "S4", "S5"} <= {spec["key"] for _, spec in question_specs}:
        question_specs = sorted(question_specs, key=lambda item: layout_order.get(item[1]["key"], 5))
    cards = []
    row = col = row_height = 0
    for index, (card_id, spec) in enumerate(question_specs):
        full_width = spec["display"] == "table" or spec["key"] in ("E5", "S2", "S3", "S4")
        if spec["display"] == "scalar":
            width, height = 8, 4
        elif spec["display"] == "table":
            width, height = 24, (10 if spec["key"] == "S4" else 6)
        elif full_width:
            width, height = 24, (10 if spec["key"] == "S4" else 8)
        else:
            width, height = 12, 8
        if (width == 24 and col) or col + width > 24:
            row += row_height
            col = row_height = 0
        cards.append(_dashcard(card_id, spec, row, col, width, height, index))
        col += width
        row_height = max(row_height, height)
        if col == 24:
            row += row_height
            col = row_height = 0
    return cards, row + (row_height if col else 0)


def _dashboard_note(name):
    note = "**Cách đọc:** Ngày mua theo khoảng [bắt đầu, kết thúc); bang là địa chỉ mới nhất gắn với khách hàng duy nhất."
    if name == "Executive":
        note += " Doanh thu là tổng giá sản phẩm bằng BRL, loại đơn canceled/unavailable; AOV = doanh thu / số đơn distinct."
    elif name == "Sales OLAP":
        note += " Top 5/10 được chọn trên toàn cửa sổ lọc; tổng số đơn là distinct, không cộng giữa các danh mục. S4 là bảng số thay cho pivot tô màu."
    else:
        note += " Late rate dùng đơn giao có đủ ngày; review xấu là 1–2 sao trên đơn có review. Danh mục/người bán của fact là item giá cao nhất. Tương quan không chứng minh nguyên nhân."
    return note


def _is_dashboard_note(dashcard):
    note = dashcard.get("visualization_settings", {}).get("text", "")
    return note.startswith("**Cách đọc:**") or "<!-- co4031-metabase-note -->" in note


def _auth(api, password, email):
    props = api.call("GET", "session/properties")
    if props.get("has-user-setup"):
        api.session = api.call("POST", "session", {"username": email, "password": password})["id"]
    else:
        response = api.call("POST", "setup", {
            "token": props["setup-token"],
            "user": {"email": email, "password": password, "first_name": "Olist", "last_name": "Local Admin"},
            "prefs": {"site_name": "CO4031 Olist BI", "site_locale": "vi", "allow_tracking": False},
        })
        api.session = response["id"]


def provision(api=None, check_preflight=preflight, catalog_path=CATALOG, upgrade=False):
    check_preflight()
    api = api or API()
    password = os.getenv("METABASE_ADMIN_PASSWORD", "")
    if not password:
        raise RuntimeError("METABASE_ADMIN_PASSWORD is empty; run scripts/docker_init.py first")
    _auth(api, password, os.getenv("METABASE_ADMIN_EMAIL", "admin@olist.local"))
    try:
        saved = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
        databases = api.call("GET", "database")["data"]
        expected = {"host": "postgres", "port": 5432, "dbname": os.getenv("POSTGRES_DB", "olist_dw"),
                    "user": "metabase_ro"}
        database = next((x for x in databases if x["id"] == saved.get("database_id")), None)
        if saved.get("database_id") and database is None:
            raise RuntimeError("Saved BI database ID is gone; inspect the catalog before recovery")
        if database is None:
            hits = [x for x in databases if x["name"] == DATABASE_NAME]
            if len(hits) > 1:
                raise RuntimeError("Multiple matching Olist data connections; resolve them before provisioning")
            database = hits[0] if hits else None
        if database:
            details = database.get("details", {})
            if database.get("engine") != "postgres" or any(str(details.get(k)) != str(v) for k, v in expected.items()):
                raise RuntimeError("Existing Olist data connection does not match postgres:5432/olist_dw/metabase_ro")
        else:
            database = api.call("POST", "database", {"name": DATABASE_NAME, "engine": "postgres",
                "details": {**expected, "password": os.environ["METABASE_RO_PASSWORD"], "ssl": False,
                            "schema-filters-type": "inclusion", "schema-filters-patterns": "bi"},
                "is_full_sync": True, "is_on_demand": False})
        database_id = database["id"]
        api.call("POST", f"database/{database_id}/sync_schema")
        required_tables = {"dataset_status", "sales_items", "delivery_orders"}
        until = time.monotonic() + 120
        while True:
            metadata = api.call("GET", f"database/{database_id}/metadata")
            tables = {t["name"]: {f["name"]: f["id"] for f in t["fields"]}
                      for t in metadata.get("tables", [])}
            if required_tables <= tables.keys() and all(
                    field in tables[table] for table, field in (
                        ("sales_items", "purchase_date"), ("sales_items", "customer_state"),
                        ("sales_items", "customer_region"), ("sales_items", "category"))):
                break
            if time.monotonic() >= until:
                raise RuntimeError("Metabase did not sync bi view fields within 120 seconds; retry after sync")
            time.sleep(2)

        collection_response = api.call("GET", "collection")
        collections = collection_response.get("data", collection_response) if isinstance(collection_response, dict) else collection_response
        collection = next((c for c in collections if c["id"] == saved.get("collection_id")), None)
        if saved.get("collection_id") and collection is None:
            raise RuntimeError("Saved Metabase collection ID is gone; inspect the catalog before recovery")
        if collection is None:
            hits = [c for c in collections if c.get("name") == COLLECTION_NAME]
            if len(hits) > 1:
                raise RuntimeError("Multiple BI collections found; resolve them before provisioning")
            collection = hits[0] if hits else api.call("POST", "collection", {
                "name": COLLECTION_NAME, "description": "Local Olist BI; the Streamlit app retains DSS."})
        collection_id = collection["id"]
        items = api.call("GET", f"collection/{collection_id}/items")["data"]
        card_ids = dict(saved.get("cards", {}))
        dash_ids = dict(saved.get("dashboards", {}))
        if upgrade:
            backup = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "collection_id": collection_id,
                      "cards": [], "dashboards": []}
            for item in items:
                if item.get("model") == "card":
                    backup["cards"].append(api.call("GET", f"card/{item['id']}?legacy-mbql=true"))
                elif item.get("model") == "dashboard":
                    backup["dashboards"].append(api.call("GET", f"dashboard/{item['id']}"))
            backup_dir = catalog_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            runtime_owner = _runtime_owner(catalog_path.parent)
            os.chown(catalog_path.parent, runtime_owner.st_uid, runtime_owner.st_gid)
            os.chown(backup_dir, runtime_owner.st_uid, runtime_owner.st_gid)
            owner = runtime_owner
            backup_path = backup_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=backup_dir, delete=False) as handle:
                handle.write(json.dumps(backup, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.chown(temporary, owner.st_uid, owner.st_gid)
            temporary.chmod(0o600)
            os.replace(temporary, backup_path)
        catalog = {"database_id": database_id, "collection_id": collection_id,
                   "cards": card_ids, "dashboards": dash_ids, "updated_at_utc": datetime.now(timezone.utc).isoformat()}
        all_specs = dashboard_specs()
        for board_name, board in all_specs.items():
            dashboard_card_ids = []
            for spec in [*board["cards"], {**board["status"], "key": "STATUS_" + board_name}]:
                spec_key = board_name + "/" + spec["key"]
                card_name = spec_key + " — " + spec["name"]
                item = next((x for x in items if x.get("model") == "card" and x.get("id") == card_ids.get(spec_key)), None)
                if card_ids.get(spec_key) and item is None:
                    raise RuntimeError(f"Saved question ID for {spec_key} is missing; inspect the catalog before recovery")
                if item is None:
                    item = _one_named(items, "card", card_name)
                if item is None:
                    fields = tables.get(spec.get("view", ""), {})
                    for field_name in spec["filters"]:
                        if field_name in ("customer_state", "customer_region", "category") and field_name not in fields:
                            raise RuntimeError(f"Metabase schema sync is missing bi.{spec.get('view')}.{field_name}")
                    payload = card_payload({**spec, "name": card_name}, database_id, collection_id, fields)
                    item = api.call("POST", "card", payload)
                    items.append({"id": item["id"], "model": "card", "name": card_name})
                elif upgrade:
                    fields = tables.get(spec.get("view", ""), {})
                    payload = card_payload({**spec, "name": card_name}, database_id, collection_id, fields)
                    api.call("PUT", f"card/{item['id']}", payload)
                card_ids[spec_key] = item["id"]
                dashboard_card_ids.append((item["id"], spec))
            dash = next((x for x in items if x.get("model") == "dashboard" and x.get("id") == dash_ids.get(board_name)), None)
            if dash_ids.get(board_name) and dash is None:
                raise RuntimeError(f"Saved dashboard ID for {board_name} is missing; inspect the catalog before recovery")
            if dash is None:
                dash = _one_named(items, "dashboard", board_name)
            if dash is None:
                dash = api.call("POST", "dashboard", {"name": board_name, "collection_id": collection_id,
                    "description": _description(board_name), "parameters": dashboard_parameters(board_name == "Sales OLAP")})
                items.append({"id": dash["id"], "model": "dashboard", "name": board_name})
                previous = []
            else:
                previous = api.call("GET", f"dashboard/{dash['id']}").get("dashcards", [])
            existing_cards = {x.get("card_id") for x in previous}
            missing = [(cid, spec) for cid, spec in dashboard_card_ids if cid not in existing_cards]
            cards = list(previous)
            if missing:
                if not previous:
                    cards, _ = _layout_managed(dashboard_card_ids)
                else:
                    row = max((x.get("row", 0) + x.get("size_y", 1) for x in cards), default=0)
                    for idx, (card_id, spec) in enumerate(missing):
                        width, height = (24, 6) if spec["display"] == "table" else (12, 8)
                        cards.append(_dashcard(card_id, spec, row, 0, width, height, idx))
                        row += height
            annotation = next((x for x in cards if x.get("card_id") is None and _is_dashboard_note(x)), None)
            if annotation and upgrade:
                annotation["visualization_settings"]["text"] = _dashboard_note(board_name)
            elif annotation is None:
                row = max((x.get("row", 0) + x.get("size_y", 1) for x in cards), default=0)
                cards.append({"id": -900, "card_id": None, "row": row, "col": 0, "size_x": 24, "size_y": 4,
                              "visualization_settings": {"virtual_card": {"name": None, "display": "text",
                                  "visualization_settings": {}, "dataset_query": {}, "archived": False},
                                  "text": _dashboard_note(board_name)}, "parameter_mappings": []})
            if upgrade:
                managed_ids = {cid for cid, _ in dashboard_card_ids}
                annotation = next((x for x in cards if x.get("card_id") is None and _is_dashboard_note(x)), None)
                manual = [x for x in cards if x.get("card_id") not in managed_ids and x is not annotation]
                cards, bottom = _layout_managed(dashboard_card_ids)
                if annotation:
                    annotation.update({"row": bottom, "col": 0, "size_x": 24, "size_y": 4})
                    cards.append(annotation)
                    bottom += 4
                for extra in manual:
                    extra["row"] = bottom
                    extra["col"] = 0
                    bottom += extra.get("size_y", 4)
                    cards.append(extra)
            if missing or upgrade or annotation is None:
                if upgrade:
                    managed_ids = {cid for cid, _ in dashboard_card_ids}
                    for dashcard in cards:
                        if dashcard.get("card_id") not in managed_ids:
                            continue
                        spec = next(spec for cid, spec in dashboard_card_ids if cid == dashcard["card_id"])
                        dashcard["parameter_mappings"] = [{"parameter_id": name, "card_id": dashcard["card_id"],
                            "target": ["variable" if name in ("start_date", "end_date", "grain") else "dimension",
                                       ["template-tag", name]]} for name in spec["filters"]]
                dashboard_update = {"dashcards": cards}
                if upgrade:
                    dashboard_update.update({"parameters": dashboard_parameters(board_name == "Sales OLAP"),
                                             "description": _description(board_name)})
                api.call("PUT", f"dashboard/{dash['id']}", dashboard_update)
            dash_ids[board_name] = dash["id"]
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_owner = _runtime_owner(catalog_path.parent)
        os.chown(catalog_path.parent, runtime_owner.st_uid, runtime_owner.st_gid)
        owner = catalog_path.parent.stat()
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=catalog_path.parent,
                                         prefix=".catalog.", delete=False) as handle:
            handle.write(json.dumps(catalog, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chown(temporary, owner.st_uid, owner.st_gid)
        temporary.chmod(0o600)
        os.replace(temporary, catalog_path)
        return catalog
    finally:
        if api.session:
            try:
                api.call("DELETE", "session", {"metabase-session-id": api.session})
            finally:
                api.session = None


def _description(name):
    return ("Olist historical data. Sales uses SUM(price), excludes canceled/unavailable orders. "
            "Date window is [start, end); customer geography is the latest known customer address. "
            "Delivery denominators include delivered orders with valid dates; review rate uses reviewed orders. "
            "Associations are descriptive and do not establish causality. " + name)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upgrade", action="store_true", help="Back up and update managed questions and filters")
    provision(upgrade=parser.parse_args().upgrade)
    print("Metabase dashboards provisioned; local ID catalog updated.")
