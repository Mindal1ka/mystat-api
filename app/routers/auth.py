"""§3 Auth-ендпоінти (без гілки) — ЕТАЛОННИЙ РОУТЕР: інші розділи пишуться в цьому ж стилі.

Правила стилю:
- префікси повторюють прод: /v1/mystat/auth/*; «гілкові» роутери — prefix="/v1/mystat/{branch_alias}";
- кожен ендпоінт: докладний markdown-опис (маркер 🟢/✅/⚠️/❌, реальний URL, заголовки,
  тіло з типами, відповідь, особливості), responses= з моделлю помилки ApiError;
- тіло обробника — завжди через handle()/forward() з ..proxy (mock|proxy режими);
- фікстури для 🟢-ендпоінтів підключаються внутрішнім завантажувачем (без посилань у документації)."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx, language_header, make_fake_jwt, userid_header
from ..models.common import ApiError
from ..proxy import MODE, forward, handle
from ..fixtures import fixture

router = APIRouter(prefix="/v1/mystat", tags=["Auth"])


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class LoginIn(BaseModel):
    """Форма входу (поля форми логіна фронту)."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"login": "student_demo", "password": "••••••"}]})

    login: str = Field(min_length=1, max_length=256, description="Логін або e-mail студента.", examples=["student_demo"])
    password: str = Field(min_length=1, max_length=1024, description="Пароль.", examples=["secret123"])


class EmptyBody(BaseModel):
    """Порожнє JSON-тіло `{}` — так викликають фронтові POST без параметрів."""

    model_config = ConfigDict(json_schema_extra={"examples": [{}]})


class PasswordLinkIn(BaseModel):
    email: str = Field(description="E-mail для листа відновлення.", examples=["user@gmail.com"])


class PasswordResetIn(BaseModel):
    token: str = Field(description="Токен з посилання листа (?t=...).")
    password: str = Field(description="Новий пароль.", min_length=6)
    password_repeat: str = Field(
        alias="passwordRepeat", description="Повтор пароля (поле форми passwordRepeat)."
    )


class PasswordStoreIn(BaseModel):
    """Створення пароля при першому вході за запрошенням. Точний набір полів ⚠️."""

    model_config = ConfigDict(extra="allow")

    password: str = Field(min_length=6)


class PhonesByStudIn(BaseModel):
    """Ідентифікатор студента. Точний формат ⚠️ (імовірно {id_stud} або {phone_hint})."""

    model_config = ConfigDict(extra="allow")

    id_stud: Optional[int] = Field(default=None, description="logbook_id студента ⚠️")


class SendAuthCodeIn(BaseModel):
    phone: str = Field(description="Телефон із get-phones-to-auth-by-stud.", examples=["+380..."])


class LoginByCodeIn(BaseModel):
    phone: str = Field(description="Телефон.")
    code: str = Field(description="Код з SMS.")


class RelativeIn(BaseModel):
    """Додавання родича. Поля відновлені за непрямими ознаками ⚠️."""

    model_config = ConfigDict(extra="allow")

    firstname: str
    lastname: str
    created_by: int = Field(description="id_user_storage створювача (= X-UserId).")
    contacts: list[dict[str, str]] = Field(
        default_factory=list,
        description='[{"channel": "mail", "value": "email"}]',
    )


# ── Ендпоінти ─────────────────────────────────────────────────────────────────


@router.post(
    "/auth/login",
    summary="Вхід: отримати access_token (відповідь — plain-text JWT)",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {"text/plain": {"example": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...."}},
            "description": "Рядок JWT (responseType:'text' у фронті!).",
        },
        401: {"model": ApiError, "description": "Невірний логін/пароль."},
    },
)
async def login(body: LoginIn, request: Request) -> Any:
    """**POST /v1/mystat/auth/login** ✅🟢(структура)

    Логін за парою логін+пароль.

    - **Відповідь**: `text/plain` — рядок **JWT** (фронт робить запит з `responseType:"text"` і кладе його в
      `localStorage.access_token`). Payload токена несе весь профіль: `sub/id` (logbook_id),
      `id_user_storage` (→ заголовок `X-UserId`), `branch_alias`, `lang`, `profile`, `project_id`.
    - Після логіна фронт одразу викликає `POST /auth/me`, щоб проставити заголовки.
    - Помилки — масивом `[{field:"login"|"password"|"summary", message}]`.

    > Mock: повертає фейковий JWT з коректним набором claims — ним можна авторизуватися
    > в решті Swagger UI через кнопку **Authorize**. Облікові дані НЕ перевіряються, тому
    > мок стартує лише на loopback (див. lifespan у main.py, MYSTAT_ALLOW_REMOTE_MOCK)."""
    if MODE == "proxy":
        return await forward(request)
    token = make_fake_jwt(username=body.login)
    return PlainTextResponse(token, media_type="text/plain")


