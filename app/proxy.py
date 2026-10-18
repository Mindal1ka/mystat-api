"""Єдина точка виконання запиту: режим mock (фікстури/заглушки) або proxy (живе API).

Роутери НЕ повинні самі ходити в мережу — тільки викликати handle()/forward() звідси."""
import asyncio
from typing import Any, Optional

import httpx
from fastapi import HTTPException, Request, Response

from .config import FILES_UPSTREAM, MAX_BODY_BYTES, MODE, UPSTREAM
from .fixtures import FixtureNotFound, fixture

_client: Optional[httpx.AsyncClient] = None
_files_client: Optional[httpx.AsyncClient] = None
# Глобальний asyncio.Lock: лінива ініціалізація _client без гонки
# (перші два proxy-запити не повинні створити два клієнти/з'єднання).
_client_lock = asyncio.Lock()

# x-userid — справжня назва; x-user-id — на випадок клієнтів з іншим написанням:
# пересилаємо обидва, щоб заголовок не губився. x-l-session і user-agent теж потрібні upstream.
_PASSTHROUGH_HEADERS = (
    "authorization", "x-language", "x-userid", "x-user-id", "x-l-session", "user-agent",
)

# Hop-by-hop заголовки, які НЕМОЖНА копіювати з відповіді upstream
# (стосуються конкретного з'єднання, а не повідомлення).
# content-encoding теж викидаємо: httpx вже декодував тіло (gzip/br),
# і повторне декодування клієнтом зламало б відповідь.
_HOP_BY_HOP_HEADERS = frozenset(
    {"content-length", "transfer-encoding", "connection", "content-encoding"}
)

DISABLED_DETAIL = [
    {
        "field": "summary",
        "message": "Фича отключена в филиале: настоящий API отвечает 404 (см. MYSTAT_API.md, пометка ❌).",
    }
]


async def get_client() -> httpx.AsyncClient:
    """Лінива ініціалізація клієнта до upstream — під asyncio.Lock.

    Створення відкладене до першого proxy-запиту (в mock-режимі клієнт не створюється
    взагалі), а подвійна перевірка під локом виключає гонку двох перших запитів."""
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                # follow_redirects=False: редирект upstream віддаємо клієнту як є,
                # інакше Authorization міг би піти на сторонній хост.
                _client = httpx.AsyncClient(
                    base_url=UPSTREAM, timeout=20.0, follow_redirects=False
                )
    return _client


async def get_files_client() -> httpx.AsyncClient:
    """Клієнт до файлового сервера (MYSTAT_FILES_UPSTREAM) — окремий від mapi."""
    global _files_client
    if _files_client is None:
        async with _client_lock:
            if _files_client is None:
                _files_client = httpx.AsyncClient(
                    base_url=FILES_UPSTREAM, timeout=60.0, follow_redirects=False
                )
    return _files_client


async def close_client() -> None:
    """Graceful shutdown: закрити HTTP-клієнти до upstream (викликається з lifespan main.py)."""
    global _client, _files_client
    async with _client_lock:
        for c in (_client, _files_client):
            if c is not None:
                await c.aclose()
        _client = None
        _files_client = None


async def _read_body_limited(request: Request) -> bytes:
    """Прочитати тіло запиту з обмеженням MAX_BODY_BYTES (413 при перевищенні)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail=[{"field": "summary", "message": "Тіло запиту завелике"}])
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail=[{"field": "summary", "message": "Тіло запиту завелике"}])
        chunks.append(chunk)
    return b"".join(chunks)


async def forward(request: Request, *, files: bool = False) -> Response:
    """Проксі-режим: повторити запит у mapi.itstep.org з тим самим шляхом і ключовими заголовками.

    Крім авторизаційних передаємо `content-type` і `accept` запиту — інакше у
    multipart-запитів губиться boundary, а в JSON-тіла тип вмісту.
    З відповіді upstream копіюємо ВСІ заголовки КРІМ hop-by-hop — так до клієнта
    доїжджають X-Pagination-*, Content-Disposition, WWW-Authenticate тощо."""
    headers = {k: v for k, v in request.headers.items() if k.lower() in _PASSTHROUGH_HEADERS}
    if "content-type" in request.headers:
        headers["content-type"] = request.headers["content-type"]
    if "accept" in request.headers:
        headers["accept"] = request.headers["accept"]
    path = request.url.path
    # Шлях, що починається з «//», httpx трактує як network-path (інший хост) → SSRF.
    if not path.startswith("/") or path.startswith("//"):
        raise HTTPException(status_code=400, detail=[{"field": "summary", "message": "Некоректний шлях"}])
    query = f"?{request.url.query}" if request.url.query else ""
    if files:
        if not FILES_UPSTREAM:
            raise HTTPException(
                status_code=501,
                detail=[{
                    "field": "summary",
                    "message": "Файловий сервер у proxy-режимі не налаштований: "
                               "задайте MYSTAT_FILES_UPSTREAM (хост з /user/file-token, напр. https://fsx3.itstep.org).",
                }],
            )
        client = await get_files_client()
    else:
        client = await get_client()
    resp = await client.request(
        request.method,
        path + query,
        headers=headers,
        content=await _read_body_limited(request),
    )
    # Копіюємо всі заголовки відповіді upstream, крім hop-by-hop;
    # дублікати list-заголовків склеюємо через ", " (валідно),
    # АЛЕ set-cookie склеювати НЕМОЖНА: два куки в одному заголовку
    # браузер розбере як один битий (сесійне куки губиться) —
    # їх додаємо окремими raw-заголовками після створення Response.
    out_headers: dict[str, str] = {}
    set_cookies: list[str] = []
    for key, value in resp.headers.multi_items():
        if key.lower() in _HOP_BY_HOP_HEADERS:
            continue
        if key.lower() == "set-cookie":
            set_cookies.append(value)
            continue
        out_headers[key] = f"{out_headers[key]}, {value}" if key in out_headers else value
    response = Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=out_headers,
        media_type=resp.headers.get("content-type", "application/json"),
    )
    if set_cookies:
        response.raw_headers.extend(
            (b"set-cookie", value.encode("latin-1")) for value in set_cookies
        )
    return response


async def handle(
    request: Request,
    *,
    fixture_name: Optional[str] = None,
    sample: Any = None,
    disabled: bool = False,
    files: bool = False,
) -> Any:
    """Стандартне тіло обробника.

    - proxy → форвард у справжнє API (files=True → на MYSTAT_FILES_UPSTREAM, а без нього 501);
    - disabled=True → імітація 404 вимкненої фічі;
    - fixture_name → віддати examples/<fixture_name> (🟢 живі дані);
    - інакше sample (✅/⚠️ правдоподібна заглушка)."""
    if MODE == "proxy":
        return await forward(request, files=files)
    if disabled:
        raise HTTPException(status_code=404, detail=DISABLED_DETAIL)
    if fixture_name:
        try:
            # Читання/парсинг файлу — блоківна операція: відводимо в потік,
            # щоб не стопорити event loop (FixtureNotFound → падаємо далі в sample).
            return await asyncio.to_thread(fixture, fixture_name)
        except FixtureNotFound:
            pass
    if sample is not None:
        return sample
    return {"status": "ok", "mock": True}
