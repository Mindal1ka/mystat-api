# -*- coding: utf-8 -*-
"""Генерує openapi.json у корені репозиторію зі застосунку FastAPI (app/).

Запуск (з venv, де встановлено залежності):
    python tools/openapi_dump.py            # пише openapi.json у корені (компактний JSON, UTF-8)
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

spec = app.openapi()
(ROOT / "openapi.json").write_text(json.dumps(spec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
ops = sum(1 for item in spec["paths"].values() for m in item if m in ("get", "post", "put", "patch", "delete"))
print(f"openapi.json: {len(spec['paths'])} шляхів, {ops} операцій")
