"""§8 Файловий сервіс ✅🟢 — видача file-token і власна поверхня файлового сервера.

Два роутери в одному модулі:
- ``router_a`` — «філійний» ендпоінт MyStat ``GET /v1/mystat/{branch_alias}/user/file-token``
  (обов'язкова авторизація access_token);
- ``router_b`` — поверхня файлового сервера ``/api/v1/files/*``: у справжньому проді це
  ОКРЕМИЙ динамічний хост (зараз fsx3.itstep.org), а в НАШІЙ версії ми самі виступаємо
  файловим хостом, тому його методи змонтовані просто в цьому застосунку.

``router`` — агрегат обох (саме його підключає app.main).
"""
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile

from ..config import MAX_UPLOAD_FILES
from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import MODE, handle

# Ліміти мок-завантажень (вміст не зберігається, але розмір і імена контролюємо).
MAX_FILE_BYTES = 25 * 1024 * 1024
_MAX_NAME_LEN = 120
_DIR_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def _bad(message: str, field: str = "summary", status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=[{"field": field, "message": message}])


def sanitize_filename(name: str | None) -> str:
    """Лишає тільки базове ім'я: без каталогів, керуючих символів і довжини понад ліміт."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "_", base).strip(" .")
    if not base:
        raise _bad("Некоректне ім'я файлу", "files")
    return base[:_MAX_NAME_LEN]


def sanitize_path(path: str) -> str:
    """Шлях у відповіді: без «..», порожніх сегментів і керуючих символів."""
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise _bad("Некоректний шлях", "path")
    return "/".join(sanitize_filename(p) for p in parts)


def _check_upload(f: Any) -> UploadFile:
    if not isinstance(f, UploadFile):
        raise _bad("Очікувався файл", "files")
    if f.size is not None and f.size > MAX_FILE_BYTES:
        raise _bad(f"Файл завеликий (макс. {MAX_FILE_BYTES // (1024 * 1024)} МБ)", "files", 413)
    return f

router_a = APIRouter(
    prefix="/v1/mystat/{branch_alias}",
    tags=["Files"],
    dependencies=[Depends(auth_ctx)],
)

router_b = APIRouter(
    prefix="/api/v1/files",
    tags=["Files"],
    # У справжньому проді файловий сервіс вимагає Bearer file-token; у моку
    # роутер був АНОНІМНИМ: будь-хто міг «видаляти» й перезаписувати файли.
    dependencies=[Depends(auth_ctx)],
)


# ── Router A: видача file-token ───────────────────────────────────────────────


@router_a.get(
    "/user/file-token",
    summary="Токен і адреса файлового сервера (localStorage.file_token)",
    responses={
        200: {
            "description": "url/domain/token/directories — структура підтверджена живою відповіддю.",
        },
        401: {"model": ApiError},
    },
)
async def file_token(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/user/file-token** 🟢 — структура звірена з живою відповіддю.

    Вхід у файловий сервіс. Відповідь кладеться фронтом у `localStorage.file_token`.

    Ключові поля:
    - **url** — база файлового сервера, **ДИНАМІЧНА**: зараз `https://fsx3.itstep.org/api/v1/files`,
      але хост НЕ фіксований — аватарки студентів віддаються з `fsx1`, статика фронта лежить на `fs1`.
      У своєму клієнті ЗАВЖДИ беріть `url`/`domain` з цієї відповіді — **не хардкодьте хост**.
    - **domain** — той самий хост без шляху (`https://fsx3.itstep.org`);
    - **token** — окремий JWT рівно на **48 годин** (не плутати з access_token на 30 днів!), HS256,
      claims: `{projectId:5, extId:<id_user_storage>, userId:"<logbook_id> РЯДКОМ", access:["file.create"]}`;
    - **directories** — hash-каталоги користувача:
      `homeworkDirId` (домашні роботи) · `portfolioDirId` (портфоліо) · `reviewDirId` (рев'ю) ·
      `examDirId` (екзамени) · `photoStudDirId` (фото студента) · `chatDirId` (вкладення чату).

    Усі запити до `url` підписуються: `Authorization: Bearer <token>` + заголовок `X-Language`.

    Поверхня самого файлового сервера (upload/info/delete/replace) — тег *Files*,
    префікс `/api/v1/files`.
    """
    return await handle(request, fixture_name="file-token.json")


# ── Router B: наша версія файлового сервера (/api/v1/files) ───────────────────


