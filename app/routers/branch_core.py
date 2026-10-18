"""§5 Конфіг філії та спільні дані — «гілкові» ендпоінти зі спільними даними акаунта.

Правила стилю (як у routers/auth.py):
- префікс повторює прод: /v1/mystat/{branch_alias}/…;
- кожен ендпоінт: докладний markdown-опис (маркер 🟢/✅/⚠️/❌, реальний URL, заголовки,
  тіло з типами, відповідь, особливості), responses= з моделлю помилки ApiError;
- тіло обробника — завжди через handle()/forward() з ..proxy (mock|proxy режими);
- фікстури для 🟢-ендпоінтів підключаються внутрішнім завантажувачем (без посилань у документації)."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx, language_header, userid_header
from ..models.common import ApiError
from ..proxy import MODE, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", tags=["Branch"], dependencies=[Depends(auth_ctx)])


# ── Ендпоінти ─────────────────────────────────────────────────────────────────


@router.get(
    "/config",
    summary="Конфіг філії: проєкт, меню, платежі, група, прапорці",
    responses={200: {"description": "Конфіг філії — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def config(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/config** 🟢 — структура звірена з живою відповіддю.

    Великий об'єкт «як бачить філію цей студент»: інфо про проєкт + навігація +
    платежі + група студента + прапорці філії. Завантажується фронтом першим і визначає
    весь UI (які пункти меню малювати, які блоки всередині них увімкнені).

    Структура відповіді (довгі значення скорочені):

    - **Проєкт** (ті самі поля, що й у `/v1/config/1`):
      - `id: 50`, `uuid`, `name: "Lbapi"`, `alias: "lbapi"`;
      - `currency_code: "EUR"`, `language_code: "uk"`, `logo` (data:image/png;base64,…);
      - `has_admin: 1`, `has_frontend: 1`, `is_multilang_branches: 0`;
      - `currencies[]` — ~20 валют виду `{code:"USD", name:"Dollars", symbol:"$"}`.
    - **Навігація**:
      - `menuItems: ["main","progress","schedule",…]` — які пункти меню показувати;
      - `menuItemsDetails.main: ["payment","attendance","awards","average_mark","marks",
        "homeworks","reviews","leaderboard"]` — блоки всередині пункту;
      - аналогічні блоки для: `header`, `profile`, `progress`, `schedule`, `materials`,
        `review`, `contacts`, `news`, `homework`, `shop`, `awards`, `clubs`, `payment`.
    - **Платежі**: `paymentConfig: {need_payment_schedule: true}`.
    - **Група студента** (масив `group[]`):
      `{id_tgroups: 1001, id_streams: 398, id_dir: 103, curator_id: null,
      name_tgroups: "П-101", arc_tgroups: 0, is_merged: 0, azure: null,
      is_special_schedule: 0, special_days_per_week: null, special_lessons_per_day: null,
      lessons_type: 0, link_to_group: null}`.
    - **Форми навчання**: `studyForm: [{id_form: 5, form_name: "МКА (вихідні)", form_status: 0}]`,
      поруч `baseStudyForm`.
    - **Прапорці філії**: `country`, `is_school: false`, `is_college: false`,
      `is_children_form`, `is_globus: false`, `is_third_party`, `show_languages[]`.
    - **Онбординг**: `instructions: [{type: "welcome" | "achievements"}]`
      (див. також `/stud-passed-instructions`)."""
    return await handle(request, fixture_name="config.json")


