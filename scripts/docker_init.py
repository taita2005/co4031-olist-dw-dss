"""Create local Compose credentials before any service starts."""
import os
from pathlib import Path
import secrets
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def init_env(path: Path = ENV_PATH) -> None:
    current = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                current[key] = value
    for key in ("POSTGRES_ADMIN_PASSWORD", "BTL_PASSWORD", "METABASE_RO_PASSWORD",
                "METABASE_DB_PASSWORD", "METABASE_ADMIN_PASSWORD"):
        if not current.get(key):
            current[key] = secrets.token_urlsafe(32)
    current.setdefault("METABASE_ADMIN_EMAIL", "admin@olist.local")
    current.setdefault("METABASE_PORT", "3000")
    current.setdefault("STREAMLIT_PORT", "8501")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        for key, value in current.items():
            f.write(f"{key}={value}\n")
        f.flush()
        os.fsync(f.fileno())
        temporary = Path(f.name)
    owner = ROOT.stat()
    os.chown(temporary, owner.st_uid, owner.st_gid)
    temporary.chmod(0o600)
    os.replace(temporary, path)
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    os.chown(runtime, owner.st_uid, owner.st_gid)


if __name__ == "__main__":
    init_env()
    print("Local Compose credentials prepared in .env (mode 600).")