@router_b.post(
    "",
    summary="Завантаження файлів: multipart directory + files[]",
    responses={400: {"model": ApiError, "description": "Не передано каталог або файли."}},
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object",
        "required": ["directory", "files"],
        "properties": {
            "directory": {"type": "string", "description": "Каталог-одержувач: hash із file-token.directories."},
            "files": {"type": "array", "items": {"type": "string", "format": "binary"},
                      "description": "Один або кілька файлів (поле files[] повторюється)."},
        },
    }}}}},
)
async def upload_files(request: Request) -> Any:
    """**POST {url}** ✅ — у нашому маунті: `/api/v1/files` — завантаження одного/кількох файлів.

    multipart/form-data: `directory=<hash-каталог>` + `files[]=<File,…>`.
    Заголовки як у всього файлового сервісу: `Authorization: Bearer <file-token>` + `X-Language`.

    - Прогрес у фронті відображається через **upload events** (XHR `onprogress` /
      axios `onUploadProgress`): байти йдуть одним запитом, відсотки рахуються локально
      до отримання відповіді — серверних подій прогресу немає.
    - Відповідь — JSON зі списком збережених шляхів:
      `{"files":[{"path":"<directory>/<filename>"}]}`; отриманий `path` далі
      підставляється в ДЗ/рев'ю/екзамени/чат/портфоліо.

    > Mock: збирає шляхи з імен завантажених файлів, вміст не зберігається.
    > Ліміти: до MYSTAT_MAX_UPLOAD_FILES файлів, до 25 МБ кожен; імена санітизуються.
    > Proxy: форвардиться на MYSTAT_FILES_UPSTREAM (без нього — 501).
    """
    if MODE == "proxy":
        # Тіло не чіпаємо (form() його спожив би) — форвард читає його сам, з лімітом.
        return await handle(request, files=True)
    form = await request.form()
    directory = form.get("directory")
    if not isinstance(directory, str) or not _DIR_RE.match(directory):
        raise _bad("Не передано коректний каталог", "directory")
    uploads = form.getlist("files") or form.getlist("files[]")
    if not uploads:
        raise _bad("Не передано файли", "files")
    if len(uploads) > MAX_UPLOAD_FILES:
        raise _bad(f"Забагато файлів (макс. {MAX_UPLOAD_FILES})", "files", 413)
    result = [{"path": f"{directory}/{sanitize_filename(_check_upload(f).filename)}"} for f in uploads]
    return {"files": result}


@router_b.get("/info/{filename}", summary="Мета файлу")
async def file_info(request: Request, filename: str) -> Any:
    """**GET {url}/info/{filename}** ✅ — мета файлу: розмір, MIME, час, власник ⚠️ (точний набір полів не підтверджений).

    `filename` — ім'я/шлях файлу всередині одного з hash-каталогів з відповіді `user/file-token`.
    """
    return await handle(
        request,
        files=True,
        sample={"name": sanitize_filename(filename), "size": 0, "mimeType": "application/octet-stream"},
    )


@router_b.delete("/{path:path}", summary="Видалити файл")
async def delete_file(request: Request, path: str) -> Any:
    """**DELETE {url}/{path}** ✅ — видалити файл за шляхом, який повернуло завантаження (`files[].path`)."""
    return await handle(request, files=True, sample={"status": "ok", "path": sanitize_path(path)})


@router_b.post(
    "/replace-file",
    summary="Замінити наявний файл",
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object",
        "required": ["file", "token"],
        "properties": {
            "file": {"type": "string", "format": "binary", "description": "Новий файл."},
            "token": {"type": "string", "description": "Шлях СТАРОГО файлу (те, що повернуло завантаження)."},
            "keepOriginalName": {"type": "boolean", "default": False, "description": "Зберегти ім'я старого файлу."},
            "makeBackup": {"type": "boolean", "default": False, "description": "Залишити резервну копію заміненого."},
        },
    }}}}},
)
async def replace_file(request: Request) -> Any:
    """**POST {url}/replace-file** ✅ — заміна вмісту наявного файлу.

    multipart/form-data:
    - `file` — новий файл;
    - `token` — шлях **старого** файлу;
    - `keepOriginalName=true/false` — зберегти ім'я старого файлу;
    - `makeBackup=false/true` — залишити бекап заміненого ⚠️.

    Відповідь — шлях до результату заміни ⚠️.
    """
    if MODE == "proxy":
        return await handle(request, files=True)
    form = await request.form()
    file = _check_upload(form.get("file"))
    token = form.get("token")
    if not isinstance(token, str) or not token:
        raise _bad("Не передано token (шлях старого файлу)", "token")
    keep_original_name = str(form.get("keepOriginalName", "false")).lower() in ("1", "true", "on")
    make_backup = str(form.get("makeBackup", "false")).lower() in ("1", "true", "on")
    token = sanitize_path(token)
    base = token.rsplit("/", 1)[0] if "/" in token else ""
    new_name = sanitize_filename(file.filename)
    # token без каталогу («report.pdf») → раніше давав «report.pdf/newfile.pdf»
    new_path = token if keep_original_name else (f"{base}/{new_name}" if base else new_name)
    return {"path": new_path, "backup": make_backup}
 
 
# ── Агрегат для app.main — В КІНЦІ, після оголошення всіх маршрутів ── 
router = APIRouter(tags=["Files"]) 
router.include_router(router_a) 
router.include_router(router_b)
