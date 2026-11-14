import json
from urllib.error import HTTPError

import pytest

from scripts import metabase_provision as provisioner
from scripts.metabase_provision import _layout_managed
from src.bi.metabase import card_payload, dashboard_parameters, dashboard_specs


def test_specs_contract_and_sql_filters():
    specs = dashboard_specs()
    assert set(specs) == {"Executive", "Sales OLAP", "Delivery Quality"}
    assert sum(len(board["cards"]) for board in specs.values()) == 15
    assert len(specs) * 6 == 18
    assert all(board["status"]["filters"] == [] for board in specs.values())
    for board in specs.values():
        for card in board["cards"]:
            assert "FROM bi." in card["sql"]
            assert "JOIN dw.fact" not in card["sql"]
            assert "[[AND" in card["sql"] and "AND AND" not in card["sql"]
            assert "{{start_date}}" in card["sql"] and "{{end_date}}" in card["sql"]
    assert "top5 AS" in specs["Sales OLAP"]["cards"][1]["sql"]
    assert "top10 AS" in specs["Sales OLAP"]["cards"][3]["sql"]
    assert "nullif(count(review_score),0)" in specs["Delivery Quality"]["cards"][4]["sql"].lower()
    for board in specs.values():
        for card in board["cards"]:
            assert "[[AND " in card["sql"]
            assert "AND AND" not in card["sql"]
            assert "purchase_date >= {{start_date}}" in card["sql"]
            assert "purchase_date < {{end_date}}" in card["sql"]
        assert "purchase_date" not in board["status"]["sql"]


def test_card_payload_has_only_the_filters_needed_by_the_question():
    spec = dashboard_specs()["Sales OLAP"]["cards"][0]
    payload = card_payload(spec, 2, 3, {"customer_state": 21, "customer_region": 22, "category": 23})
    tags = payload["dataset_query"]["native"]["template-tags"]
    assert tags["category"]["dimension"] == ["field", 23, None]
    assert tags["start_date"]["default"] == "2017-01-01"
    assert tags["end_date"]["default"] == "2018-09-01"
    assert payload["dataset_query"]["database"] == 2
    assert dashboard_parameters(True)[-1]["id"] == "grain"
    assert {p["id"] for p in dashboard_parameters(True)} >= {"category", "customer_state", "customer_region"}


def test_api_http_error_does_not_return_response_body(monkeypatch):
    def fail(_request, timeout):
        raise HTTPError("http://localhost/api/session", 401, "unauthorized", {}, None)

    monkeypatch.setattr(provisioner, "urlopen", fail)
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        provisioner.API("http://localhost").call("GET", "session")
    assert "password" not in str(error.value).lower()


class FakeAPI:
    def __init__(self):
        self.session = None
        self.items = []
        self.dashcards = {}
        self.dashboard_data = {}
        self.card_data = {}
        self.database = None
        self.collection = None
        self.user_setup = False
        self.next_id = 1
        self.cards_created = 0
        self.dashboards_created = 0

    def _new(self, model, name):
        item = {"id": self.next_id, "model": model, "name": name}
        self.next_id += 1
        self.items.append(item)
        return item

    def call(self, method, path, value=None):
        if method == "GET" and path == "session/properties":
            return {"has-user-setup": self.user_setup, "setup-token": "test-setup-token"}
        if method == "POST" and path == "setup":
            self.user_setup = True
            self.session = "fake-session"
            return {"id": self.session}
        if method == "POST" and path == "session":
            self.session = "fake-session"
            return {"id": self.session}
        if method == "DELETE" and path == "session":
            self.session = None
            return {}
        if method == "GET" and path == "database":
            return {"data": [self.database] if self.database else []}
        if method == "POST" and path == "database":
            self.database = {"id": self.next_id, "engine": value["engine"], "name": value["name"], "details": value["details"]}
            self.next_id += 1
            return self.database
        if method == "POST" and path.endswith("/sync_schema"):
            return {}
        if method == "GET" and path.endswith("/metadata"):
            return {"tables": [
                {"schema": "bi", "name": "sales_items", "fields": [{"name": x, "id": 100 + i} for i, x in enumerate(
                    ["purchase_date", "customer_state", "customer_region", "category"])]},
                {"schema": "bi", "name": "delivery_orders", "fields": [{"name": x, "id": 200 + i} for i, x in enumerate(
                    ["purchase_date", "customer_state", "customer_region"])]},
                {"schema": "bi", "name": "dataset_status", "fields": []},
            ]}
        if method == "GET" and path == "collection":
            return [self.collection] if self.collection else []
        if method == "POST" and path == "collection":
            self.collection = {"id": self.next_id, **value}
            self.next_id += 1
            return self.collection
        if method == "GET" and path.endswith("/items"):
            return {"data": list(self.items)}
        if method == "POST" and path == "card":
            self.cards_created += 1
            item = self._new("card", value["name"])
            self.card_data[item["id"]] = value
            return item
        if method == "GET" and path.startswith("card/"):
            card_id = int(path.split("/")[1].split("?")[0])
            return self.card_data[card_id]
        if method == "PUT" and path.startswith("card/"):
            self.card_data[int(path.split("/")[1])] = value
            return {}
        if method == "POST" and path == "dashboard":
            self.dashboards_created += 1
            item = self._new("dashboard", value["name"])
            self.dashcards[item["id"]] = []
            self.dashboard_data[item["id"]] = value
            return item
        if method == "GET" and path.startswith("dashboard/"):
            dashboard_id = int(path.split("/")[1])
            return {**self.dashboard_data[dashboard_id], "dashcards": self.dashcards[dashboard_id]}
        if method == "PUT" and path.startswith("dashboard/"):
            dashboard_id = int(path.split("/")[1])
            self.dashcards[dashboard_id] = value["dashcards"]
            self.dashboard_data[dashboard_id].update(value)
            return {}
        raise AssertionError((method, path, value))


