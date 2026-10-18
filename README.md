# mystat-api

> **EN (short).** Unofficial, educational reverse-engineering of the public web client of *MyStat*
> (`mystat.itstep.org`): a documented REST/socket.io API description plus a runnable **FastAPI** server with
> Swagger UI. It runs in two modes: **`mock`** (offline, anonymised fixtures, safe) and **`proxy`**
> (forwards requests to the real `mapi.itstep.org` using *your own* credentials/token).
> Not affiliated with, endorsed by, or connected to IT STEP / MyStat. Use only your own account and respect the
> service's terms. The vendor's front-end code is **not** included. MIT licensed.
>
> Quick start: `pip install -r requirements.txt && uvicorn app.main:app --port 8000` → <http://127.0.0.1:8000/docs>.

---

# MyStat API — документація та FastAPI-реалізація

Неофіційний навчальний проєкт: за публічним фронтендом **mystat.itstep.org** описано API (REST + socket.io +
файловий сервіс) і зроблено робочий сервер на **FastAPI** з інтерактивним Swagger UI («Try it out»).

> ⚠️ **Застереження.**
> - Проєкт **неофіційний**, створений **для навчальних цілей**; він **не афілійований** з IT STEP та MyStat і не схвалений ними.
> - Назви та торговельні марки належать їхнім власникам.
> - Використовуйте **лише власні облікові дані** й дотримуйтесь умов користування сервісом. Не навантажуйте чужий API.
> - Токени, паролі й сирі відповіді з персональними даними **ніколи не комітьте** (`.gitignore` це враховує).
> - Фронтенд-код вендора (JS-бандли) у репозиторій **не входить**; `tools/fetch_bundles.py` завантажує його локально.

## Що всередині

| Шлях | Призначення |
|---|---|
| `app/` | застосунок FastAPI: роутери за розділами API, режими mock/proxy, кастомний Swagger UI |
| `docs/MYSTAT_API.md` | повний опис API (адреси, заголовки, JWT, ендпоінти, сокети) + §15 — зміни збірки 2026-10 |
| `docs/how.md` | методика реверсу: як з бандлів отримати опис API і оновити його при новій версії |
| `openapi.json` | згенерована специфікація OpenAPI 3.1 (`python tools/openapi_dump.py`) |
| `examples/` | анонімізовані фікстури відповідей (див. `examples/README.md`) |
| `tools/` | скрипти реверсу: завантаження й порівняння бандлів, пошук ендпоінтів, жива звірка |
| `smoke_test.py` | самоперевірка (~90 перевірок через `TestClient`) |

## Швидкий старт

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
На Windows достатньо `start.bat`. Далі:

| Адреса | Що там |
|---|---|
| <http://127.0.0.1:8000/docs> | Swagger UI (темна тема, пошук, «Try it out») |
| <http://127.0.0.1:8000/redoc> | ReDoc |
| <http://127.0.0.1:8000/openapi.json> | специфікація OpenAPI |

Перевірка: `python smoke_test.py`.

## Режими

| Режим | Увімкнення | Поведінка |
|---|---|---|
| `mock` *(типово)* | — | Відповідає фікстурами з `examples/` і правдоподібними заглушками. Офлайн, безпечно. Логін видає **фейковий** JWT з правильними claims — натисніть **Authorize** у Swagger і вставте його. Приймає будь-які облікові дані, тому типово слухає лише loopback (`MYSTAT_ALLOW_REMOTE_MOCK=1` — явний обхід). |
| `proxy` | `MYSTAT_MODE=proxy` | Форвардить кожен запит у справжній `https://mapi.itstep.org` із вашими заголовками. Потрібен ваш власний токен: логін через `POST /v1/mystat/auth/login` (або токен із браузера) і вставка в **Authorize**. Файловий сервер: `MYSTAT_FILES_UPSTREAM=https://<хост із user/file-token>`. |

Інші змінні: `MYSTAT_UPSTREAM`, `MYSTAT_ALIAS` (філія, типово `pl`), `MYSTAT_LANG`, `MYSTAT_CORS_ORIGINS`,
`MYSTAT_MAX_BODY_MB` — див. `app/config.py`.

PowerShell: `$env:MYSTAT_MODE = "proxy"; uvicorn app.main:app --port 8000`.
Токен тримайте лише в Swagger/сесії — не у файлах.

## Позначки достовірності

🟢 підтверджено живим запитом · ✅ підтверджено кодом бандлів · ⚠️ відновлено за непрямими ознаками ·
❌ на проді відповідає 404 (фіча вимкнена у філії; мок теж віддає 404).

## Оновлення API

`assets/version.json` може не змінюватися при перезбірці, тому порівнюйте поле `release` в environment-чанку:

```bash
python -I tools/fetch_bundles.py ../fresh_bundles               # свіжі публічні бандли в НОВУ теку
python -I tools/diff_bundles.py ../old_bundles ../fresh_bundles  # що змінилось
```
Докладніше — `docs/how.md` §7. Станом на 2026-10-18 відмінності між збірками малі (§15 в `docs/MYSTAT_API.md`).

## Ліцензія

[MIT](LICENSE) © 2026 Mindal1ka.
