"""Configuration helpers for environment-based settings."""

import os
from pathlib import Path

WEATHER_API_KEY_ENV = "WEATHER_API_KEY"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_fallback(env_path: Path):
    """Minimal `.env` loader used when python-dotenv is unavailable."""
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def load_project_env(env_path: str | None = None):
    """Load project `.env` into process environment without overriding existing vars."""
    env_file = Path(env_path) if env_path else DEFAULT_ENV_PATH

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        _load_env_fallback(env_file)
        return

    load_dotenv(dotenv_path=env_file, override=False)


def get_weather_api_key(env_path: str | None = None) -> str | None:
    """Resolve weather API key from environment / optional project `.env`."""
    load_project_env(env_path=env_path)
    key = os.getenv(WEATHER_API_KEY_ENV)
    return key if key else None
