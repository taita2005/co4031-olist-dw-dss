import shutil
from pathlib import Path

from scripts import docker_init


def _read_env(path):
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)


def test_bootstrap_fills_example_and_preserves_passwords_and_ports(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_init, "ROOT", tmp_path)
    example = Path(__file__).resolve().parents[1] / ".env.example"
    env_path = tmp_path / ".env"
    shutil.copyfile(example, env_path)

    docker_init.init_env(env_path)
    generated = _read_env(env_path)
    password_keys = ("POSTGRES_ADMIN_PASSWORD", "BTL_PASSWORD", "METABASE_RO_PASSWORD",
                     "METABASE_DB_PASSWORD", "METABASE_ADMIN_PASSWORD")
    assert all(generated[key] for key in password_keys)
    assert generated["METABASE_ADMIN_EMAIL"] == "admin@olist.local"
    assert generated["METABASE_PORT"] == "3000"
    assert generated["STREAMLIT_PORT"] == "8501"
    first_passwords = {key: generated[key] for key in password_keys}
    generated["METABASE_ADMIN_PASSWORD"] = "custom-admin-password"
    generated["METABASE_PORT"] = "3310"
    generated["STREAMLIT_PORT"] = "8510"
    env_path.write_text("".join(f"{key}={value}\n" for key, value in generated.items()), encoding="utf-8")

    docker_init.init_env(env_path)
    repeated = _read_env(env_path)
    assert {key: repeated[key] for key in password_keys if key != "METABASE_ADMIN_PASSWORD"} == {
        key: value for key, value in first_passwords.items() if key != "METABASE_ADMIN_PASSWORD"
    }
    assert repeated["METABASE_ADMIN_PASSWORD"] == "custom-admin-password"
    assert repeated["METABASE_PORT"] == "3310"
    assert repeated["STREAMLIT_PORT"] == "8510"
    assert env_path.stat().st_mode & 0o777 == 0o600


def test_bootstrap_default_path_is_compose_dotenv():
    assert docker_init.ENV_PATH.name == ".env"