def test_provision_rerun_reuses_cards_and_dashboards(monkeypatch, tmp_path):
    monkeypatch.setenv("METABASE_ADMIN_PASSWORD", "secret-in-test")
    monkeypatch.setenv("METABASE_RO_PASSWORD", "reader-secret")
    api = FakeAPI()
    catalog = tmp_path / "catalog.json"
    first = provisioner.provision(api, lambda: None, catalog)
    second = provisioner.provision(api, lambda: None, catalog)
    assert first["cards"] == second["cards"]
    assert first["dashboards"] == second["dashboards"]
    assert api.cards_created == 18
    assert api.dashboards_created == 3
    assert all(any(c.get("card_id") is None for c in cards) for cards in api.dashcards.values())
    assert "password" not in catalog.read_text().lower()


def test_explicit_upgrade_backs_up_before_updating_and_keeps_manual_cards(monkeypatch, tmp_path):
    monkeypatch.setenv("METABASE_ADMIN_PASSWORD", "secret-in-test")
    monkeypatch.setenv("METABASE_RO_PASSWORD", "reader-secret")
    api = FakeAPI()
    catalog = tmp_path / ".runtime" / "metabase" / "catalog.json"
    provisioner.provision(api, lambda: None, catalog)
    dashboard_id = next(iter(api.dashcards))
    api.dashcards[dashboard_id].append({"id": 99, "card_id": 999, "row": 0, "col": 0, "size_x": 12,
                                         "size_y": 4, "parameter_mappings": []})
    provisioner.provision(api, lambda: None, catalog, upgrade=True)
    backups = list((catalog.parent / "backups").glob("*.json"))
    assert len(backups) == 1
    assert len(json.loads(backups[0].read_text())["cards"]) == 18
    assert any(c.get("card_id") == 999 for c in api.dashcards[dashboard_id])
    assert any(c.get("visualization_settings", {}).get("text", "").startswith("**Cách đọc:**")
               for c in api.dashcards[dashboard_id])


def test_managed_dashboard_layout_flushes_full_width_tables():
    board = dashboard_specs()["Sales OLAP"]
    entries = [(i, spec) for i, spec in enumerate(board["cards"])]
    cards, _ = _layout_managed(entries)
    for card in cards:
        if card["size_x"] == 24:
            assert card["col"] == 0
        assert card["col"] + card["size_x"] <= 24
    assert [card["card_id"] for card in cards] == [0, 4, 1, 2, 3]
    assert cards[0]["size_x"] == cards[1]["size_x"] == 12
    assert cards[0]["row"] == cards[1]["row"] and cards[0]["col"] == 0 and cards[1]["col"] == 12
    assert cards[2]["size_x"] == cards[3]["size_x"] == cards[4]["size_x"] == 24
    assert cards[2]["row"] > cards[0]["row"]
    assert cards[3]["row"] == cards[2]["row"] + cards[2]["size_y"]
    assert cards[4]["size_y"] == 10 and cards[4]["row"] == cards[3]["row"] + cards[3]["size_y"]
