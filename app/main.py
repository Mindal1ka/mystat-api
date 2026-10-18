"""MyStat API — FastAPI-реалізація за реверсом mystat.itstep.org (див. MYSTAT_API.md, how.md).

Запуск: uvicorn app.main:app --reload --port 8000   → Swagger UI на /docs
Режими: MYSTAT_MODE=mock (фікстури examples/, за замовчуванням) | proxy (живе mapi.itstep.org)."""
import ipaddress
import logging
import os
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .config import (
    ALLOW_REMOTE_MOCK,
    CORS_LOCAL_REGEX,
    CORS_ORIGINS,
    MAX_BODY_BYTES,
    MODE,
    PUBLIC_URL,
    TITLE,
    VERSION,
)
from .docs import redoc_ui, swagger_ui
from .proxy import close_client
from .routers import (
    admin_shop,
    awards_chat,
    auth,
    branch_core,
    extras,
    files,
    homework,
    info,
    news_missions,
    public,
    schedule,
    study_misc,
    survey,
)

DESCRIPTION = """
Реверс-інжиніринг **mystat.itstep.org** → повна специфікація + робочий бекенд.
Джерело: реверс JS-бандлів Angular SPA · живі проби реального акаунта (2026-08) · звірка зі збіркою фронту 2026-10 (release b480fd2).

---
**Легенда позначок**

| Маркер | Значення |
|---|---|
| 🟢 | підтверджено живим запитом реального акаунта |
| ✅ | підтверджено кодом бандлів фронтенду |
| ⚠️ | відновлено за непрямими ознаками — уточнити перехопленням трафіку |
| ❌ | справжнє API відповідає 404 — фіча вимкнена або видалена на проді |

**Ключові інваріанти**
- **Два різних ID**: `logbook_id` (= JWT.sub/id, `balances[].user_id`, адмінський `id_stud`) ≠ `id_user_storage` (= заголовок `X-UserId`). Не плутати!
- Заголовки: `Authorization: Bearer <JWT>`, `X-Language` (lang), `X-UserId`.
- JWT — HS256, доступ рівно **30 діб**; file_token — рівно **48 годин**, хост файлового сервера **динамічний** (беріть з `/user/file-token`).
- Пагінація трьох стилів: laravel `pagination[page]`, yii `page/per_page`, flask `limit/offset`; у ледачих розділів номери сторінок — заголовками `X-Pagination-*`.
- Помилки — масивом `[{field, message}]`.

**Карта модулів**
| База | Де живе |
|---|---|
| `/v1/mystat/auth/*` | логін/токени (без гілки) |
| `/v1/mystat/{branch_alias}/*` | майже все (isMultiBranches=true), включно з розкладом `/schedule/*`, `/video/link`, гейміфікацією |
| `/v1/config/{appId}` | публічний конфіг застосунку |
| динамічний host з `/user/file-token` | файловий сервіс (зараз fsx3) |

**Socket.io**: notify-socket-logbook / log-socket-mystat / chat-socket-logbook `.itstep.org`
(`query.alias`, `auth.token`, події — див. тег *Docs & Info* → `/v1/info/sockets`).

⚠️ Неофіційна документація. Проєкт IT Step не пов'язаний з цією реалізацією.
"""

log = logging.getLogger("mystat.mock")


def _bind_host() -> str:
    """Хост, на якому запущено uvicorn: --host з argv, інакше UVICORN_HOST/MYSTAT_BIND_HOST,
    інакше дефолт uvicorn (127.0.0.1)."""
    argv = sys.argv
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--host="):
            return arg.split("=", 1)[1]
    return os.environ.get("MYSTAT_BIND_HOST") or os.environ.get("UVICORN_HOST") or "127.0.0.1"


