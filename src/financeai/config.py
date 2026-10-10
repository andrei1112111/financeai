from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE = Path.home() / ".financeai"

CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "financeai"
)
CONFIG_FILE = CONFIG_DIR / ".env"

# Порядок загрузки: локальный .env (для разработки), затем пользовательский
# конфиг (создаётся при первом запуске). Уже заданные переменные окружения
# имеют приоритет над обоими файлами.
load_dotenv()
load_dotenv(CONFIG_FILE)

BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
REASONING_EFFORT = "high"


def base_dir() -> Path:
    raw = os.environ.get("FINANCE_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_BASE.resolve()


def config_file() -> Path:
    return CONFIG_FILE


def has_api_key() -> bool:
    return bool(os.environ.get("DEEPSEEK", "").strip())


def api_key() -> str:
    key = os.environ.get("DEEPSEEK", "").strip()
    if not key:
        raise RuntimeError(
            "Не найден ключ DEEPSEEK. Добавь его в .env или в переменные окружения."
        )
    return key


def save_api_key(key: str) -> None:
    key = key.strip()
    if not key:
        raise ValueError("Пустой ключ DEEPSEEK.")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(f"DEEPSEEK={key}\n", encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass
    os.environ["DEEPSEEK"] = key
