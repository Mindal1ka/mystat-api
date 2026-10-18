"""§6 Навчальні сервіси (з гілкою) + хвіст §3 (sms/mailing) — студентські дрібниці.

Правила стилю (як у routers/auth.py):
- «філійні» шляхи повторюють прод: /v1/mystat/{branch_alias}/...;
- кожен ендпоінт: детальний markdown-опис (маркер 🟢/✅/⚠️/❌, реальний URL, заголовки,
  тіло з типами, відповідь, особливості), responses= з моделлю помилки ApiError;
- тіло обробника — завжди через handle()/forward() з ..proxy (mock|proxy режими);
- фікстури examples/*.json підключаються для 🟢-ендпоінтів за іменем файлу.
"""
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import MODE, forward, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", tags=["Study"])


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class NotificationCreateIn(BaseModel):
    """Рапорт про відсутність (форма «Я не прийду»). Поля відновлені З КОДУ
    ФРОНТА ✅ (getPayload форми absence в чанку Chm3fOqc)."""

    model_config = ConfigDict(extra="allow")

    category: Literal["late", "absence", "online_presence"] = Field(
        description="Категорія рапорта (радіокнопки форми): late | absence | online_presence.",
        examples=["absence"],
    )
    date_start: str = Field(description="Початок періоду YYYY-MM-DD (дефолт форми — сьогодні).", examples=["2026-08-24"])
    date_end: str = Field(description="Кінець періоду YYYY-MM-DD.", examples=["2026-08-24"])
    student_id: int = Field(description="logbook_id студента (= JWT.sub / account.id).", examples=[100001])
    text: str = Field(description="Коментар-причина (обов'язковий на фронті).", examples=["Хворію, відвідаю лікаря."])
    additional_answer: Optional[str] = Field(default=None, description="Відповідь на додаткове питання (дефолт фронта 'no_join_online').")
    additional_text: Optional[str] = Field(default=None, description="Додатковий текст (опціонально).")


class PassedInstructionIn(BaseModel):
    """Позначити онбординг-інструкцію пройденою."""

    type: Literal["welcome", "achievements"] = Field(
        description='Код інструкції ("welcome" | "achievements"; у доку допускаються й інші ⚠️).',
        examples=["welcome"],
    )


class ContractSuspendIn(BaseModel):
    """Призупинення навчання — коментар обов'язковий, мінімум 10 символів ✅."""

    comment: str = Field(min_length=10, description="Причина призупинення (min 10 символів).", examples=["Через сімейні обставини"])


class ScreenReviewIn(BaseModel):
    """Відгук з екрана (соцопитування після заняття). Поля та query-параметри ⚠️."""

    model_config = ConfigDict(extra="allow")

    review: Optional[str] = Field(default=None, description="Текст відгуку ⚠️.")
    rating: Optional[int] = Field(default=None, ge=1, le=5, description="Оцінка місця навчання ⚠️.", examples=[5])


class VerifiedPhoneIn(BaseModel):
    """Перевірка SMS-коду при підтвердженні телефону. Точний набір полів ⚠️."""

    model_config = ConfigDict(extra="allow")

    phone: str = Field(description="Телефон профілю.", examples=["+380..."])
    code: str = Field(description="Код з SMS.", examples=["4821"])


class MailingConfirmIn(BaseModel):
    """Тіло `POST /mailing/send-confirmation` ✅ (бандл ZhxNLKrC: body `{email:t}`)."""

    model_config = ConfigDict(extra="allow")

    email: str = Field(description="E-mail для підтвердження.", examples=["student@example.com"])
    key: Optional[str] = Field(default=None, description="Не використовується сервером; ігноруйте.")


class MailingKeyIn(BaseModel):
    """Тіло `POST /{alias}/mailing/confirm` ✅ (фронт шле `{key:e}`)."""

    key: str = Field(description="Ключ (токен) з посилання підтвердження в листі.", examples=["c3f9…long-token"])


# ── Students ──────────────────────────────────────────────────────────────────
# POST /students/evaluate-lesson — канонічний типізований ендпоінт живе
# в routers/extras.py (поля {mark_lesson, mark_teach, comment, id} підтверджені бандлом).


