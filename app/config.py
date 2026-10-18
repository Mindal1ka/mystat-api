"""Налаштування застосунку MyStat API (FastAPI-реалізація за MYSTAT_API.md)."""
import os
from pathlib import Path

# Корінь репозиторію: app/config.py → parents[1] == корінь з examples/
ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT_DIR / "examples"

TITLE = "MyStat API"
VERSION = "1.0.3"  # = assets/version.json прод-фронту на момент реверсу

# Режим роботи:
#   mock  — відповідаємо фікстурами з examples/ і правдоподібними заглушками (безпечно, офлайн)
#   proxy — проксуємо всі запити до справжнього https://mapi.itstep.org (потрібен живий токен)
MODE = os.environ.get("MYSTAT_MODE", "mock").lower().strip()
UPSTREAM = os.environ.get("MYSTAT_UPSTREAM", "https://mapi.itstep.org").rstrip("/")

DEFAULT_ALIAS = os.environ.get("MYSTAT_ALIAS", "pl")
DEFAULT_LANG = os.environ.get("MYSTAT_LANG", "uk")

# ── Безпека мока ─────────────────────────────────────────────────────────────
# Мок видає JWT будь-кому й віддає адмінські дії, тому за замовчуванням він
# дозволений лише на loopback. Для навмисного запуску в мережі (docker тощо)
# потрібно явно виставити MYSTAT_ALLOW_REMOTE_MOCK=1.
ALLOW_REMOTE_MOCK = os.environ.get("MYSTAT_ALLOW_REMOTE_MOCK", "").strip() == "1"

# Перевіряти exp у JWT (мок/проксі). Вимкнено за замовчуванням: у Swagger часто
# вставляють старий справжній токен. Ввімкнення: MYSTAT_VERIFY_EXP=1.
VERIFY_EXP = os.environ.get("MYSTAT_VERIFY_EXP", "").strip() == "1"

# CORS: за замовчуванням тільки localhost/127.0.0.1/[::1] на будь-якому порту.
# Свій список (через кому): MYSTAT_CORS_ORIGINS=https://a.example,https://b.example
CORS_ORIGINS = [o.strip() for o in os.environ.get("MYSTAT_CORS_ORIGINS", "").split(",") if o.strip()]
CORS_LOCAL_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

# Адреса цього сервісу для блоку servers в OpenAPI.
PUBLIC_URL = os.environ.get("MYSTAT_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")

# Ліміти завантажень (байти / кількість).
MAX_BODY_BYTES = int(os.environ.get("MYSTAT_MAX_BODY_MB", "50")) * 1024 * 1024
MAX_UPLOAD_FILES = int(os.environ.get("MYSTAT_MAX_UPLOAD_FILES", "10"))

# Файловий сервер у proxy-режимі: /api/v1/files/* НЕ живе на mapi.itstep.org
# (це окремий динамічний хост, напр. fsx3.itstep.org, його адреса — у /user/file-token).
# Якщо задано, ці маршрути форвардяться туди; якщо ні — відповідаємо 501.
FILES_UPSTREAM = os.environ.get("MYSTAT_FILES_UPSTREAM", "").rstrip("/")
