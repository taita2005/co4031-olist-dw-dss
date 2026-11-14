import json
import pytest

from scripts.docker_pipeline import ensure_etl, ensure_model, should_run_etl, should_train


def test_empty_dw_runs_etl_once():
    calls = []
    result = ensure_etl(False, False, None, lambda: calls.append("etl"))
    assert result == "loaded"
    assert calls == ["etl"]


def test_certified_dw_skips_etl():
    calls = []
    assert ensure_etl(True, True, True, lambda: calls.append("etl")) == "skipped"
    assert calls == []


@pytest.mark.parametrize("sales,delivery", [(True, False), (False, True)])
def test_partial_dw_fails_closed(sales, delivery):
    with pytest.raises(RuntimeError, match="partially initialized"):
        should_run_etl(sales, delivery, None)


@pytest.mark.parametrize("ready", [False, None])
def test_uncertified_existing_dw_fails_closed(ready):
    with pytest.raises(RuntimeError, match="checks are missing or failed"):
        should_run_etl(True, True, ready)


@pytest.mark.parametrize("model_exists,metadata_exists", [(False, False), (False, True), (True, False)])
def test_missing_model_artifacts_trigger_training(tmp_path, model_exists, metadata_exists):
    model, metadata = tmp_path / "model.joblib", tmp_path / "metrics.json"
    if model_exists:
        model.touch()
    if metadata_exists:
        metadata.write_text(json.dumps({"etl_run_id": "run-1"}), encoding="utf-8")
    calls = []
    assert ensure_model("run-1", model, metadata, lambda: calls.append("train")) == "trained"
    assert calls == ["train"]


def test_model_for_current_run_is_preserved(tmp_path):
    model, metadata = tmp_path / "model.joblib", tmp_path / "metrics.json"
    model.touch()
    metadata.write_text(json.dumps({"etl_run_id": 42}), encoding="utf-8")
    calls = []
    assert ensure_model("42", model, metadata, lambda: calls.append("train")) == "skipped"
    assert calls == []


def test_stale_model_is_retrained(tmp_path):
    model, metadata = tmp_path / "model.joblib", tmp_path / "metrics.json"
    model.touch()
    metadata.write_text(json.dumps({"etl_run_id": "old"}), encoding="utf-8")
    calls = []
    assert ensure_model("new", model, metadata, lambda: calls.append("train")) == "trained"
    assert calls == ["train"]


@pytest.mark.parametrize("contents", ["{broken", "{}", "[]"])
def test_bad_model_metadata_fails_with_actionable_error(tmp_path, contents):
    model, metadata = tmp_path / "model.joblib", tmp_path / "metrics.json"
    model.touch()
    metadata.write_text(contents, encoding="utf-8")
    with pytest.raises(RuntimeError, match="metadata"):
        should_train("run-1", model, metadata)
