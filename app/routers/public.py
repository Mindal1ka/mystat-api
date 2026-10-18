"""§10 Інше (+ §1 Базові адреси) — публічні поверхні без обов'язкової авторизації.

- `GET /v1/config/{app_id}` — конфіг застосунку 🟢 (фронт викликає його ще ДО логіну);
- `GET /v1/mystat/translate` — переклади ❌ (на проді 404); актуальне джерело —
  статика `https://mystat.itstep.org/assets/i18n/{lang}.json`;
- `POST /v1/sentry` — туннель Sentry envelope ✅.
"""
from typing import Any

from fastapi import APIRouter, Depends, Path, Request

from ..deps import AuthCtx, optional_auth
from ..models.common import ApiError
from ..proxy import handle

router = APIRouter(prefix="", tags=["Public"])


@router.get(
    "/v1/config/{app_id}",
    summary="Конфіг застосунку: проєкт, валюти, версії, філії, мови, меню",
    responses={200: {"description": "AppConfig JSON — структура підтверджена живою відповіддю."}},
)
async def app_config(
    request: Request,
    app_id: int = Path(description="ID конфігурації застосунку (фронт завжди викликає 1).", examples=[1]),
    ctx: AuthCtx = Depends(optional_auth),
) -> Any:
    """**GET /v1/config/{app_id}** 🟢 — структура звірена з живою відповіддю; прод: `https://mapi.itstep.org/v1/config/1`.

    Bootstrap-запит SPA: викликається **до логіну**, тому авторизація опціональна
    (`optional_auth`). Шаблон шляху — `/config/{appId}`, фактично завжди `appId=1`.

    Структура (ключове):
    - сам проєкт: `id=50`, `name` **«Lbapi»**, `alias:"lbapi"`, `uuid`, `currency_code`,
      `language_code`, `logo` (data:image/png;base64), `has_admin`, `has_frontend`, …;
    - `currencies[]` — `{code, name, symbol}` (валюти геймифікації/магазину);
    - `appVersions[]` — `{version, critical, link}`: фронт звіряє свою збірку
      (див. також `https://mystat.itstep.org/assets/version.json?t=<ts>`) і при `critical`
      пропонує перезавантаження;
    - `branches[]` — філії (їх `alias` іде в `/v1/mystat/{branch_alias}/…`);
    - `languages[]` — доступні мови інтерфейсу (числові `lang_id` для перекладів);
    - `menuItems[]` — пункти бокового меню (іконки, права, порядок).
    """
    return await handle(request, fixture_name="app-config.json")


@router.get(
    "/v1/mystat/translate",
    summary="Словник перекладів (на проді 404; джерело — статика i18n)",
    responses={
        404: {
            "model": ApiError,
            "description": "Справжнє API відповідає 404 на всіх варіантах — ендпоінт прибрано з прода.",
        },
    },
)
async def translate(request: Request, lang_id: int, ctx: AuthCtx = Depends(optional_auth)) -> Any:
    """**GET /v1/mystat/translate?lang_id={code}** ❌

    Ендпоінт **відсутній у поточному API**: сервер відповідає 404
    (з токеном і без, для будь-якого `lang_id`).

    Актуальне джерело перекладів — **статика фронта**:
    `GET https://mystat.itstep.org/assets/i18n/{lang}.json`
    (~62 КБ для `uk`). Це плоский словник `"ключ": "Переклад"` без вкладеності.

    Як це влаштовано у фронті: застосунок завантажує JSON статики і викликає
    `translate.setTranslation(lang, відповідь)` — після чого всі шаблони беруть рядки за ключами.
    `lang_id` тут — числовий код мови з `/v1/config/{app_id}` → `languages[]`.

    > Для своєї версії віддавайте переклади статикою;
    > цей маршрут залишено **вимкненим**, щоб точно відтворити поведінку прода (404).
    """
    return await handle(request, disabled=True)


@router.post("/v1/sentry", summary="Тунель Sentry (envelope)")
async def sentry_tunnel(request: Request) -> Any:
    """**POST /v1/sentry** ✅ — тунель Sentry envelope; прод: `https://mapi.itstep.org/sentry` (БЕЗ `/v1`).

    Фронт налаштовує Sentry `tunnel` на цей URL, щоб DSN не світився в браузері:
    тіло — сирий envelope (`text/plain` / `application/x-sentry-envelope`: перший рядок —
    заголовок `{event_id, sent_at, dsn}`, далі item-и події). Справжній сервер пересилає
    конверт у Sentry.

    > Mock: завжди `{"received": true}`.
    """
    return await handle(request, sample={"received": True})