@router.post("/notification/create", summary="Рапорт про відсутність («Я не прийду»)")
async def notification_create(body: NotificationCreateIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/notification/create** ✅ (payload з коду фронта)

    Рапорт про відсутність/запізнення/онлайн-присутність (форма «Я не прийду»).

    - **Body** ✅: `{category:"late"|"absence"|"online_presence", date_start, date_end,
      student_id, text, additional_answer?, additional_text?}`;
    - фронт читає відповідь: якщо `error[].length` — показує `error[0].message`
      (наприклад «there_are_no_classes_on_the_day_you_selected» — у обраний день
      немає занять).

    > Mock: `{error: []}`; proxy — форвард.
    """
    return await handle(request, sample={"error": []})


# ── Онбординг ─────────────────────────────────────────────────────────────────


@router.get("/stud-passed-instructions", summary="Пройдені онбординг-інструкції")
async def stud_passed_instructions_get(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/stud-passed-instructions** 🟢

    Список уже пройдених інструкцій онбордингу.

    - **Відповідь**: масив кодів інструкцій (`["welcome", ...]`).
    - Жива відповідь для нового акаунта: **порожній масив `[]`** — поки нічого не позначено.

    > Mock: `[]` (фікстура `examples/stud-passed-instructions.json`, якщо з'явиться);
    > proxy — форвард.
    """
    return await handle(request, fixture_name="stud-passed-instructions.json", sample=[])


@router.post("/stud-passed-instructions", summary="Позначити інструкцію пройденою")
async def stud_passed_instructions_post(body: PassedInstructionIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/stud-passed-instructions** ✅

    Позначити онбординг-інструкцію пройденою (фронт викликає після показу привітання
    і розділу досягнень).

    - **Body** ✅: `{type:"welcome"|"achievements"}` (у доку допускаються й інші коди ⚠️).
    - **Відповідь**: статус позначки; після цього GET перестає повертати код порожнім.

    > Mock: `{status:"ok"}`; proxy — форвард.
    """
    return await handle(request, sample={"status": "ok"})


# ── Contract ──────────────────────────────────────────────────────────────────


@router.get(
    "/contract/conditions",
    summary="Умови договору",
    responses={404: {"model": ApiError, "description": "Фіча вимкнена у філії — 404 на живому API."}},
)
async def contract_conditions(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/contract/conditions** ❌

    Умови договору філії.

    - На живому API гілки `pl` — **404**: фіча вимкнена у філії.
    - Фронт обробляє 404 мовчки (розділ просто не відкривається).

    > Mock: імітація вимкненої фічі — HTTP 404 (`handle(disabled=True)`).
    """
    return await handle(request, disabled=True)


@router.post("/contract/suspend", summary="Призупинення навчання")
async def contract_suspend(body: ContractSuspendIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/contract/suspend** ✅

    Призупинення навчання за договором (форма з обов'язковим коментарем).

    - **Body** ✅: `{comment:str}` — мінімум **10 символів** (валідація на фронті).
    - **Відповідь**: статус операції; договір переходить у стан призупинення.

    > Приклад curl — див. §12 «Призупинення договору». Mock: `{status:"ok"}`; proxy — форвард.
    """
    return await handle(request, sample={"status": "ok"})


# ── Cyberfit ──────────────────────────────────────────────────────────────────


@router.get("/cyberfit/get-stats", summary="Статистика Cyberfit")
async def cyberfit_get_stats(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/cyberfit/get-stats?{params}** 🟢

    Статистика платформи Cyberfit (тренування з кібербезпеки).

    - **Відповідь**: **200**, але **`{}`**, якщо Cyberfit до акаунта не підключений —
      жива відповідь для звичайного студента саме така.
    - Query-параметри `{params}` опціональні (точний склад ⚠️), у режимі proxy
      передаються на живе API як є.

    > Mock: `{}` (фікстура `examples/cyberfit-get-stats.json`, якщо з'явиться);
    > proxy — форвард разом із query.
    """
    return await handle(request, fixture_name="cyberfit-get-stats.json", sample={})


# ── Utility ───────────────────────────────────────────────────────────────────


@router.get(
    "/utility/statistic/achievements",
    summary="Досягнення (statistic)",
    responses={404: {"model": ApiError, "description": "Ендпоінт недоступний — 404 на живому API."}},
)
async def utility_statistic_achievements(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/utility/statistic/achievements?{params}** ❌

    Досягнення через `/utility/statistic`.

    - На живому API гілки `pl` — **404** (ендпоінт прибрано/вимкнено у філії).

    > Mock: імітація вимкненої фічі — HTTP 404 (`handle(disabled=True)`).
    """
    return await handle(request, disabled=True)


@router.post("/utility/social-review/screen-review", summary="Надсилання відгуку з екрана")
async def social_review_screen_review(body: ScreenReviewIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/utility/social-review/screen-review?{params}** ⚠️

    Соцопитування: надсилання відгуку з екрана (після заняття фронт пропонує оцінити
    місце навчання).

    - **Query** ⚠️: `{params}` — точний склад не підтверджений, у режимі proxy
      передаються на живе API як є.
    - **Body** ⚠️: текст відгуку та/або оцінка — модель приймає extra-поля.
    - **Відповідь**: статус збереження відгуку.

    > Mock: `{status:"ok"}`; proxy — форвард.
    """
    return await handle(request, sample={"status": "ok"})


@router.get(
    "/utility/social-review/get-review-list",
    summary="Список відгуків",
    responses={404: {"model": ApiError, "description": "Фіча вимкнена у філії — 404 на живому API."}},
)
async def social_review_get_review_list(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/utility/social-review/get-review-list?{params}** ❌

    Список відгуків соцопитування.

    - На живому API гілки `pl` — **404**: фіча вимкнена у філії.

    > Mock: імітація вимкненої фічі — HTTP 404 (`handle(disabled=True)`).
    """
    return await handle(request, disabled=True)


@router.get(
    "/utility/social-review/get-study-place-list",
    summary="Список місць навчання для відгуку",
    responses={404: {"model": ApiError, "description": "Фіча вимкнена у філії — 404 на живому API."}},
)
async def social_review_get_study_place_list(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/utility/social-review/get-study-place-list?{params}** ❌

    Список місць навчання для форми відгуку (що саме оцінює студент).

    - На живому API гілки `pl` — **404**: фіча вимкнена у філії.

    > Mock: імітація вимкненої фічі — HTTP 404 (`handle(disabled=True)`).
    """
    return await handle(request, disabled=True)


# ── SMS: підтвердження телефону при реєстрації (хвіст §3) ───────────────────


@router.post("/sms/send-code", summary="Надіслати SMS-код на телефон профілю")
async def sms_send_code(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    body: Optional[dict[str, Any]] = Body(default=None, description="Тіло не використовується — фронт шле JSON `null`."),
) -> Any:
    """**POST /v1/mystat/{branch_alias}/sms/send-code** ✅

    Надіслати код підтвердження на телефон профілю (крок реєстрації/зміни телефону).

    - **Body**: `null` — параметрів немає, телефон береться з профілю
      (`Body(default=None)` — тіло можна взагалі не передавати).
    - **Відповідь**: статус надсилання; код приходить у SMS.

    > Mock: `{status:"sent"}`; proxy — форвард.
    """
    return await handle(request, sample={"status": "sent"})


@router.post("/sms/verified-phone", summary="Перевірити код підтвердження телефону")
async def sms_verified_phone(body: VerifiedPhoneIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/sms/verified-phone** ⚠️

    Перевірка SMS-коду — завершення підтвердження телефону.

    - **Body** ⚠️: `{phone:str, code:str}` — точний набір полів не підтверджений,
      модель приймає extra-поля.
    - **Відповідь**: статус верифікації; при неправильному коді — помилка API.

    > Mock: `{status:"verified"}`; proxy — форвард.
    """
    return await handle(request, sample={"status": "verified"})


# ── Mailing: підтвердження e-mail (хвіст §3) ─────────────────────────────────


@router.post(
    "/mailing/send-confirmation",
    summary="Надіслати підтвердження e-mail (sendEmail)",
    responses={
        200: {"description": "Статус надсилання листа ⚠️."},
        400: {"model": ApiError, "description": "Некоректний/уже підтверджений e-mail ⚠️."},
    },
)
async def mailing_send_confirmation(body: MailingConfirmIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/mailing/send-confirmation** ✅

    Фронт (`sendEmail`): `POST ${getEndpoint()}/send-confirmation` body `{email:t}`.
    Підтвердження за посиланням з листа виконує окремий
    `POST /mailing/confirm {key}` (див. ендпоінт нижче).

    - **Body** ✅: `{email:str}`;
    - фронт зберігає `emailExpiry` у localStorage (`verification`).
    """
    return await handle(request, sample={"status": "ok", "sent_to": body.email})


@router.post("/mailing/confirm", summary="Підтвердити e-mail за ключем з листа (confirm)")
async def mailing_confirm(body: MailingKeyIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/mailing/confirm** ✅⚠️

    Підтвердження e-mail: фронт `confirm(token, alias)` →
    `POST /${alias}/mailing/confirm` body `{key:<token>}` — ключ береться зі шляху
    посилання в листі, alias філії — з query того ж посилання.
    Фронт НЕ читає тіло відповіді, а підмінює його локально: успіх →
    `{message:"email_has_been_confirmed", type:"success"}`, помилка →
    `email_is_not_confirmed`. Реальна форма відповіді сервера ⚠️.
    """
    return await handle(request, sample={"status": "ok", "key": body.key})