@router.get(
    "/count/page-counters",
    summary="Лічильники-бейджі пунктів меню",
    responses={200: {"description": "Масив лічильників — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def page_counters(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/count/page-counters** 🟢 — структура звірена з живою відповіддю.

    Лічильники-бейджі пунктів меню. Фронт читає їх через `getCounterNumber(counter_type)`
    і малює червоні бейджі на пунктах меню.

    Відповідь — масив записів `{counter_type, counter}`:

    ```jsonc
    [
      { "counter_type": "homework",  "counter": 0 },
      { "counter_type": "review",    "counter": 0 },
      { "counter_type": "news",      "counter": 0 },
      { "counter_type": "materials", "counter": 0 },
      { "counter_type": "chats",     "counter": 0 }
    ]
    ```"""
    return await handle(request, fixture_name="page-counters.json")


@router.get(
    "/counters-header",
    summary="Полегшений лічильник для хедера (вимкнений у багатьох філіях)",
    responses={
        200: {"description": "Очікувався компактний об'єкт лічильників для хедера."},
        404: {"description": "На живому API гілки `pl` повернув 404 — фіча вимкнена."},
        401: {"model": ApiError},
    },
)
async def counters_header(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/counters-header** ❌

    Полегшений лічильник для хедера — **виняток із глобального лоадера**,
    бо викликається часто.

    ❌ На проді увімкнений не в усіх філіях (для гілки `pl` відповідає `404`).
    Фронт переживає його відсутність без помилок (просто не показує бейджі хедера).

    > Mock імітує прод-поведінку: віддає 404 з поясненням у `detail`."""
    return await handle(request, disabled=True)


@router.get(
    "/gaming/get-balances",
    summary="Баланси гейміфікації: кристали / монети / досягнення",
    responses={200: {"description": "Масив балансів — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def gaming_get_balances(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/gaming/get-balances** 🟢 — структура звірена з живою відповіддю.

    Масив балансів гейміфікації — один запис на валюту,
    `alias` ∈ `cristals` | `coins` | `achivements`:

    ```jsonc
    [
      {
        "id": 1101313, "user_id": 100001, "award_id": 50,
        "value": 170,                       // скільки одиниць нараховано
        "rating": 446,                      // рейтинг
        "project_id": 50, "branch_id": 4,
        "created_at": "2024-09-10T09:30:30.000000Z",
        "updated_at": "2026-06-04T14:40:22.000000Z",
        "alias": "cristals"
      }
      // далі записи з alias "coins" і "achivements"
    ]
    ```

    ⚠️ **ВАЖЛИВО про `user_id`**: тут це **logbook_id** (= JWT.`sub`),
    а **НЕ** заголовок `X-UserId` (`id_user_storage`)! Не плутати при зіставленні даних.

    Семантика полів: `value` = скільки одиниць нараховано, `rating` = рейтинг.
    Фронт збирає з масиву об'єкт **`amount`** — словник за ключем `alias`
    (`amount.cristals`, `amount.coins`, `amount.achivements`)."""
    return await handle(request, fixture_name="balances.json")


@router.get(
    "/students/get-promo",
    summary="Реферальний промокод студента",
    responses={200: {"description": "Промокод або null — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def students_get_promo(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/students/get-promo** 🟢 — структура звірена з живою відповіддю.

    Реферальний промокод студента (відповідь може бути `null`, якщо промокода немає):

    ```jsonc
    {
      "promocode": "DEMO1",
      "promo_url": "https://<домен-філії>/uk/promocode?token=<base64({"p":promocode,"o":phone})>",
      "is_school": false, "is_college": false, "is_globus": false,
      "amount": 500                                  // бонус за реферала
    }
    ```

    - `promo_url.token` — base64 JSON виду `{"p": "<promocode>", "o": "<телефон>"}`,
      тобто `token = base64({"p":"DEMO1","o":"000000001"})`;
    - прапорці `is_school/is_college/is_globus` повторюють прапорці філії з `/config`;
    - `amount: 500` — бонус за приведеного друга."""
    return await handle(request, fixture_name="students-promo.json")


@router.get(
    "/students/get-products",
    summary="Спеціальні пропозиції (магазин)",
    responses={200: {"description": "Масив спеціальних пропозицій або []"}, 401: {"model": ApiError}},
)
async def students_get_products(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/students/get-products** 🟢

    Спеціальні пропозиції для студента. Якщо показувати нічого —
    повертається порожній масив `[]` (нормальна відповідь, не помилка)."""
    return await handle(request, sample=[])


@router.get(
    "/profile/check-moderating-data",
    summary="Статуси модерації/верифікації email і телефону",
    responses={200: {"description": "Статуси перевірки — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def check_moderating_data(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/profile/check-moderating-data** 🟢 — структура звірена з живою відповіддю.

    Статуси верифікації контактних даних (фронт показує галочки/попередження в профілі):

    ```jsonc
    {
      "photo": null,
      "email": { "verified_status": "0", "email_address": "...@student.itstep.org" },
      "phone": { "phone_number": "+380...",   "verified_status": "0" }
    }
    ```

    `verified_status` — рядок: `"0"` = не підтверджено (на перевірці), `"1"` = підтверджено."""
    return await handle(request, fixture_name="check-moderating.json")


@router.get(
    "/profile/get-personal-data",
    summary="Персональні дані: ПІБ, дата народження, email-и, телефони, фото",
    responses={200: {"description": "Personal data JSON — структура підтверджена живою відповіддю."}, 401: {"model": ApiError}},
)
async def get_personal_data(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    lang: Optional[str] = Depends(language_header),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**GET /v1/mystat/{alias}/profile/get-personal-data** 🟢 — структура звірена з живою відповіддю.

    Персональні дані для екрана «Особисті дані»:

    ```jsonc
    {
      "photo": "https://fsx1.itstep.org/api/v1/files/<hash>",   // або null
      "photo_alternative": null,
      "fio": "Прізвище Ім'я По батькові",
      "birthdate": "2009-05-14",
      "emails": [ { "value": "особистий@gmail.com" }, { "value": "логін@student.itstep.org" } ],
      "phones": [ { "value": "+380..." } ]
    }
    ```

    Фото лежить на файловому сервері `fsx1.itstep.org`; `photo_alternative` — запасний варіант.
    Зміна цих полів — через `POST /profile/change-personal-data`."""
    return await handle(request, fixture_name="personal-data.json")


@router.post(
    "/profile/change-personal-data",
    summary="Змінити персональні дані (multipart/form-data)",
    responses={
        200: {"description": "Підтвердження зміни (точна форма відповіді ⚠️)."},
        401: {"model": ApiError},
    },
)
async def change_personal_data(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    birthdate: Optional[str] = Form(default=None, description="Дата народження, YYYY-MM-DD."),
    phone: Optional[str] = Form(default=None, description="Телефон."),
    email: Optional[str] = Form(default=None, description="E-mail."),
    photo: Optional[UploadFile] = File(default=None, description="Файл нового фото профілю."),
    child_id: Optional[int] = Query(
        default=None,
        description="ID дитини (logbook_id) — коли форму надсилає батько ⚠️.",
    ),
) -> Any:
    """**POST /v1/mystat/{alias}/profile/change-personal-data** ✅⚠️

    Зміна персональних даних з екрана профілю. Тіло — `multipart/form-data`:

    - `birthdate: str` — дата народження (опціонально);
    - `phone: str` — телефон (опціонально);
    - `email: str` — e-mail (опціонально);
    - `photo: file` — нове фото профілю (опціонально).

    ⚠️ Query-параметри передаються **окремо від тіла форми** — наприклад `child_id`,
    коли персональні дані змінює батько для дитини (інші параметри ⚠️).

    > Після успішної зміни фронт перечитує дані через
    > `GET /profile/get-personal-data` і статус верифікації через
    > `GET /profile/check-moderating-data` (нові email/телефон ідуть на модерацію)."""
    return await handle(request, sample={"status": "ok"})


# ── Нове у збірці 2026-10 ────────────────────────────────────────────────────


class ActiveChildrenIn(BaseModel):
    """Тіло `get-active-children` ✅: `{ids: [logbook_id, …]}` — logbook_id усіх дітей батька."""

    model_config = ConfigDict(extra="allow")

    ids: list[int] = Field(description="logbook_id дітей (profiles[].logbook_id з /auth/me).", examples=[[100001, 100002]])


class ActivityEvent(BaseModel):
    """Один інтервал активності у розділі UI."""

    section: str = Field(
        description="Розділ UI: main, homework, progress, schedule, materials, review, awards, "
        "home_achievements, home_achievements_stud, shop, nutrition, clubs, payment, news, "
        "cyberfit, contacts, chat, other.",
        examples=["homework"],
    )
    seconds: int = Field(ge=1, le=1800, description="Активні секунди (сегмент ріжеться кожні 1800 с).", examples=[95])
    continued: Optional[bool] = Field(
        default=None, description="true, якщо це продовження того самого сегмента (поле опускається, коли false)."
    )


class ActivityEventsIn(BaseModel):
    """Пакет подій активності ✅: `{events: [...]}` (до 100 штук в одному запиті)."""

    model_config = ConfigDict(extra="allow")

    events: list[ActivityEvent] = Field(max_length=100)


@router.post(
    "/relatives/get-active-children",
    summary="Які діти батька «активні» у філії + їхні групи",
    responses={401: {"model": ApiError}},
)
async def get_active_children(
    body: ActiveChildrenIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{alias}/relatives/get-active-children** ✅ (нове у збірці 2026-10)

    Викликається лише для акаунта-батька (`profile === "relative"`) після завантаження
    `/auth/me`; тіло `{ids}` — `logbook_id` усіх дітей. Відповідь:
    `{active_ids: [logbook_id…], groups: {"<logbook_id>": "<назва групи>"}}`.
    Фронт зберігає `active_ids` (якщо вибрана дитина не серед них — перемикає на першу
    активну) та `groups` (підпис групи біля дитини в меню профілю). Будь-яка помилка
    ігнорується (`catchError → null`).
    """
    return await handle(
        request,
        sample={"active_ids": body.ids[:1], "groups": {str(i): "GROUP-001" for i in body.ids}},
    )


@router.post(
    "/activity/events",
    summary="Телеметрія часу, проведеного у розділах UI",
    responses={401: {"model": ApiError}},
)
async def activity_events(
    body: ActivityEventsIn,
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    user_id: Optional[str] = Depends(userid_header),
) -> Any:
    """**POST /v1/mystat/{alias}/activity/events** ✅ (нове у збірці 2026-10)

    Фронт веде облік активного часу по розділах (події `pointerdown/keydown/wheel/scroll/
    mousemove/touchstart`, пауза після 2 хв бездіяльності) і пачками шле на цей шлях:
    `{events:[{section, seconds, continued?}]}`. Чергу скидають при сховані вкладки
    (`fetch(..., keepalive:true)`) та кожні ~5 хв; пачка ≤100 подій, черга ≤500.

    - Заголовки: `Authorization`, `X-UserId` (= `id_user_storage`, береться зі scope запису).
    - Відповідь клієнтом не читається ⚠️; клієнт відкидає подію при 4xx (крім 401) і
      повторює при 5xx/мережевій помилці. Глобальний error-інтерцептор НЕ показує тост на 500
      для цього шляху.
    - Не надсилається під час «входу як студент» (`localStorage.logbook_impersonation`).
    """
    return await handle(request, sample={"status": "ok"})