def _is_loopback(host: str) -> bool:
    host = host.strip("[]")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Старт: у mock-режимі відмовляємось стартувати на не-loopback хості (мок видає JWT
    будь-кому). Обхід: MYSTAT_ALLOW_REMOTE_MOCK=1 (тоді лише гучне попередження).
    Клієнт до upstream створюється ліниво при першому proxy-запиті.
    Shutdown: акуратно закрити httpx-клієнти до upstream."""
    if MODE != "proxy":
        host = _bind_host()
        if not _is_loopback(host):
            if not ALLOW_REMOTE_MOCK:
                raise RuntimeError(
                    f"Мок MyStat не стартує на {host}: логін приймає будь-які облікові дані. "
                    "Біндьте на 127.0.0.1 або явно задайте MYSTAT_ALLOW_REMOTE_MOCK=1."
                )
            log.warning("!!! Мок слухає %s без автентифікації — доступний з мережі !!!", host)
    yield
    await close_client()


TAGS = [
    {"name": "Auth", "description": "логін, refresh, відновлення пароля, вхід за SMS, /auth/me."},
    {"name": "Branch", "description": "конфіг філії, лічильники меню, гейміфікація, промокод, профіль."},
    {"name": "Study", "description": "оцінка уроків, рапорти, договір, Cyberfit, відгуки, онбординг, sms/mailing."},
    {"name": "Homework", "description": "домашні роботи. Статуси — числовий енам 1=Done/2=Examination/3=UntilExecution/5=Retake (НЕ done/undone!); фільтри type[],spec_id[],sort,status,overdue,for_last_year,limit,homework_id; + GET /homework/{id}."},
    {"name": "Schedule", "description": "розклад — філійні шляхи /mystat/{alias}/schedule/*; get-month приймає type=week|month і date_filter=понеділок."},
    {"name": "Surveys & Progress", "description": "тести/опитування/відповіді/прогрес + інтерв'ю-квізи /quiz/*. survey-user-attempts вимагають {id} у шляху!"},
    {"name": "News", "description": "новини."},
    {"name": "Missions", "description": "місії — GET /missions/get-list + POST send-to-review/{id}. На проді pl зараз 404 (модуль вимкнено)."},
    {"name": "Awards & Payments", "description": "нагороди батька: CRUD /custom-awards/awards|award/{id}, give-award, аватари-предмети, поповнення (topup-options, pay-link, providers)."},
    {"name": "Chat", "description": "чат REST: /chat/room-list + літеральний /sender/conversation[/messages|/decrement-unreaded|/message-edit|/message-delete]."},
    {"name": "Shop", "description": "магазин: products(+get-others,get-quantity), orders, create-order, discard-order, get-providers. Статуси замовлення: 1|3 нове, 2|5 скасоване, 4 закрите."},
    {"name": "Dashboard & Stats", "description": "дашборд і статистика: count/homework, statistic/*, progress/*, gaming/is-star. Періоди: month|half_year|year."},
    {"name": "Contacts", "description": "контакти+Signal: /contacts, send-ceo/send-teach, довідки get-reference-data?type=1 (blob), /signal."},
    {"name": "Payments+", "description": "платежі: /payment(реквізити), history, schedule, link, get-providers, get-next-payment, get-offer-contract."},
    {"name": "Club", "description": "клуби: get-clubs, transactions, get-balance, link, get-providers, abonements, buy-abonement, download-schedules."},
    {"name": "Nutrition", "description": "харчування: QR (/students/get-qr-code), баланс/транзакції, меню за датами, замовлення, payments/success."},
    {"name": "Library", "description": "бібліотека і відгуки: library/list, settings/history-specs, reviews/list."},
    {"name": "Admin", "description": "список студентів, вхід як студент (rolePerm admin.mystat.view)."},
    {"name": "Files", "description": "file-token + поверхня файлового сервера (динамічний хост)."},
    {"name": "Public", "description": "конфіг застосунку, переклади (❌ прибрані — статика i18n), sentry."},
    {"name": "Docs & Info", "description": "Довідка цього сервісу: список операцій, події сокетів, легенда. У справжньому API відсутній."},
]

app = FastAPI(
    title=TITLE,
    version=VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS,
    docs_url=None,   # /docs перевизначається нижче: темна тема + UX (app/docs.py)
    redoc_url=None,  # /redoc теж своя
    lifespan=lifespan,  # graceful shutdown httpx-клієнта proxy-режиму
    servers=[
        {"url": PUBLIC_URL, "description": f"цей сервіс (режим: {MODE})"},
        {"url": "https://mapi.itstep.org/v1", "description": "справжній прод (для звірки)"},
    ],
)

# CORS: за замовчуванням лише localhost-origins (MYSTAT_CORS_ORIGINS — свій список).
# allow_credentials=False: «будь-який origin + креденшели» — класична діра.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=None if CORS_ORIGINS else CORS_LOCAL_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Відсікає запити із заявленим Content-Length понад MYSTAT_MAX_BODY_MB (413).
    Chunked-тіла додатково обмежує proxy._read_body_limited і перевірки в files.py."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": [{"field": "summary", "message": "Тіло запиту завелике"}]},
        )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """422 в контракті помилок [{field, message}] (MYSTAT_API §«Помилки»):
    дефолтний FastAPI-формат {"detail":[{loc,msg,type}]} не відповідав
    заявленому і ламав парсинг фронтендом."""
    errors: list[dict[str, str]] = []
    for e in exc.errors():
        loc = ".".join(str(part) for part in e.get("loc", ()) if part != "body")
        field = loc.split(".")[-1] if loc else "summary"  # «query.date_filter» → «date_filter»
        errors.append({"field": field, "message": e.get("msg", "validation_error")})
    return JSONResponse(status_code=422, content={"detail": errors})

for router in (
    auth.router,
    branch_core.router,
    study_misc.router,
    homework.router,
    schedule.router,
    survey.router,
    news_missions.router,
    awards_chat.router,
    admin_shop.router,
    extras.router,
    files.router,
    public.router,
    info.router,
):
    app.include_router(router)


@app.get("/docs", include_in_schema=False)
async def docs_page() -> HTMLResponse:
    """Swagger UI: темна тема за замовчуванням, пошук, monokai, persist Authorization."""
    return swagger_ui(
        openapi_url=app.openapi_url,
        title=f"{TITLE} — Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_page() -> HTMLResponse:
    return redoc_ui(openapi_url=app.openapi_url, title=f"{TITLE} — ReDoc")


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": TITLE,
        "version": VERSION,
        "mode": MODE,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "source_docs": ["docs/MYSTAT_API.md", "docs/how.md"],
    }
