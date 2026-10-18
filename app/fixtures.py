"""Завантажувач фікстур — живих відповідей справжнього API, збережених у examples/."""
import json
from pathlib import Path
from typing import Any

from .config import FIXTURES_DIR


class FixtureNotFound(LookupError):
    pass


def _safe_path(name: str) -> Path:
    """Шлях до фікстури строго всередині FIXTURES_DIR (захист від ../ і абсолютних шляхів)."""
    base = FIXTURES_DIR.resolve()
    try:
        path = (base / name).resolve()
        path.relative_to(base)
    except (ValueError, OSError):
        raise FixtureNotFound(name)
    return path


def fixture(name: str) -> Any:
    """Прочитати examples/<name>.json. Кожен виклик парсить заново (без мутацій кешу)."""
    path = _safe_path(name)
    if not path.is_file():
        raise FixtureNotFound(name)
    return json.loads(path.read_text(encoding="utf-8-sig"))  # utf-8-sig: терпить BOM від PowerShell


def has_fixture(name: str) -> bool:
    try:
        return _safe_path(name).is_file()
    except FixtureNotFound:
        return False
