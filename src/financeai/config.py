from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE = Path.home() / "financeai"


def base_dir() -> Path:
    raw = os.environ.get("FINANCE_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_BASE.resolve()


def api_key() -> str:
    key = os.environ.get("DEEPSEEK")
    if not key:
        raise RuntimeError(
            "Не найден ключ DEEPSEEK. Добавь его в .env или в переменные окружения."
        )
    return key


BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
REASONING_EFFORT = "high"