@router.post("/auth/logout", summary="Вихід (інвалідація сесії)", dependencies=[Depends(auth_ctx)])
async def logout(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    return await handle(request)


@router.post(
    "/auth/me",
    summary="Повний об'єкт акаунта (після кожного логіна)",
    responses={200: {"description": "Account JSON — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def me(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**POST /v1/mystat/auth/me** 🟢 — структура звірена з живою відповіддю.

    Викликається фронтом **після логіна** (і після refresh), щоб встановити:
    - `X-Language` ← `lang`;
    - `X-UserId` ← `id_user_storage` (= `user_profiles[*][*].user_id`; це НЕ logbook_id!);
    - `branch_alias`, `child_id` (для батька).

    Ключові поля відповіді:
    - `id` = JWT.sub — **logbook_id**;
    - `id_user_storage` — акаунт у user-storage;
    - `user_profiles` → `{project_id: {branch_id: [profile...]}}`;
    - `user_storage` — ПІБ/дата народження;
    - для `profile:"relative"` додатково `childs[{id, profiles[{logbook_id,...}]}]`, `rolePerm`.

    > Body — порожній JSON `{}`."""
    return await handle(request, fixture_name="me.json")


@router.post(
    "/auth/refresh",
    summary="Оновити access_token (одноразово за будь-якого 401)",
    response_class=PlainTextResponse,
    dependencies=[Depends(auth_ctx)],
)
async def refresh(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/auth/refresh** ✅

    Інтерцептор фронту: на будь-який `401` (крім самого login) один раз смикає refresh
    (shared subject — паралельні запити чекають новий токен), повторює запит.
    `401` від refresh = локальний логаут. Відповідь — `text/plain` новий JWT."""
    if MODE == "proxy":
        return await forward(request)
    return PlainTextResponse(make_fake_jwt(jti="refreshed"), media_type="text/plain")


@router.post("/auth/password/link", summary="Надіслати посилання відновлення пароля")
async def password_link(body: PasswordLinkIn, request: Request) -> Any:
    """**POST /v1/mystat/auth/password/link** ✅ — body `{email}`; відповідь text/plain."""
    return await handle(request, sample={"status": "ok"})


@router.get("/auth/password/check", summary="Перевірити токен з листа відновлення")
async def password_check(token: str, request: Request) -> Any:
    """**GET /v1/mystat/auth/password/check?token=…** ✅"""
    return await handle(request, sample={"valid": True})


@router.post("/auth/password/reset", summary="Скидання пароля за токеном з листа")
async def password_reset(body: PasswordResetIn, request: Request) -> Any:
    """**POST /v1/mystat/auth/password/reset** ✅ — body `{token, password, passwordRepeat}`."""
    return await handle(request, sample={"status": "ok"})


@router.post("/user-storage/password/store", summary="Створити пароль при першому вході (запрошення)")
async def password_store(body: PasswordStoreIn, request: Request) -> Any:
    """**POST /v1/mystat/user-storage/password/store** ✅

    Абсолютний шлях: `apiUrl + "/mystat" + "/user-storage/password/store"` (без гілки)."""
    return await handle(request, sample={"status": "ok"})


@router.post(
    "/relatives/get-phones-to-auth-by-stud",
    summary="Телефони студента для швидкого входу батька за SMS",
    tags=["Auth"],
)
async def phones_to_auth(body: PhonesByStudIn, request: Request) -> Any:
    """**POST /v1/mystat/relatives/get-phones-to-auth-by-stud** ✅ — відповідь: список телефонів (маскованих)."""
    return await handle(request, sample=["+380 •• ••• •• 12", "+380 •• ••• •• 44"])


@router.post("/user-storage/password/send-auth-code", summary="Надіслати код входу за SMS")
async def send_auth_code(body: SendAuthCodeIn, request: Request) -> Any:
    """**POST /v1/mystat/user-storage/password/send-auth-code** ✅ — body `{phone}`."""
    return await handle(request, sample={"status": "sent"})


@router.post(
    "/auth/login-by-auth-code",
    summary="Вхід за кодом із SMS → plain-text JWT",
    response_class=PlainTextResponse,
)
async def login_by_code(body: LoginByCodeIn, request: Request) -> Any:
    """**POST /v1/mystat/auth/login-by-auth-code** ✅ — body `{phone, code}`; відповідь — рядок JWT."""
    if MODE == "proxy":
        return await forward(request)
    return PlainTextResponse(make_fake_jwt(), media_type="text/plain")


@router.post(
    "/user-storage/relative",
    summary="Додати родича (абсолютний шлях, без гілки)",
    tags=["Auth"],
)
async def add_relative(body: RelativeIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/user-storage/relative** ✅⚠️

    Викликається як абсолют (`apiUrl + "/mystat" + path`) — БЕЗ `/{alias}`.
    Body ⚠️: `{firstname, lastname, …, created_by: id_user_storage, contacts:[{channel,value}]}`."""
    return await handle(request, sample={"status": "created"})
